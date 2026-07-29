from datetime import datetime, date as date_cls
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Income

income_bp = Blueprint("income", __name__, url_prefix="/income")

SOURCES = ["Salary", "Business", "Freelancing", "Investments", "Others"]


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date_cls.today()


@income_bp.route("/")
@login_required
def list_income():
    incomes = Income.query.filter_by(user_id=current_user.id).order_by(Income.date.desc()).all()
    return render_template("income.html", incomes=incomes, sources=SOURCES)


@income_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_income():
    if request.method == "POST":
        income = Income(
            user_id=current_user.id,
            source=request.form.get("source", "Others"),
            name=request.form.get("name", "").strip() or "Income",
            amount=float(request.form.get("amount") or 0),
            date=_parse_date(request.form.get("date")),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(income)
        db.session.commit()
        flash(f"Added ₹{income.amount:,.2f} income from {income.source}.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("add_income.html", sources=SOURCES)


@income_bp.route("/<int:income_id>/edit", methods=["GET", "POST"])
@login_required
def edit_income(income_id):
    income = Income.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        income.source = request.form.get("source", income.source)
        income.name = request.form.get("name", "").strip() or income.name
        income.amount = float(request.form.get("amount") or income.amount)
        income.date = _parse_date(request.form.get("date"))
        income.notes = request.form.get("notes", "").strip()
        db.session.commit()
        flash("Income updated.", "success")
        return redirect(url_for("income.list_income"))

    return render_template("add_income.html", sources=SOURCES, income=income)


@income_bp.route("/<int:income_id>/delete", methods=["POST"])
@login_required
def delete_income(income_id):
    income = Income.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()
    db.session.delete(income)
    db.session.commit()
    flash("Income entry deleted.", "info")
    return redirect(request.referrer or url_for("income.list_income"))
