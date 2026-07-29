from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Client

client_bp = Blueprint("client", __name__, url_prefix="/clients")


@client_bp.route("/")
@login_required
def clients_page():
    clients = Client.query.filter_by(user_id=current_user.id).order_by(Client.created_at.desc()).all()
    return render_template("clients.html", clients=clients)


@client_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_client():
    if request.method == "POST":
        client = Client(
            user_id=current_user.id,
            name=request.form.get("name", "").strip() or "Untitled Client",
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(client)
        db.session.commit()
        flash(f"{client.name} added to clients.", "success")

        next_action = request.form.get("next_action")
        if next_action == "invoice":
            return redirect(url_for("invoice.add_invoice", client_id=client.id))
        return redirect(url_for("client.clients_page"))

    return render_template("add_client.html")


@client_bp.route("/<int:client_id>")
@login_required
def client_detail(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first_or_404()
    return render_template("client_detail.html", client=client)


@client_bp.route("/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        client.name = request.form.get("name", "").strip() or client.name
        client.phone = request.form.get("phone", "").strip()
        client.email = request.form.get("email", "").strip()
        client.notes = request.form.get("notes", "").strip()
        db.session.commit()
        flash("Client updated.", "success")
        return redirect(url_for("client.client_detail", client_id=client.id))

    return render_template("add_client.html", client=client)


@client_bp.route("/<int:client_id>/delete", methods=["POST"])
@login_required
def delete_client(client_id):
    client = Client.query.filter_by(id=client_id, user_id=current_user.id).first_or_404()
    db.session.delete(client)
    db.session.commit()
    flash("Client and their invoice history deleted.", "info")
    return redirect(url_for("client.clients_page"))
