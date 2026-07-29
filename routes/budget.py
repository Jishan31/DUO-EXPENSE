from datetime import date
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models import Category, Expense

budget_bp = Blueprint("budget", __name__, url_prefix="/budgets")


def _status(spent, budget):
    if not budget or budget <= 0:
        return "none"
    pct = spent / budget * 100
    if pct >= 100:
        return "over"
    if pct >= 80:
        return "warning"
    return "ok"


def _compute_budget_data(user):
    categories = Category.query.filter_by(user_id=user.id).order_by(Category.sort_order).all()
    today = date.today()

    cat_data = []
    total_spent = 0.0
    for c in categories:
        spent = c.spent_this_month()
        total_spent += spent
        pct = round(min((spent / c.monthly_budget * 100), 999), 1) if c.monthly_budget else 0
        cat_data.append({
            "id": c.id, "name": c.name, "color": c.color, "icon": c.icon,
            "spent": round(spent, 2), "budget": c.monthly_budget,
            "percent": pct, "status": _status(spent, c.monthly_budget),
            "remaining": round(max(c.monthly_budget - spent, 0), 2) if c.monthly_budget else None,
        })

    total_budget = user.monthly_budget_total or 0
    total_pct = round(min((total_spent / total_budget * 100), 999), 1) if total_budget else 0

    alerts = []
    for c in cat_data:
        if c["status"] == "over":
            over_by = round(c["spent"] - c["budget"], 2)
            alerts.append({"type": "category_over", "category": c["name"], "color": c["color"],
                            "message": f"{c['name']} is over budget by ₹{over_by:,.0f}."})
        elif c["status"] == "warning":
            alerts.append({"type": "category_warning", "category": c["name"], "color": c["color"],
                            "message": f"{c['name']} has used {c['percent']:.0f}% of its budget."})
    if total_budget and total_spent > total_budget:
        alerts.append({"type": "total_over", "category": None, "color": "#E9607A",
                        "message": f"You're ₹{total_spent - total_budget:,.0f} over your overall monthly budget."})

    return {
        "categories": cat_data,
        "total_budget": total_budget,
        "total_spent": round(total_spent, 2),
        "total_percent": total_pct,
        "total_status": _status(total_spent, total_budget),
        "month_label": today.strftime("%B %Y"),
        "alerts": alerts,
    }


@budget_bp.route("/")
@login_required
def budgets_page():
    data = _compute_budget_data(current_user)
    return render_template("budgets.html", data=data)


@budget_bp.route("/update-total", methods=["POST"])
@login_required
def update_total_budget():
    payload = request.get_json(silent=True) or {}
    try:
        value = float(payload.get("monthly_budget_total", 0) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number."}), 400
    current_user.monthly_budget_total = max(value, 0)
    db.session.commit()
    return jsonify({"success": True, "monthly_budget_total": current_user.monthly_budget_total})


@budget_bp.route("/api", methods=["GET"])
@login_required
def budgets_api():
    return jsonify(_compute_budget_data(current_user))
