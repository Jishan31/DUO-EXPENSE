# Duo Expense — AI Expense Tracker (Phase 1–4)

A premium, glassmorphic expense tracker built with Flask + SQLite. Phases 1
(auth, dashboard, the Expense Wheel), 2 (OCR bill scanner, budgets + alerts,
charts/reports), 3 (Loans & EMI tracking), and 4 (Business/Inventory, Client
management, Invoice generator with PDF + QR) are complete and functional.
See "What's next" below for what's left from the brief.

## Run it locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. The SQLite database is
created automatically on first run at `instance/expense_tracker.db`. If
you're upgrading from a Phase 1 install, your existing database is upgraded
automatically the first time you run `python app.py` — no need to delete it.

### OCR bill scanner — one extra system dependency

The bill scanner uses [Tesseract OCR](https://github.com/tesseract-ocr/tesseract),
which is a system program, not a Python package, so `pip install` alone
won't get you there. Install it once:

- **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr`
- **macOS:** `brew install tesseract`
- **Windows:** install from the [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), then add it to your PATH

If Tesseract isn't installed, the app still runs fine — the scanner just
tells the user to enter details manually instead of crashing.

### AI Assistant — one extra step (optional)

The floating 💬 chat widget needs a Gemini API key (free tier, no credit card) to actually respond
(the rest of the app works fully without it):

```bash
cp .env.example .env
```

Then open `.env` and fill in:
```
GEMINI_API_KEY=AIza...   # get one free at aistudio.google.com/apikey
```

Restart `python app.py` after saving. Without a key, the widget still opens
and shows a clear setup message instead of failing silently.

Before deploying anywhere public, set a real `SECRET_KEY` environment
variable instead of the default in `config.py`.

## What's built in Phase 1

- **Auth** — register, login, logout. Passwords hashed with Werkzeug,
  sessions via Flask-Login. Phone/OTP field is a demo stub (no real SMS
  provider wired up yet — see below).
- **Landing page** — animated lavender gradient, floating glass hero,
  feature + steps sections, dark/light mode toggle.
- **Login / Register** — glassmorphic cards, password-strength meter,
  Google/Apple buttons are present but inert (need real OAuth credentials).
- **Dashboard** — top nav, 5 live summary cards (Income, Expense, Balance,
  Budget Remaining, Savings), quick actions.
- **The Expense Wheel** — the signature piece. SVG-generated annular
  sectors, one per category, sized and colored live from your data. Tap a
  wedge to log an expense in that category; tap the center orb to jump to
  the Overview panel. Fully data-driven — Add/Edit/Delete Category reshapes
  it instantly.
- **Expense CRUD** — add/edit/delete, category picker, payment mode,
  merchant, GST, tags, location, description. Receipt upload UI is present;
  OCR extraction is not wired up yet (Phase 2).
- **Income CRUD** — add/edit/delete by source (Salary, Business,
  Freelancing, Investments, Others).
- **Category management** — add/edit/delete via a glass modal, with icon
  and color pickers.
- **Recent Transactions + Category Breakdown** — live on the dashboard.

## What's built in Phase 2

- **OCR Bill Scanner** — upload or camera-capture a receipt on the Add
  Expense page. Tesseract reads the image; regex/keyword heuristics pull out
  merchant, total amount, GST, date, a best-guess category, and candidate
  line items, then pre-fill the form. You always review before saving.
- **Budgets** — set an overall monthly budget and a per-category budget
  (via the category modal). The Budgets page shows animated circular
  progress gauges, spent/remaining figures, and status pills (on track /
  near limit / over budget).
- **Overspending alerts** — computed live from your budgets vs. actual
  spend. Shown as banners on the Dashboard and Budgets page, and in a
  notification-bell dropdown in the top nav.
- **Charts & Reports** — a new Reports page with five live Chart.js
  charts: category-wise pie, income vs. expense (6 months), monthly trend,
  weekly trend, and cash/UPI/card payment-mode breakdown.
- **Auto-migration** — a small built-in schema upgrader so upgrading from
  Phase 1 doesn't require deleting your database.

## What's built in Phase 3

- **Loans & EMI tracking** — one unified module covering both the "EMI"
  and "Loan" sections of the original brief (they overlap almost
  completely). Add a loan with amount, interest rate, and tenure; Duo Expense
  runs a standard reducing-balance EMI calculation and builds the full
  month-by-month amortization schedule automatically (principal/interest
  split per installment, verified against known reference EMI values).
- **Live EMI calculator** — the Add Loan form shows estimated EMI, total
  interest, and total payment as you type, before you even save.
- **Payment history & "Mark Paid"** — mark installments paid one at a
  time; progress gauges and remaining-principal figures update from actual
  recorded payments, not just theoretical schedule.
- **Due-date alerts** — overdue and due-soon (within 7 days) installments
  feed into the same notification bell as budget alerts.

## UI fixes and design pass

- Fixed a dark-mode contrast bug where the category and payment-mode
  selectors on the Add Expense page had unreadable (white-on-white) text —
  they were using a hardcoded light-only background with no dark-mode
  variant. Introduced theme-aware surface tokens (`--surface-soft` etc.)
  and audited the rest of the app for the same issue.
- Added real hover feedback to those selectors (previously had none).
- Deepened the glass system toward genuine Apple-style "liquid glass":
  layered specular highlight gradients on every glass surface, a moving
  shine sweep on primary buttons, richer blur/saturation, and inset
  highlight/shadow edges that mimic light catching curved glass.
- Added visible keyboard-focus rings site-wide (accessibility).

## What's built in Phase 4

- **Business / Inventory** — track products with purchase price, selling
  price, stock quantity, and a low-stock reorder threshold. Revenue, units
  sold, and profit/loss are computed live from actual invoice line items
  (not stored redundantly, so they can't drift out of sync). Includes an
  inventory pie chart and a low-stock alert list, merged into the same
  notification bell as budget and loan alerts.
- **Client management** — name, phone, email, notes, and a full invoice
  history per client with running totals (billed / paid / pending).
- **Invoice generator** — a proper line-item builder: pick an existing
  product (auto-fills price and checks stock) or add a custom item,
  discount %, GST %, due date, and notes, with totals updating live as you
  type. On save, invoices deduct stock automatically (validated server-side
  so you can't oversell); deleting an invoice restores it.
- **Invoice PDF + QR code** — download a formatted PDF (via reportlab)
  with an embedded QR code, or use the on-screen print-friendly view
  (browser print / Ctrl+P). Payments can be recorded partially; status
  moves from unpaid → paid automatically once the balance clears.
  *(PDFs use "Rs." instead of "₹" — reportlab's base font doesn't include
  that glyph, so it's swapped for the one place it'd otherwise render as a
  black box. The web UI still shows ₹ everywhere else.)*
- Verified end-to-end: invoice math (subtotal/discount/GST/total), stock
  deduction and restoration, product profit calculation, valid PDF/PNG
  output, and stock-overselling validation all confirmed with real test
  data before shipping.

## Latest fixes (this update)

- **Rebranded** from "Duo Expense" to **Duo Expense** throughout the app, PDF invoices, and page titles.
- **Notification dropdown was getting clipped** — a `overflow-y: auto` added to the sidebar for scroll support was cutting off the dropdown's text. Fixed by moving floating panels (notifications, search) outside the sidebar's DOM subtree entirely and positioning them via JS in real viewport coordinates — this also avoids a second, subtler bug where the sidebar's mobile slide-in `transform` would have broken `position: fixed` children.
- **Chart text still invisible in dark mode, round 2** — the previous fix only updated a chart's legend/axis colors if those config objects already existed, which most charts didn't have explicitly set, so it silently skipped them. Also fixed a timing bug where the initial theme color was read before dark mode had even been applied to the page (so charts could render wrong on first load if dark mode was already your saved preference).
- **Invoice QR codes are now real UPI payment links.** Add your UPI ID on the Business page and invoice QR codes become actual `upi://pay` deep links — scanning with GPay/PhonePe/Paytm opens a pre-filled payment screen. Without one, it falls back to a plain-text summary (which is what "doesn't show details" was — most scanner apps only treat recognized URI schemes as actionable; plain text just displays/copies).
- **Global search now actually works.** It was previously a stub that only fired on the Dashboard and ignored the query entirely. Now searches Expenses, Income, Categories, Clients, Products, Loans/EMIs, and Invoices from any page, with a live dropdown of grouped results — closing out that item from the original brief.

## Deploying this as a real website

The short version: **SQLite (what this app uses locally) is not suitable for
production hosting** — most hosts wipe the local filesystem on every deploy,
which would delete your database. You have two realistic paths:

### Path A — Render.com (recommended, beginner-friendly, free tier available)

1. Push this project to a GitHub repo (see the git steps below if you haven't already).
2. Create a free **PostgreSQL** database on [Render](https://render.com) — this replaces SQLite for production. Render gives you a connection string like `postgresql://user:pass@host/dbname`.
3. Add `psycopg2-binary` to `requirements.txt` (the Postgres driver):
   ```
   pip install psycopg2-binary
   pip freeze | grep psycopg2-binary >> requirements.txt
   ```
4. In `config.py`, change the database line to prefer an environment variable:
   ```python
   SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "expense_tracker.db"))
   ```
   (Render's Postgres URLs start with `postgres://` — SQLAlchemy 2.x needs `postgresql://`; if you hit an error about the URL scheme, add `.replace("postgres://", "postgresql://", 1)` to that line.)
5. Create a new **Web Service** on Render, connect your GitHub repo, and set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app` (add `gunicorn` to `requirements.txt` first)
   - **Environment variables:** `SECRET_KEY` (a long random string), `DATABASE_URL` (from step 2), and `GEMINI_API_KEY` if you want the AI assistant live.
6. Tesseract (for OCR) isn't installed on Render by default — add a `render-build.sh` that runs `apt-get install -y tesseract-ocr` before the pip install, or accept that OCR will show its "enter manually" fallback in production until you do.
7. Deploy. Render gives you a live `https://yourapp.onrender.com` URL.

### Path B — Keep SQLite, accept the tradeoffs (Railway, Fly.io, PythonAnywhere)

If you don't want to migrate to Postgres yet, some hosts (Railway, Fly.io) let you attach a **persistent volume** so SQLite's file survives redeploys — check their docs for "persistent disk" or "volumes" and mount it at `/instance`. PythonAnywhere's free tier also keeps files between deploys since there's no redeploy step — you just edit and reload. This is the fastest path to "live" but doesn't scale past one server instance.

### Either way, before going live:

- Set a real `SECRET_KEY` via environment variable — never commit the dev default in `config.py`.
- Set `GEMINI_API_KEY` as an environment variable on your host (never in code or git).
- Consider rate-limiting `/assistant/chat` (e.g. with `Flask-Limiter`) so a single user can't run up your API bill.
- The AI assistant, OAuth buttons, and OTP flow are still demo-scoped (see "What's next" below) — fine for a personal or portfolio deploy, not yet for public signups.

## Latest fixes (this update)

- **AI Assistant chat widget** — a floating 💬 button on every page opens a
  chat panel that can answer questions about your actual expenses, budgets,
  and loans (it's given a live snapshot of your data as context) and explain
  how to use any feature. Uses Google's Gemini API (**free tier, no credit
  card required** — get a key at aistudio.google.com/apikey). Needs a
  `GEMINI_API_KEY` (see `.env.example`) — without one, it shows a clear
  setup message instead of failing silently. Conversation history is saved
  per-user. *Testing note:* the request-building, response parsing, and
  error-handling code paths are all verified against the real SDK, but the
  sandbox this was built in couldn't reach Gemini's API domain to complete
  a full live round-trip — worth trying a real conversation once you add
  your key.
- **`.env` files now actually work** — `python-dotenv` had been listed as a
  dependency since Phase 1 but was never actually invoked, so a `.env` file
  silently did nothing. Fixed and added `.env.example`.
- **Search was truncating categories** — a shared 5-result limit across all
  search types cut off categories once a user had more than 5. Categories
  now get their own higher limit since there are rarely more than a couple
  dozen per user.
- **Theme toggle icon didn't change** — clicking 🌙/☀️ correctly switched the
  theme but the icon itself never updated to reflect the new state. Fixed.
- **Floating background** — decorative ₹ $ 💰 🪙 📈 symbols drift and slowly
  rotate behind the UI, with a subtle parallax effect that follows the
  cursor. Purely decorative (low opacity, `pointer-events: none`, respects
  `prefers-reduced-motion`).
- **3D page transitions** — pages tilt in on load and tilt away on internal
  navigation. Built with safeguards: navigation is scheduled *before* the
  animation runs (so a failed animation never blocks navigating), and a
  `pageshow` listener clears any stuck exit-animation state if the browser
  restores a page from its back/forward cache.
- **Lavender line-item fields** — the invoice builder's item pickers now use
  a distinct lavender tint instead of the generic neutral input styling.

## UI fixes and design pass (previous update)

- Fixed a dark-mode contrast bug where category/payment-mode selectors had
  unreadable white-on-white text; added theme-aware surface tokens.
- Fixed the Dashboard's "Budget Remaining" card, which ignored the overall
  budget set on the Budgets page.
- Fixed OCR-scanned expenses silently failing to save (a hidden `required`
  radio input was blocking submission with no visible error).
- Moved navigation to a left sidebar (collapses to an off-canvas drawer on
  mobile); dropdown option contrast; real Google/Apple icons; theme-aware
  chart text; orbiting wheel sectors with upright labels.

## What's next (not yet built)

1. Reports export (PDF / Excel / CSV) across date ranges
2. Real OTP delivery (SMS provider) and OAuth (Google/Apple sign-in)
3. Full settings page (currency, backup/restore, delete account)
4. Rate-limiting on the AI assistant endpoint before any public deploy

## Project structure

```
expense-tracker/
  app.py                 # app factory + entry point
  config.py               # loads .env, reads SECRET_KEY / GEMINI_API_KEY etc.
  extensions.py          # db, login_manager
  models.py              # User, Category, Expense, Income, ChatMessage, ...
  .env.example            # copy to .env and fill in your own values
  routes/
    auth.py               # register/login/logout
    main.py               # landing, dashboard, JSON APIs, global search
    expense.py             # expense CRUD
    income.py               # income CRUD
    category.py              # category CRUD (used by the wheel)
    scanner.py                # OCR bill scan endpoint
    budget.py                  # budgets + alerts
    analytics.py                 # chart data endpoints
    loan.py                        # loans/EMI CRUD + amortization + alerts
    business.py                      # products/inventory CRUD + alerts
    client.py                          # client CRUD
    invoice.py                           # invoice builder, PDF, QR, payments
    assistant.py                           # AI assistant chat endpoints
  utils/
    ocr.py                 # Tesseract extraction + parsing heuristics
    migrate.py               # lightweight auto-migration
    finance.py                 # EMI formula + amortization schedule
    invoice_pdf.py               # reportlab PDF + QR generation
    assistant.py                   # financial-context system prompt + Gemini call
  templates/
  static/
    css/  (style, landing, auth, dashboard, wheel, budgets, charts, loans,
           sidebar, business)
    js/   (main, wheel, dashboard, scanner, budgets, charts, notifications,
           loans, sidebar, business, invoice-builder, search, assistant,
           float-bg, page-transitions)
  instance/               # SQLite database lives here
```
