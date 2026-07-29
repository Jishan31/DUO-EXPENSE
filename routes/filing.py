from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import FilingProject, Bid

filing_bp = Blueprint("filing", __name__, url_prefix="/filing")


def _maybe_auto_award(project):
    """If bidding has closed and nobody's awarded it yet, auto-award the lowest bid.
    Runs lazily whenever a project is viewed, since this app has no background scheduler."""
    if project.status == "open" and project.bid_deadline_passed():
        lowest = project.lowest_bid()
        if lowest:
            for b in project.bids:
                b.status = "won" if b.id == lowest.id else "lost"
            project.winning_bid_id = lowest.id
            project.status = "awarded"
        else:
            project.status = "cancelled"  # nobody bid — nothing to award
        db.session.commit()


@filing_bp.route("/")
@login_required
def my_filing_projects():
    projects = (FilingProject.query.filter_by(user_id=current_user.id)
                .order_by(FilingProject.created_at.desc()).all())
    for p in projects:
        _maybe_auto_award(p)
    return render_template("filing_list.html", projects=projects, today=date.today())


@filing_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_filing_project():
    if request.method == "POST":
        try:
            period_start = date.fromisoformat(request.form.get("period_start", ""))
            period_end = date.fromisoformat(request.form.get("period_end", ""))
            bid_deadline = date.fromisoformat(request.form.get("bid_deadline", ""))
        except ValueError:
            flash("Please provide valid dates.", "error")
            return render_template("filing_new.html")

        title = request.form.get("title", "").strip()
        if not title:
            flash("Please give this filing project a title.", "error")
            return render_template("filing_new.html")
        if bid_deadline <= date.today():
            flash("Bid deadline needs to be a future date.", "error")
            return render_template("filing_new.html")
        if period_end < period_start:
            flash("The filing period's end date can't be before its start date.", "error")
            return render_template("filing_new.html")

        project = FilingProject(
            user_id=current_user.id, title=title,
            description=request.form.get("description", "").strip(),
            period_start=period_start, period_end=period_end, bid_deadline=bid_deadline,
        )
        db.session.add(project)
        db.session.commit()
        flash("Filing project posted — auditors can now bid on it.", "success")
        return redirect(url_for("filing.project_detail", project_id=project.id))

    return render_template("filing_new.html")


@filing_bp.route("/<int:project_id>")
@login_required
def project_detail(project_id):
    project = FilingProject.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    _maybe_auto_award(project)
    active_bids = sorted([b for b in project.bids if b.status in ("pending", "won", "lost")],
                          key=lambda b: b.amount)
    return render_template("filing_project_detail.html", project=project, bids=active_bids, today=date.today())


@filing_bp.route("/<int:project_id>/report.pdf")
@login_required
def download_report(project_id):
    from flask import send_file
    from utils.expense_report import compute_expense_report, generate_expense_report_pdf

    project = FilingProject.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    report = compute_expense_report(current_user, project.period_start, project.period_end)
    pdf = generate_expense_report_pdf(current_user, project.period_start, project.period_end, report)
    filename = f"Expense-Report-{project.period_start.isoformat()}-to-{project.period_end.isoformat()}.pdf"
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@filing_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_filing_project(project_id):
    project = FilingProject.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    if project.status != "open":
        flash("This project can no longer be edited — bidding has already closed.", "error")
        return redirect(url_for("filing.project_detail", project_id=project.id))

    if request.method == "POST":
        try:
            period_start = date.fromisoformat(request.form.get("period_start", ""))
            period_end = date.fromisoformat(request.form.get("period_end", ""))
            bid_deadline = date.fromisoformat(request.form.get("bid_deadline", ""))
        except ValueError:
            flash("Please provide valid dates.", "error")
            return render_template("filing_edit.html", project=project)

        title = request.form.get("title", "").strip()
        if not title:
            flash("Please give this filing project a title.", "error")
            return render_template("filing_edit.html", project=project)
        if bid_deadline <= date.today():
            flash("Bid deadline needs to be a future date.", "error")
            return render_template("filing_edit.html", project=project)
        if period_end < period_start:
            flash("The filing period's end date can't be before its start date.", "error")
            return render_template("filing_edit.html", project=project)

        project.title = title
        project.description = request.form.get("description", "").strip()
        project.period_start = period_start
        project.period_end = period_end
        project.bid_deadline = bid_deadline
        db.session.commit()
        flash("Filing project updated.", "success")
        return redirect(url_for("filing.project_detail", project_id=project.id))

    return render_template("filing_edit.html", project=project)


@filing_bp.route("/<int:project_id>/award/<int:bid_id>", methods=["POST"])
@login_required
def award_bid(project_id, bid_id):
    project = FilingProject.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    if project.status != "open":
        flash("This project has already been decided.", "error")
        return redirect(url_for("filing.project_detail", project_id=project.id))

    bid = Bid.query.filter_by(id=bid_id, filing_project_id=project.id).first_or_404()
    lowest = project.lowest_bid()
    if lowest and bid.id != lowest.id:
        flash("Only the current lowest bid can be awarded early — that's the whole point of the auction.", "error")
        return redirect(url_for("filing.project_detail", project_id=project.id))

    for b in project.bids:
        b.status = "won" if b.id == bid.id else "lost"
    project.winning_bid_id = bid.id
    project.status = "awarded"
    db.session.commit()
    flash(f"Awarded to {bid.auditor.username} for ₹{bid.amount:,.0f}.", "success")
    return redirect(url_for("filing.project_detail", project_id=project.id))


@filing_bp.route("/<int:project_id>/cancel", methods=["POST"])
@login_required
def cancel_project(project_id):
    project = FilingProject.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    if project.status == "open":
        project.status = "cancelled"
        for b in project.bids:
            if b.status == "pending":
                b.status = "withdrawn"
        db.session.commit()
        flash("Filing project cancelled.", "info")
    return redirect(url_for("filing.my_filing_projects"))


@filing_bp.route("/<int:project_id>/complete", methods=["POST"])
@login_required
def mark_complete(project_id):
    project = FilingProject.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
    if project.status == "awarded":
        project.status = "completed"
        db.session.commit()
        flash("Marked as completed. Thanks for using Duo Expense's auditor marketplace!", "success")
    return redirect(url_for("filing.project_detail", project_id=project.id))
