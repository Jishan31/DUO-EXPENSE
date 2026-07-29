from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user, login_user

from extensions import db
from models import User, FilingProject, Bid, Expense, Income
from utils.validators import validate_email_format, is_password_strong_enough

auditor_bp = Blueprint("auditor", __name__, url_prefix="/auditor")


def _require_auditor():
    return current_user.is_authenticated and current_user.role == "auditor"


@auditor_bp.route("/login", methods=["GET", "POST"])
def auditor_login():
    if current_user.is_authenticated:
        return redirect(url_for("auditor.auditor_dashboard") if current_user.role == "auditor" else url_for("main.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter(
            (db.func.lower(User.email) == identifier) | (db.func.lower(User.username) == identifier)
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid username/email or password.", "error")
        elif user.role != "auditor":
            flash("That account isn't registered as an auditor. Use the regular login instead, "
                  "or create a separate auditor account below.", "error")
        else:
            login_user(user)
            return redirect(url_for("auditor.auditor_dashboard"))

    return render_template("auditor_login.html")


@auditor_bp.route("/register", methods=["GET", "POST"])
def auditor_register():
    if current_user.is_authenticated:
        return redirect(url_for("auditor.auditor_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        qualification = request.form.get("qualification", "").strip()
        bio = request.form.get("bio", "").strip()

        if not username or not email or not password:
            flash("Please fill in all required fields.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif not is_password_strong_enough(password):
            flash("Password is too weak — use at least 8 characters with a mix of uppercase, "
                  "lowercase, and a number or symbol.", "error")
        elif not validate_email_format(email)[0]:
            flash(f"Email address: {validate_email_format(email)[1]}", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            email = validate_email_format(email)[1]
            auditor = User(username=username, email=email, role="auditor",
                            auditor_qualification=qualification, auditor_bio=bio)
            auditor.set_password(password)
            db.session.add(auditor)
            db.session.commit()
            login_user(auditor)
            flash("Welcome! Your auditor profile is live — browse open filing projects below.", "success")
            return redirect(url_for("auditor.auditor_dashboard"))

    return render_template("auditor_register.html")


@auditor_bp.route("/account", methods=["GET", "POST"])
@login_required
def auditor_account():
    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            new_username = request.form.get("username", "").strip()
            if not new_username or len(new_username) < 3:
                flash("Username must be at least 3 characters.", "error")
            elif User.query.filter(User.username == new_username, User.id != current_user.id).first():
                flash("That username is already taken.", "error")
            else:
                current_user.username = new_username
                current_user.auditor_qualification = request.form.get("qualification", "").strip()
                current_user.auditor_bio = request.form.get("bio", "").strip()
                db.session.commit()
                flash("Profile updated.", "success")

        elif action == "update_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "error")
            elif not is_password_strong_enough(new_password):
                flash("New password is too weak — use at least 8 characters with a mix of uppercase, lowercase, and a number or symbol.", "error")
            elif new_password != confirm:
                flash("New passwords don't match.", "error")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password updated.", "success")

        return redirect(url_for("auditor.auditor_account"))

    return render_template("auditor_account.html")


@auditor_bp.route("/dashboard")
@login_required
def auditor_dashboard():
    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    open_projects = (FilingProject.query.filter_by(status="open")
                      .order_by(FilingProject.bid_deadline).all())
    my_bids = (Bid.query.filter_by(auditor_id=current_user.id)
               .order_by(Bid.created_at.desc()).all())
    won_projects = [b.project for b in my_bids if b.status == "won"]

    return render_template("auditor_dashboard.html", open_projects=open_projects,
                            my_bids=my_bids, won_projects=won_projects, today=date.today())


@auditor_bp.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    project = FilingProject.query.get_or_404(project_id)
    my_bid = Bid.query.filter_by(filing_project_id=project.id, auditor_id=current_user.id).first()
    lowest = project.lowest_bid()
    return render_template("auditor_project_detail.html", project=project, my_bid=my_bid,
                            lowest=lowest, today=date.today())


@auditor_bp.route("/projects/<int:project_id>/bid", methods=["POST"])
@login_required
def submit_bid(project_id):
    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    project = FilingProject.query.get_or_404(project_id)
    if project.status != "open" or project.bid_deadline_passed():
        flash("This project is no longer accepting bids.", "error")
        return redirect(url_for("auditor.project_detail", project_id=project.id))

    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash("Enter a valid bid amount.", "error")
        return redirect(url_for("auditor.project_detail", project_id=project.id))

    existing = Bid.query.filter_by(filing_project_id=project.id, auditor_id=current_user.id).first()
    if existing:
        existing.amount = amount
        existing.message = request.form.get("message", "").strip()
        existing.status = "pending"
        flash("Your bid has been updated.", "success")
    else:
        db.session.add(Bid(filing_project_id=project.id, auditor_id=current_user.id,
                            amount=amount, message=request.form.get("message", "").strip()))
        flash("Bid submitted — lowest bid wins when the deadline passes.", "success")
    db.session.commit()
    return redirect(url_for("auditor.project_detail", project_id=project.id))


@auditor_bp.route("/bids/<int:bid_id>/withdraw", methods=["POST"])
@login_required
def withdraw_bid(bid_id):
    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    bid = Bid.query.filter_by(id=bid_id, auditor_id=current_user.id).first_or_404()
    if bid.status == "pending":
        bid.status = "withdrawn"
        db.session.commit()
        flash("Bid withdrawn.", "info")
    return redirect(url_for("auditor.auditor_dashboard"))


@auditor_bp.route("/projects/<int:project_id>/report.pdf")
@login_required
def download_client_report(project_id):
    from flask import send_file
    from utils.expense_report import compute_expense_report, generate_expense_report_pdf

    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    project = FilingProject.query.get_or_404(project_id)
    if project.status not in ("awarded", "completed") or not project.winning_bid or project.winning_bid.auditor_id != current_user.id:
        flash("You don't have access to this project's data.", "error")
        return redirect(url_for("auditor.auditor_dashboard"))

    client = project.owner
    report = compute_expense_report(client, project.period_start, project.period_end)
    pdf = generate_expense_report_pdf(client, project.period_start, project.period_end, report)
    filename = f"Expense-Report-{project.period_start.isoformat()}-to-{project.period_end.isoformat()}.pdf"
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@auditor_bp.route("/projects/<int:project_id>/data")
@login_required
def project_data(project_id):
    """Read-only view of the client's expense/income data for the awarded period —
    only reachable by the auditor who actually won this specific project."""
    if not _require_auditor():
        return redirect(url_for("main.dashboard"))

    project = FilingProject.query.get_or_404(project_id)
    if project.status != "awarded" or not project.winning_bid or project.winning_bid.auditor_id != current_user.id:
        flash("You don't have access to this project's data.", "error")
        return redirect(url_for("auditor.auditor_dashboard"))

    expenses = (Expense.query.filter(Expense.user_id == project.user_id,
                                      Expense.date >= project.period_start,
                                      Expense.date <= project.period_end)
                .order_by(Expense.date).all())
    incomes = (Income.query.filter(Income.user_id == project.user_id,
                                    Income.date >= project.period_start,
                                    Income.date <= project.period_end)
               .order_by(Income.date).all())

    return render_template("auditor_project_data.html", project=project, expenses=expenses, incomes=incomes)
