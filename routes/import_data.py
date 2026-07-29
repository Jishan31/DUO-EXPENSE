import os
import uuid
from datetime import date as date_cls

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from extensions import db
from models import Expense, Category, ImportBatch
from utils.import_csv import (read_csv_rows, guess_mapping, parse_amount,
                               parse_date_value, suggest_category_for_text)

import_bp = Blueprint("import_data", __name__, url_prefix="/imports")

PREVIEW_ROW_COUNT = 8


def _tmp_dir():
    path = os.path.join(current_app.instance_path, "tmp_imports")
    os.makedirs(path, exist_ok=True)
    return path


@import_bp.route("/")
@login_required
def imports_page():
    batches = ImportBatch.query.filter_by(user_id=current_user.id).order_by(ImportBatch.uploaded_at.desc()).all()
    return render_template("imports.html", batches=batches)


@import_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("dataset")
        if not file or file.filename == "":
            flash("Choose a CSV file to upload.", "error")
            return render_template("import_upload.html")
        if not file.filename.lower().endswith(".csv"):
            flash("Only CSV files are supported right now — export your data as CSV and try again.", "error")
            return render_template("import_upload.html")

        token = f"{current_user.id}_{uuid.uuid4().hex[:12]}.csv"
        path = os.path.join(_tmp_dir(), token)
        file.save(path)

        try:
            headers, rows = read_csv_rows(path)
        except Exception as e:
            os.remove(path)
            flash(f"Couldn't read that file — make sure it's a valid CSV. ({e})", "error")
            return render_template("import_upload.html")

        if not headers or not rows:
            os.remove(path)
            flash("That file doesn't seem to have any data rows.", "error")
            return render_template("import_upload.html")

        mapping = guess_mapping(headers)
        categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()

        return render_template(
            "import_mapping.html", token=token, headers=headers, mapping=mapping,
            preview_rows=rows[:PREVIEW_ROW_COUNT], total_rows=len(rows),
            original_filename=file.filename, categories=categories,
        )

    return render_template("import_upload.html")


@import_bp.route("/confirm", methods=["POST"])
@login_required
def confirm():
    token = request.form.get("token", "")
    path = os.path.join(_tmp_dir(), token)

    if not token or not token.startswith(f"{current_user.id}_") or not os.path.isfile(path):
        flash("That upload has expired — please upload the file again.", "error")
        return redirect(url_for("import_data.upload"))

    date_col = request.form.get("date_col") or None
    amount_col = request.form.get("amount_col") or None
    desc_col = request.form.get("desc_col") or None
    category_col = request.form.get("category_col") or None
    default_category_id = request.form.get("default_category_id", type=int)
    batch_name = request.form.get("batch_name", "").strip()

    categories = Category.query.filter_by(user_id=current_user.id).all()
    if not categories:
        os.remove(path)
        flash("Add at least one category before importing expenses.", "error")
        return redirect(url_for("main.dashboard"))

    default_category = next((c for c in categories if c.id == default_category_id), None)
    if not default_category:
        default_category = next((c for c in categories if c.name.lower() == "others"), categories[0])

    if not amount_col or not desc_col:
        os.remove(path)
        flash("An Amount column and a Description column are required.", "error")
        return redirect(url_for("import_data.upload"))

    try:
        headers, rows = read_csv_rows(path)
    except Exception:
        flash("Couldn't re-read the uploaded file — please try uploading again.", "error")
        return redirect(url_for("import_data.upload"))

    batch = ImportBatch(user_id=current_user.id, filename=batch_name or token)
    db.session.add(batch)
    db.session.flush()

    name_map = {c.name.lower(): c for c in categories}
    imported, skipped, total = 0, 0, 0.0

    for row in rows:
        raw_amount = row.get(amount_col, "")
        raw_desc = (row.get(desc_col, "") or "").strip()
        raw_date = row.get(date_col, "") if date_col else ""

        amount = parse_amount(raw_amount)
        if amount is None or not raw_desc:
            skipped += 1
            continue

        amount = abs(amount)
        expense_date = parse_date_value(raw_date) or date_cls.today()

        category = None
        if category_col:
            category = name_map.get((row.get(category_col) or "").strip().lower())
        if not category:
            category = suggest_category_for_text(raw_desc, categories)
        if not category:
            category = default_category

        db.session.add(Expense(
            user_id=current_user.id,
            category_id=category.id,
            name=raw_desc[:120],
            amount=amount,
            date=expense_date,
            payment_mode="Bank Transfer",
            description=f"Imported from {batch_name or 'uploaded dataset'}",
            import_batch_id=batch.id,
        ))
        imported += 1
        total += amount

    batch.row_count = imported
    batch.skipped_count = skipped
    batch.total_amount = round(total, 2)
    db.session.commit()
    os.remove(path)

    msg = f"Imported {imported} expense{'s' if imported != 1 else ''} totalling ₹{total:,.2f}."
    if skipped:
        msg += f" Skipped {skipped} row(s) that couldn't be parsed."
    flash(msg, "success" if imported else "error")

    return redirect(url_for("import_data.batch_report", batch_id=batch.id))


@import_bp.route("/<int:batch_id>")
@login_required
def batch_report(batch_id):
    batch = ImportBatch.query.filter_by(id=batch_id, user_id=current_user.id).first_or_404()
    expenses = Expense.query.filter_by(import_batch_id=batch.id).order_by(Expense.date).all()

    by_category = {}
    for e in expenses:
        entry = by_category.setdefault(e.category.name, {"amount": 0.0, "color": e.category.color})
        entry["amount"] += e.amount
    top_categories = sorted(by_category.items(), key=lambda kv: kv[1]["amount"], reverse=True)

    date_range = (min(e.date for e in expenses), max(e.date for e in expenses)) if expenses else None

    return render_template("import_report.html", batch=batch, expenses=expenses,
                            top_categories=top_categories, date_range=date_range)


@import_bp.route("/<int:batch_id>/delete", methods=["POST"])
@login_required
def delete_batch(batch_id):
    batch = ImportBatch.query.filter_by(id=batch_id, user_id=current_user.id).first_or_404()
    also_delete_expenses = request.form.get("also_delete_expenses") == "1"

    if also_delete_expenses:
        Expense.query.filter_by(import_batch_id=batch.id).delete()
    else:
        Expense.query.filter_by(import_batch_id=batch.id).update({"import_batch_id": None})

    db.session.delete(batch)
    db.session.commit()
    flash("Import removed." + (" Its expenses were deleted too." if also_delete_expenses else " Its expenses were kept as regular expenses."), "info")
    return redirect(url_for("import_data.imports_page"))
