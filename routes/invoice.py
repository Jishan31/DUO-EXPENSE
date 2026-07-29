import json
from datetime import datetime, date as date_cls
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user

from extensions import db
from models import Invoice, InvoiceItem, Client, Product
from utils.invoice_pdf import generate_invoice_pdf, generate_qr_png_bytes

invoice_bp = Blueprint("invoice", __name__, url_prefix="/invoices")


def _parse_date(value, fallback=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


def _next_invoice_number():
    seq = Invoice.query.filter_by(user_id=current_user.id).count() + 1
    return f"INV-{date_cls.today().year}-{seq:04d}"


@invoice_bp.route("/")
@login_required
def invoices_page():
    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).all()
    total_billed = round(sum(i.total_amount for i in invoices if i.status != "draft"), 2)
    total_pending = round(sum(i.balance_due() for i in invoices if i.status not in ("draft", "cancelled")), 2)
    return render_template("invoices.html", invoices=invoices, total_billed=total_billed, total_pending=total_pending)


@invoice_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_invoice():
    clients = Client.query.filter_by(user_id=current_user.id).order_by(Client.name).all()
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    preselected_client = request.args.get("client_id", type=int)

    if request.method == "POST":
        client = Client.query.filter_by(id=request.form.get("client_id", type=int), user_id=current_user.id).first()
        if not client:
            flash("Please choose a client for this invoice.", "error")
            return render_template("add_invoice.html", clients=clients, products=products,
                                    preselected_client=preselected_client)

        try:
            raw_items = json.loads(request.form.get("items_json") or "[]")
        except json.JSONDecodeError:
            raw_items = []

        if not raw_items:
            flash("Add at least one line item to the invoice.", "error")
            return render_template("add_invoice.html", clients=clients, products=products,
                                    preselected_client=client.id)

        # Validate stock BEFORE creating anything, so a failed invoice never partially deducts stock
        stock_updates = []
        for raw in raw_items:
            if raw.get("product_id"):
                product = Product.query.filter_by(id=raw["product_id"], user_id=current_user.id).first()
                if not product:
                    continue
                qty = int(raw.get("quantity") or 0)
                if qty > product.quantity_available:
                    flash(f"Not enough stock for {product.name} — only {product.quantity_available} available.", "error")
                    return render_template("add_invoice.html", clients=clients, products=products,
                                            preselected_client=client.id)
                stock_updates.append((product, qty))

        try:
            discount_percent = float(request.form.get("discount_percent") or 0)
            gst_percent = float(request.form.get("gst_percent") or 0)
        except ValueError:
            discount_percent = gst_percent = 0

        invoice = Invoice(
            user_id=current_user.id,
            client_id=client.id,
            invoice_number=_next_invoice_number(),
            issue_date=date_cls.today(),
            due_date=_parse_date(request.form.get("due_date")),
            status="draft" if request.form.get("save_as_draft") else "unpaid",
            discount_percent=discount_percent,
            gst_percent=gst_percent,
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(invoice)
        db.session.flush()

        subtotal = 0.0
        for raw in raw_items:
            quantity = max(int(raw.get("quantity") or 1), 1)
            unit_price = float(raw.get("unit_price") or 0)
            line_total = round(quantity * unit_price, 2)
            subtotal += line_total
            db.session.add(InvoiceItem(
                invoice_id=invoice.id,
                product_id=raw.get("product_id") or None,
                description=(raw.get("description") or "Item").strip(),
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            ))

        discount_amount = round(subtotal * discount_percent / 100, 2)
        taxable = subtotal - discount_amount
        gst_amount = round(taxable * gst_percent / 100, 2)
        total = round(taxable + gst_amount, 2)

        invoice.subtotal = round(subtotal, 2)
        invoice.discount_amount = discount_amount
        invoice.gst_amount = gst_amount
        invoice.total_amount = total

        # Deduct stock now that the invoice is confirmed
        if invoice.status != "draft":
            for product, qty in stock_updates:
                product.quantity_available -= qty

        db.session.commit()
        flash(f"Invoice {invoice.invoice_number} created.", "success")
        return redirect(url_for("invoice.invoice_detail", invoice_id=invoice.id))

    return render_template("add_invoice.html", clients=clients, products=products,
                            preselected_client=preselected_client)


@invoice_bp.route("/<int:invoice_id>")
@login_required
def invoice_detail(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first_or_404()
    return render_template("invoice_detail.html", invoice=invoice)


@invoice_bp.route("/<int:invoice_id>/pdf")
@login_required
def invoice_pdf(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first_or_404()
    buf = generate_invoice_pdf(invoice, current_user.username, upi_id=current_user.upi_id)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{invoice.invoice_number}.pdf")


@invoice_bp.route("/<int:invoice_id>/qr.png")
@login_required
def invoice_qr(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first_or_404()
    return send_file(generate_qr_png_bytes(invoice, upi_id=current_user.upi_id, payee_name=current_user.username),
                      mimetype="image/png")


@invoice_bp.route("/<int:invoice_id>/record-payment", methods=["POST"])
@login_required
def record_payment(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first_or_404()
    try:
        amount = float(request.form.get("amount_paid") or 0)
    except ValueError:
        flash("Enter a valid payment amount.", "error")
        return redirect(url_for("invoice.invoice_detail", invoice_id=invoice.id))

    invoice.amount_paid = round(min(invoice.amount_paid + amount, invoice.total_amount), 2)
    if invoice.amount_paid >= invoice.total_amount:
        invoice.status = "paid"
    db.session.commit()
    flash(f"Recorded a payment of ₹{amount:,.2f}.", "success")
    return redirect(url_for("invoice.invoice_detail", invoice_id=invoice.id))


@invoice_bp.route("/<int:invoice_id>/delete", methods=["POST"])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=current_user.id).first_or_404()

    # Restock any products this invoice had reserved
    if invoice.status != "draft":
        for item in invoice.items:
            if item.product:
                item.product.quantity_available += item.quantity

    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted and stock restored.", "info")
    return redirect(url_for("invoice.invoices_page"))
