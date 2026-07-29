from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Category

category_bp = Blueprint("category", __name__, url_prefix="/categories")

# A small rotating palette so new categories still look intentional on the wheel
PALETTE = ["#B57EDC", "#8E6FCE", "#A783E1", "#C79BEF", "#9A7FE0",
           "#7C5CBF", "#B08DE8", "#976FDB", "#856AC9", "#D0B6F5"]


@category_bp.route("/", methods=["GET"])
@login_required
def list_categories():
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.sort_order).all()
    return jsonify([{
        "id": c.id, "name": c.name, "icon": c.icon, "color": c.color,
        "monthly_budget": c.monthly_budget, "is_default": c.is_default,
    } for c in categories])


@category_bp.route("/add", methods=["POST"])
@login_required
def add_category():
    payload = request.get_json(silent=True) or request.form
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    count = Category.query.filter_by(user_id=current_user.id).count()
    category = Category(
        user_id=current_user.id,
        name=name,
        icon=payload.get("icon") or "tag",
        color=payload.get("color") or PALETTE[count % len(PALETTE)],
        monthly_budget=float(payload.get("monthly_budget") or 0),
        sort_order=count,
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({"id": category.id, "name": category.name, "color": category.color, "icon": category.icon}), 201


@category_bp.route("/<int:category_id>/edit", methods=["POST"])
@login_required
def edit_category(category_id):
    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    payload = request.get_json(silent=True) or request.form

    category.name = (payload.get("name") or category.name).strip()
    category.icon = payload.get("icon") or category.icon
    category.color = payload.get("color") or category.color
    if payload.get("monthly_budget") is not None:
        category.monthly_budget = float(payload.get("monthly_budget") or 0)
    db.session.commit()
    return jsonify({"id": category.id, "name": category.name, "color": category.color, "icon": category.icon})


@category_bp.route("/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    category = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    if category.expenses:
        return jsonify({"error": "Move or delete expenses in this category first."}), 400
    db.session.delete(category)
    db.session.commit()
    return jsonify({"success": True})
