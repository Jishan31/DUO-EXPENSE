from datetime import date
from flask import Blueprint, render_template, jsonify, request, url_for, redirect, flash
from flask_login import login_required, current_user

from extensions import db
from models import Category, Expense, Income, ContactMessage

main_bp = Blueprint("main", __name__)


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please fill in your name, email, and message.", "error")
        else:
            db.session.add(ContactMessage(
                user_id=current_user.id if current_user.is_authenticated else None,
                name=name, email=email, phone=phone, message=message,
            ))
            db.session.commit()
            flash("Thanks — we've got your message and will get back to you soon.", "success")
            if current_user.is_authenticated and current_user.role == "auditor":
                return redirect(url_for("auditor.auditor_dashboard"))
            return redirect(url_for("main.dashboard") if current_user.is_authenticated else url_for("main.landing"))

    prefill_name = current_user.username if current_user.is_authenticated else ""
    prefill_email = current_user.email if current_user.is_authenticated else ""
    return render_template("contact.html", prefill_name=prefill_name, prefill_email=prefill_email)


@main_bp.route("/")
def landing():
    return render_template("landing.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()
    return render_template("dashboard.html", categories=categories)


@main_bp.route("/api/wheel-data")
@login_required
def wheel_data():
    """Returns each category with its current-month spend, sized for the wheel."""
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()
    data = []
    for c in categories:
        data.append({
            "id": c.id,
            "name": c.name,
            "icon": c.icon,
            "color": c.color,
            "spent": round(c.spent_this_month(), 2),
            "budget": c.monthly_budget,
        })
    return jsonify(data)


@main_bp.route("/api/summary")
@login_required
def summary():
    today = date.today()

    incomes = Income.query.filter_by(user_id=current_user.id).all()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    month_income = sum(i.amount for i in incomes if i.date.year == today.year and i.date.month == today.month)
    month_expense = sum(e.amount for e in expenses if e.date.year == today.year and e.date.month == today.month)

    # Prefer the overall monthly budget (set on the Budgets page); fall back to
    # the sum of per-category budgets if no overall figure has been set.
    category_budget_sum = sum(c.monthly_budget for c in Category.query.filter_by(user_id=current_user.id).all())
    total_budget = current_user.monthly_budget_total or category_budget_sum

    balance = month_income - month_expense
    savings = max(balance, 0)
    budget_remaining = max(total_budget - month_expense, 0) if total_budget else 0

    return jsonify({
        "income": round(month_income, 2),
        "expense": round(month_expense, 2),
        "balance": round(balance, 2),
        "budget_remaining": round(budget_remaining, 2),
        "total_budget": round(total_budget, 2),
        "savings": round(savings, 2),
    })


@main_bp.route("/api/search")
@login_required
def global_search():
    from models import Category, Income, Loan
    from models import Client, Product, Invoice

    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({})

    like = f"%{q}%"
    uid = current_user.id
    LIMIT = 5
    CATEGORY_LIMIT = 25  # a user rarely has more than a couple dozen categories — show them all, don't truncate

    results = {}

    expenses = (Expense.query.filter_by(user_id=uid)
                .filter(db.or_(Expense.name.ilike(like), Expense.merchant.ilike(like),
                                Expense.description.ilike(like), Expense.tags.ilike(like)))
                .order_by(Expense.date.desc()).limit(LIMIT).all())
    if expenses:
        results["Expenses"] = [{"label": e.name, "subtitle": f"₹{e.amount:,.0f} · {e.date.strftime('%b %d')}",
                                 "url": url_for("expense.edit_expense", expense_id=e.id)} for e in expenses]

    incomes = (Income.query.filter_by(user_id=uid)
               .filter(db.or_(Income.name.ilike(like), Income.source.ilike(like)))
               .order_by(Income.date.desc()).limit(LIMIT).all())
    if incomes:
        results["Income"] = [{"label": i.name, "subtitle": f"₹{i.amount:,.0f} · {i.source}",
                               "url": url_for("income.edit_income", income_id=i.id)} for i in incomes]

    categories = Category.query.filter_by(user_id=uid).filter(Category.name.ilike(like)).limit(CATEGORY_LIMIT).all()
    if categories:
        results["Categories"] = [{"label": c.name, "subtitle": "Category",
                                   "url": url_for("expense.add_expense", category_id=c.id)} for c in categories]

    clients = (Client.query.filter_by(user_id=uid)
               .filter(db.or_(Client.name.ilike(like), Client.email.ilike(like), Client.phone.ilike(like)))
               .limit(LIMIT).all())
    if clients:
        results["Clients"] = [{"label": c.name, "subtitle": c.phone or c.email or "Client",
                                "url": url_for("client.client_detail", client_id=c.id)} for c in clients]

    products = (Product.query.filter_by(user_id=uid)
                .filter(db.or_(Product.name.ilike(like), Product.sku.ilike(like)))
                .limit(LIMIT).all())
    if products:
        results["Products"] = [{"label": p.name, "subtitle": f"{p.quantity_available} in stock",
                                 "url": url_for("business.edit_product", product_id=p.id)} for p in products]

    loans = (Loan.query.filter_by(user_id=uid)
             .filter(db.or_(Loan.name.ilike(like), Loan.lender.ilike(like)))
             .limit(LIMIT).all())
    if loans:
        results["Loans & EMIs"] = [{"label": l.name, "subtitle": l.lender or "Loan",
                                     "url": url_for("loan.loan_detail", loan_id=l.id)} for l in loans]

    invoices = Invoice.query.filter_by(user_id=uid).filter(Invoice.invoice_number.ilike(like)).limit(LIMIT).all()
    if invoices:
        results["Invoices"] = [{"label": i.invoice_number, "subtitle": f"₹{i.total_amount:,.0f} · {i.status}",
                                 "url": url_for("invoice.invoice_detail", invoice_id=i.id)} for i in invoices]

    return jsonify(results)


@main_bp.route("/api/recent-transactions")
@login_required
def recent_transactions():
    expenses = (Expense.query.filter_by(user_id=current_user.id)
                .order_by(Expense.date.desc(), Expense.created_at.desc()).limit(6).all())
    data = [{
        "id": e.id,
        "name": e.name,
        "amount": e.amount,
        "date": e.date.strftime("%b %d, %Y"),
        "category": e.category.name,
        "color": e.category.color,
        "payment_mode": e.payment_mode,
    } for e in expenses]
    return jsonify(data)
