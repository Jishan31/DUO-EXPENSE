"""
The in-app AI assistant. Builds a live snapshot of the signed-in user's
financial data as a system prompt, then calls the Gemini API (free tier —
no credit card required, get a key at aistudio.google.com/apikey).

Design choices:
- Fails soft. If no API key is configured, or the call errors, this raises a
  typed exception the route layer turns into a friendly chat message —
  never a 500, never breaks the rest of the app.
- The assistant is read-only by design: the system prompt explicitly tells
  it not to claim to perform actions (add expenses, change settings, etc.),
  since it has no tool access to actually do so.
"""
import os
from datetime import date

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from models import Expense, Income, Category, Loan


class AssistantNotConfigured(Exception):
    pass


class AssistantError(Exception):
    pass


# Remembers whichever model name actually worked last time, for this
# process's lifetime — avoids re-discovering on every single message.
_cached_working_model = None


def _discover_working_model(client, exclude=()):
    """
    Gemini model names drift over time (Google regularly retires old
    generations and ships new ones), so a hardcoded default can fail for a
    key even when the code is otherwise correct. This asks the API directly
    what THIS key can actually use, and returns Flash candidates (free-tier
    friendly) ranked by likely canonicalness — excluding any names already
    known not to work, since a deprecated model can still be *listed* even
    once Google has stopped serving it for new keys.

    Returns (ordered_candidate_list, debug_message).
    """
    try:
        models = list(client.models.list())
    except Exception as e:
        return [], f"ListModels failed: {getattr(e, 'message', None) or str(e)}"

    candidates = []
    all_names = []
    for m in models:
        name = getattr(m, "name", "") or ""
        short = name.split("/")[-1]  # API returns "models/gemini-2.5-flash" style names
        all_names.append(short)
        skip_terms = ("image", "tts", "embed", "vision", "live", "audio")
        if "flash" in short.lower() and not any(t in short.lower() for t in skip_terms) and short not in exclude:
            candidates.append(short)

    candidates.sort(key=len)  # shorter names tend to be the canonical alias, e.g. "gemini-2.5-flash"
    if candidates:
        return candidates, None
    return [], f"ListModels returned {len(all_names)} models, none matched a Flash filter: {all_names[:10]}"


def _financial_snapshot(user):
    today = date.today()
    expenses = Expense.query.filter_by(user_id=user.id).all()
    incomes = Income.query.filter_by(user_id=user.id).all()
    categories = Category.query.filter_by(user_id=user.id).all()

    month_expenses = [e for e in expenses if e.date.year == today.year and e.date.month == today.month]
    month_incomes = [i for i in incomes if i.date.year == today.year and i.date.month == today.month]
    total_expense = sum(e.amount for e in month_expenses)
    total_income = sum(i.amount for i in month_incomes)

    by_category = {}
    for e in month_expenses:
        by_category[e.category.name] = by_category.get(e.category.name, 0) + e.amount
    top_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]

    overspent = [c.name for c in categories if c.monthly_budget and c.spent_this_month() > c.monthly_budget]

    loans = Loan.query.filter_by(user_id=user.id, status="active").all()
    upcoming_dues = []
    for loan in loans:
        nd = loan.next_due()
        if nd:
            days = (nd.due_date - today).days
            if days <= 14:
                upcoming_dues.append(f"{loan.name}: Rs.{nd.amount:,.0f} due {nd.due_date.isoformat()}")

    lines = [
        f"Today's date: {today.isoformat()}",
        f"This month's income so far: Rs.{total_income:,.2f}",
        f"This month's expenses so far: Rs.{total_expense:,.2f}",
        f"Balance this month: Rs.{(total_income - total_expense):,.2f}",
    ]
    if user.monthly_budget_total:
        lines.append(f"Overall monthly budget: Rs.{user.monthly_budget_total:,.2f}")
    if top_categories:
        lines.append("Top spending categories this month: " +
                      ", ".join(f"{name} (Rs.{amt:,.0f})" for name, amt in top_categories))
    if overspent:
        lines.append("Categories currently over their budget: " + ", ".join(overspent))
    if upcoming_dues:
        lines.append("Loan/EMI payments due within 14 days: " + "; ".join(upcoming_dues))

    return "\n".join(lines)


def build_system_prompt(user):
    snapshot = _financial_snapshot(user)
    return (
        f"You are the in-app assistant for Duo Expense, a personal and small-business "
        f"finance tracker. You're helping the signed-in user, {user.username}. You can "
        f"explain how to use any feature (the Expense Wheel, OCR bill scanner, budgets, "
        f"loans/EMI tracking, business inventory, clients, and invoicing with UPI QR "
        f"codes) and answer questions about their own data using the snapshot below.\n\n"
        f"Live snapshot of their data right now:\n{snapshot}\n\n"
        f"Stay strictly on topic: only answer questions about the user's own finances, "
        f"their data shown above, general personal-finance/budgeting guidance, or how to "
        f"use a Duo Expense feature. If asked something unrelated — trivia, coding help, "
        f"other apps, current events, anything outside personal finance and this app — "
        f"decline briefly and redirect, e.g. \"I'm just here for your Duo Expense data and "
        f"finances — ask me about your spending, budgets, or loans!\" Don't answer the "
        f"off-topic question first and then redirect; decline it outright.\n\n"
        f"Keep replies short and conversational — this is a small chat widget, not a "
        f"report. Use Rs. for currency. You have no ability to take actions in the app "
        f"(you cannot add expenses, change budgets, or modify settings) — if asked to do "
        f"something actionable, tell the user how to do it themselves rather than "
        f"claiming to have done it."
    )


def ask_assistant(user, message, history):
    """
    history: list of ChatMessage objects (oldest first), NOT including `message`.
    Returns the assistant's reply text, or raises AssistantNotConfigured / AssistantError.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AssistantNotConfigured(
            "The AI assistant isn't set up yet. Get a free key (no credit card needed) at "
            "aistudio.google.com/apikey, add GEMINI_API_KEY=your-key-here to a .env file "
            "in the project root (see .env.example), then restart the app."
        )

    # Pinned to v1beta explicitly: ListModels and generateContent can
    # otherwise resolve against different default API versions, and some
    # models (including gemini-2.5-flash) are only registered under v1beta.
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))
    global _cached_working_model
    env_model = os.environ.get("ASSISTANT_MODEL", "").strip()
    model = env_model or _cached_working_model or "gemini-2.5-flash"

    # Gemini uses role="model" for the assistant's turns, not "assistant"
    contents = []
    for m in history:
        role = "model" if m.role == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    gen_config = types.GenerateContentConfig(
        system_instruction=build_system_prompt(user),
        max_output_tokens=600,
    )

    def _call(model_name):
        return client.models.generate_content(model=model_name, contents=contents, config=gen_config)

    try:
        response = _call(model)
    except genai_errors.ClientError as e:
        status = getattr(e, "code", None)
        raw_message = getattr(e, "message", None) or str(e)
        if status in (401, 403):
            raise AssistantNotConfigured(
                "The configured GEMINI_API_KEY was rejected — double check it's correct and active. "
                f"Raw error: {raw_message}"
            )
        if status == 429:
            raise AssistantError(
                "The assistant hit its free-tier rate limit — wait a minute and try again."
            )
        if status == 404 and not env_model:
            # Our default (or previously-cached) model name isn't available for this
            # key/project — ask the API what actually is, and try real candidates in
            # turn. A deprecated model can still be *listed* even once Google has
            # stopped serving it, so the top-ranked name isn't trustworthy on its
            # own — only an actual successful call proves a candidate works.
            candidates, debug_info = _discover_working_model(client, exclude={model})
            if not candidates:
                raise AssistantError(
                    f"Model '{model}' isn't available for this key (raw error: {raw_message}). "
                    f"Discovery info: {debug_info or 'no working Flash candidates found'}. "
                    f"Set ASSISTANT_MODEL=<a model name from your key's list> in .env to override."
                )
            last_err = None
            for candidate in candidates[:4]:
                try:
                    response = _call(candidate)
                    _cached_working_model = candidate
                    last_err = None
                    break
                except Exception as retry_err:
                    last_err = retry_err
            if last_err is not None:
                raw_retry = getattr(last_err, "message", None) or str(last_err)
                raise AssistantError(
                    f"Tried {min(len(candidates), 4)} model(s) from your key's list, none worked. "
                    f"Last error: {raw_retry}"
                )
        else:
            raise AssistantError(f"The assistant couldn't process that request ({status}): {raw_message}")
    except genai_errors.APIError as e:
        raw_message = getattr(e, "message", None) or str(e)
        raise AssistantError(f"The assistant is temporarily unavailable: {raw_message}")

    text = getattr(response, "text", None)
    return (text or "").strip() or "I'm not sure how to respond to that — could you rephrase?"

