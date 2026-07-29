from datetime import datetime, date as date_cls, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Loan, LoanPayment
from utils.finance import calculate_emi, build_amortization_schedule

loan_bp = Blueprint("loan", __name__, url_prefix="/loans")

LOAN_TYPES = ["Home", "Vehicle", "Personal", "Education", "Business", "Credit Card", "Other"]
PAYMENT_MODES = ["Cash", "UPI", "Debit Card", "Credit Card", "Bank Transfer", "Auto-debit"]


def _parse_date(value, fallback=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback or date_cls.today()


@loan_bp.route("/")
@login_required
def loans_page():
    loans = Loan.query.filter_by(user_id=current_user.id).order_by(Loan.status, Loan.created_at.desc()).all()
    loan_cards = []
    for l in loans:
        next_due = l.next_due()
        loan_cards.append({
            "loan": l,
            "percent_paid": l.percent_paid(),
            "principal_remaining": l.principal_remaining(),
            "next_due": next_due,
            "days_until_due": (next_due.due_date - date_cls.today()).days if next_due else None,
        })
    total_outstanding = sum(l.principal_remaining() for l in loans if l.status == "active")
    total_monthly_emi = sum(l.monthly_emi for l in loans if l.status == "active")
    return render_template("loans.html", loan_cards=loan_cards, loan_types=LOAN_TYPES,
                            total_outstanding=total_outstanding, total_monthly_emi=total_monthly_emi)


@loan_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_loan():
    if request.method == "POST":
        try:
            principal = float(request.form.get("principal_amount") or 0)
            rate = float(request.form.get("interest_rate") or 0)
            tenure = int(request.form.get("tenure_months") or 0)
        except ValueError:
            flash("Please enter valid numbers for amount, rate, and tenure.", "error")
            return render_template("add_loan.html", loan_types=LOAN_TYPES)

        if principal <= 0 or tenure <= 0:
            flash("Loan amount and tenure must be greater than zero.", "error")
            return render_template("add_loan.html", loan_types=LOAN_TYPES)

        start_date = _parse_date(request.form.get("start_date"))
        emi = calculate_emi(principal, rate, tenure)

        loan = Loan(
            user_id=current_user.id,
            name=request.form.get("name", "").strip() or "Untitled Loan",
            loan_type=request.form.get("loan_type", "Personal"),
            lender=request.form.get("lender", "").strip(),
            principal_amount=principal,
            interest_rate=rate,
            tenure_months=tenure,
            start_date=start_date,
            monthly_emi=emi,
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(loan)
        db.session.flush()

        schedule = build_amortization_schedule(principal, rate, tenure, start_date, emi=emi)
        for row in schedule:
            db.session.add(LoanPayment(
                loan_id=loan.id,
                installment_no=row["installment_no"],
                due_date=row["due_date"],
                amount=row["amount"],
                principal_component=row["principal_component"],
                interest_component=row["interest_component"],
            ))

        db.session.commit()
        flash(f"{loan.name} added — EMI of ₹{emi:,.2f}/month scheduled for {tenure} months.", "success")
        return redirect(url_for("loan.loan_detail", loan_id=loan.id))

    return render_template("add_loan.html", loan_types=LOAN_TYPES)


@loan_bp.route("/<int:loan_id>")
@login_required
def loan_detail(loan_id):
    loan = Loan.query.filter_by(id=loan_id, user_id=current_user.id).first_or_404()
    upcoming = [p for p in loan.payments if not p.is_paid]
    paid = [p for p in loan.payments if p.is_paid]
    return render_template("loan_detail.html", loan=loan, upcoming=upcoming, paid=paid,
                            payment_modes=PAYMENT_MODES, today=date_cls.today())


@loan_bp.route("/<int:loan_id>/edit", methods=["GET", "POST"])
@login_required
def edit_loan(loan_id):
    loan = Loan.query.filter_by(id=loan_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        loan.name = request.form.get("name", "").strip() or loan.name
        loan.loan_type = request.form.get("loan_type", loan.loan_type)
        loan.lender = request.form.get("lender", "").strip()
        loan.notes = request.form.get("notes", "").strip()
        loan.status = request.form.get("status", loan.status)
        db.session.commit()
        flash("Loan details updated.", "success")
        return redirect(url_for("loan.loan_detail", loan_id=loan.id))

    return render_template("edit_loan.html", loan=loan, loan_types=LOAN_TYPES)


@loan_bp.route("/<int:loan_id>/delete", methods=["POST"])
@login_required
def delete_loan(loan_id):
    loan = Loan.query.filter_by(id=loan_id, user_id=current_user.id).first_or_404()
    db.session.delete(loan)
    db.session.commit()
    flash("Loan deleted.", "info")
    return redirect(url_for("loan.loans_page"))


@loan_bp.route("/<int:loan_id>/payments/<int:payment_id>/mark-paid", methods=["POST"])
@login_required
def mark_paid(loan_id, payment_id):
    loan = Loan.query.filter_by(id=loan_id, user_id=current_user.id).first_or_404()
    payment = LoanPayment.query.filter_by(id=payment_id, loan_id=loan.id).first_or_404()

    payment.is_paid = True
    payment.paid_date = _parse_date(request.form.get("paid_date"), fallback=date_cls.today())
    payment.payment_mode = request.form.get("payment_mode", "UPI")

    if all(p.is_paid for p in loan.payments):
        loan.status = "closed"

    db.session.commit()
    flash(f"Installment #{payment.installment_no} marked as paid.", "success")
    return redirect(url_for("loan.loan_detail", loan_id=loan.id))


@loan_bp.route("/<int:loan_id>/payments/<int:payment_id>/unmark", methods=["POST"])
@login_required
def unmark_paid(loan_id, payment_id):
    loan = Loan.query.filter_by(id=loan_id, user_id=current_user.id).first_or_404()
    payment = LoanPayment.query.filter_by(id=payment_id, loan_id=loan.id).first_or_404()
    payment.is_paid = False
    payment.paid_date = None
    if loan.status == "closed":
        loan.status = "active"
    db.session.commit()
    flash(f"Installment #{payment.installment_no} marked as unpaid.", "info")
    return redirect(url_for("loan.loan_detail", loan_id=loan.id))


@loan_bp.route("/api/alerts")
@login_required
def loan_alerts():
    """Due-soon (within 7 days) and overdue installments, for the notification bell."""
    loans = Loan.query.filter_by(user_id=current_user.id, status="active").all()
    today = date_cls.today()
    alerts = []
    for l in loans:
        next_due = l.next_due()
        if not next_due:
            continue
        days = (next_due.due_date - today).days
        if days < 0:
            alerts.append({"type": "loan_overdue", "color": "#E9607A",
                            "message": f"{l.name} EMI of ₹{next_due.amount:,.0f} is overdue."})
        elif days <= 7:
            when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            alerts.append({"type": "loan_due_soon", "color": "#E0A64A",
                            "message": f"{l.name} EMI of ₹{next_due.amount:,.0f} is due {when}."})
    return jsonify({"alerts": alerts})
