from datetime import datetime, date as date_cls
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Expense, Category

expense_bp = Blueprint("expense", __name__, url_prefix="/expenses")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date_cls.today()


def _parse_time(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


@expense_bp.route("/")
@login_required
def list_expenses():
    expenses = (Expense.query.filter_by(user_id=current_user.id)
                .order_by(Expense.date.desc(), Expense.created_at.desc()).all())
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()
    return render_template("expenses.html", expenses=expenses, categories=categories)


@expense_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()
    preselected_category = request.args.get("category_id", type=int)

    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        category = Category.query.filter_by(id=category_id, user_id=current_user.id).first()

        if not category:
            flash("Please choose a valid category.", "error")
            return render_template("add_expense.html", categories=categories, preselected_category=category_id)

        expense = Expense(
            user_id=current_user.id,
            category_id=category.id,
            name=request.form.get("name", "").strip() or "Untitled expense",
            amount=float(request.form.get("amount") or 0),
            date=_parse_date(request.form.get("date")),
            time=_parse_time(request.form.get("time")),
            payment_mode=request.form.get("payment_mode", "UPI"),
            description=request.form.get("description", "").strip(),
            location=request.form.get("location", "").strip(),
            tags=request.form.get("tags", "").strip(),
            merchant=request.form.get("merchant", "").strip(),
            gst_amount=float(request.form.get("gst_amount") or 0),
            receipt_path=request.form.get("receipt_path", "").strip(),
        )
        db.session.add(expense)
        db.session.commit()
        flash(f"Added ₹{expense.amount:,.2f} to {category.name}.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("add_expense.html", categories=categories, preselected_category=preselected_category)


@expense_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()

    if request.method == "POST":
        expense.category_id = request.form.get("category_id", type=int)
        expense.name = request.form.get("name", "").strip() or expense.name
        expense.amount = float(request.form.get("amount") or expense.amount)
        expense.date = _parse_date(request.form.get("date"))
        expense.time = _parse_time(request.form.get("time"))
        expense.payment_mode = request.form.get("payment_mode", expense.payment_mode)
        expense.description = request.form.get("description", "").strip()
        expense.location = request.form.get("location", "").strip()
        expense.tags = request.form.get("tags", "").strip()
        expense.merchant = request.form.get("merchant", "").strip()
        expense.gst_amount = float(request.form.get("gst_amount") or 0)
        new_receipt = request.form.get("receipt_path", "").strip()
        if new_receipt:
            expense.receipt_path = new_receipt
        db.session.commit()
        flash("Expense updated.", "success")
        return redirect(url_for("expense.list_expenses"))

    return render_template("add_expense.html", categories=categories, expense=expense, preselected_category=expense.category_id)


@expense_bp.route("/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted.", "info")
    return redirect(request.referrer or url_for("expense.list_expenses"))
