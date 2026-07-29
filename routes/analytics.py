from datetime import date, timedelta
from calendar import month_abbr
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

from models import Category, Expense, Income

analytics_bp = Blueprint("analytics", __name__)


def _months_back(n):
    """Returns a list of (year, month) tuples for the last n months, oldest first."""
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


@analytics_bp.route("/analytics")
@login_required
def analytics_page():
    return render_template("analytics.html")


@analytics_bp.route("/api/charts/category-pie")
@login_required
def chart_category_pie():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    rows = [(c.name, c.color, c.spent_this_month()) for c in categories]
    rows = [r for r in rows if r[2] > 0]
    rows.sort(key=lambda r: r[2], reverse=True)
    return jsonify({
        "labels": [r[0] for r in rows],
        "colors": [r[1] for r in rows],
        "data": [round(r[2], 2) for r in rows],
    })


@analytics_bp.route("/api/charts/income-vs-expense")
@login_required
def chart_income_vs_expense():
    months = _months_back(6)
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    incomes = Income.query.filter_by(user_id=current_user.id).all()

    labels, income_vals, expense_vals = [], [], []
    for y, m in months:
        labels.append(f"{month_abbr[m]} '{str(y)[2:]}")
        income_vals.append(round(sum(i.amount for i in incomes if i.date.year == y and i.date.month == m), 2))
        expense_vals.append(round(sum(e.amount for e in expenses if e.date.year == y and e.date.month == m), 2))

    return jsonify({"labels": labels, "income": income_vals, "expense": expense_vals})


@analytics_bp.route("/api/charts/monthly-trend")
@login_required
def chart_monthly_trend():
    months = _months_back(6)
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    labels, data = [], []
    for y, m in months:
        labels.append(f"{month_abbr[m]} '{str(y)[2:]}")
        data.append(round(sum(e.amount for e in expenses if e.date.year == y and e.date.month == m), 2))
    return jsonify({"labels": labels, "data": data})


@analytics_bp.route("/api/charts/weekly-trend")
@login_required
def chart_weekly_trend():
    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    labels = [d.strftime("%a") for d in days]
    data = [round(sum(e.amount for e in expenses if e.date == d), 2) for d in days]
    return jsonify({"labels": labels, "data": data})


@analytics_bp.route("/api/charts/payment-mode")
@login_required
def chart_payment_mode():
    today = date.today()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    month_expenses = [e for e in expenses if e.date.year == today.year and e.date.month == today.month]

    totals = {}
    for e in month_expenses:
        totals[e.payment_mode] = totals.get(e.payment_mode, 0) + e.amount

    palette = {"Cash": "#2FB77E", "UPI": "#B57EDC", "Debit Card": "#7C5CBF",
               "Credit Card": "#E0A64A", "Bank Transfer": "#5B8DEF"}
    labels = list(totals.keys())
    return jsonify({
        "labels": labels,
        "data": [round(v, 2) for v in totals.values()],
        "colors": [palette.get(l, "#B57EDC") for l in labels],
    })
