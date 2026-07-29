from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Product

business_bp = Blueprint("business", __name__, url_prefix="/business")


@business_bp.route("/")
@login_required
def business_dashboard():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.created_at.desc()).all()

    total_revenue = round(sum(p.revenue() for p in products), 2)
    total_profit = round(sum(p.profit() for p in products), 2)
    total_stock_value = round(sum(p.quantity_available * p.purchase_price for p in products), 2)
    low_stock = [p for p in products if p.is_low_stock()]

    return render_template("business.html", products=products, total_revenue=total_revenue,
                            total_profit=total_profit, total_stock_value=total_stock_value,
                            low_stock=low_stock)


@business_bp.route("/products/add", methods=["GET", "POST"])
@login_required
def add_product():
    if request.method == "POST":
        try:
            purchase_price = float(request.form.get("purchase_price") or 0)
            selling_price = float(request.form.get("selling_price") or 0)
            quantity = int(request.form.get("quantity_available") or 0)
            threshold = int(request.form.get("low_stock_threshold") or 5)
        except ValueError:
            flash("Please enter valid numbers for price, quantity, and threshold.", "error")
            return render_template("add_product.html")

        product = Product(
            user_id=current_user.id,
            name=request.form.get("name", "").strip() or "Untitled Product",
            sku=request.form.get("sku", "").strip(),
            purchase_price=purchase_price,
            selling_price=selling_price,
            quantity_available=quantity,
            low_stock_threshold=threshold,
        )
        db.session.add(product)
        db.session.commit()
        flash(f"{product.name} added to inventory.", "success")
        return redirect(url_for("business.business_dashboard"))

    return render_template("add_product.html")


@business_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        try:
            product.purchase_price = float(request.form.get("purchase_price") or 0)
            product.selling_price = float(request.form.get("selling_price") or 0)
            product.quantity_available = int(request.form.get("quantity_available") or 0)
            product.low_stock_threshold = int(request.form.get("low_stock_threshold") or 5)
        except ValueError:
            flash("Please enter valid numbers for price, quantity, and threshold.", "error")
            return render_template("add_product.html", product=product)

        product.name = request.form.get("name", "").strip() or product.name
        product.sku = request.form.get("sku", "").strip()
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("business.business_dashboard"))

    return render_template("add_product.html", product=product)


@business_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
    if product.invoice_items:
        flash("This product appears on existing invoices and can't be deleted.", "error")
        return redirect(url_for("business.business_dashboard"))
    db.session.delete(product)
    db.session.commit()
    flash("Product removed from inventory.", "info")
    return redirect(url_for("business.business_dashboard"))


@business_bp.route("/payment-settings", methods=["POST"])
@login_required
def update_payment_settings():
    current_user.upi_id = request.form.get("upi_id", "").strip()
    current_user.business_name = request.form.get("business_name", "").strip()
    current_user.business_gstin = request.form.get("business_gstin", "").strip().upper()
    db.session.commit()
    flash("Payment settings updated — new invoice QR codes will use this UPI ID." if current_user.upi_id
          else "UPI ID cleared — invoice QR codes will show a plain summary instead.", "success")
    return redirect(url_for("business.business_dashboard"))


@business_bp.route("/gst-filing")
@login_required
def gst_filing():
    from datetime import date
    from utils.gst_filing import compute_gst_summary

    today = date.today()
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    if start_str and end_str:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    else:
        # Default to the current Indian financial-year quarter (Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar)
        fy_month = (today.month - 4) % 12  # months since April
        quarter_start_month = [4, 7, 10, 1][fy_month // 3]
        year = today.year if quarter_start_month <= today.month else today.year - 1
        start_date = date(year, quarter_start_month, 1)
        end_date = today

    summary = compute_gst_summary(current_user, start_date, end_date)
    return render_template("gst_filing.html", summary=summary, start_date=start_date, end_date=end_date)


@business_bp.route("/gst-filing/pdf")
@login_required
def gst_filing_pdf():
    from datetime import date
    from flask import send_file
    from utils.gst_filing import compute_gst_summary, generate_gst_pdf

    start_date = date.fromisoformat(request.args.get("start"))
    end_date = date.fromisoformat(request.args.get("end"))
    summary = compute_gst_summary(current_user, start_date, end_date)
    pdf = generate_gst_pdf(current_user, start_date, end_date, summary)
    filename = f"GST-Filing-{start_date.isoformat()}-to-{end_date.isoformat()}.pdf"
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)


@business_bp.route("/api/products")
@login_required
def products_api():
    """Used by the invoice builder to populate the product picker with live prices/stock."""
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    return jsonify([{
        "id": p.id, "name": p.name, "selling_price": p.selling_price,
        "quantity_available": p.quantity_available,
    } for p in products])


@business_bp.route("/api/alerts")
@login_required
def business_alerts():
    products = Product.query.filter_by(user_id=current_user.id).all()
    alerts = []
    for p in products:
        if p.quantity_available <= 0:
            alerts.append({"type": "out_of_stock", "color": "#E9607A",
                            "message": f"{p.name} is out of stock."})
        elif p.is_low_stock():
            alerts.append({"type": "low_stock", "color": "#E0A64A",
                            "message": f"{p.name} is low on stock ({p.quantity_available} left)."})
    return jsonify({"alerts": alerts})
