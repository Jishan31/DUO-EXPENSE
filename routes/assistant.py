from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from extensions import db
from models import ChatMessage
from utils.assistant import ask_assistant, AssistantNotConfigured, AssistantError

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

HISTORY_LIMIT = 12


@assistant_bp.route("/history")
@login_required
def history():
    messages = (ChatMessage.query.filter_by(user_id=current_user.id)
                .order_by(ChatMessage.created_at.desc()).limit(HISTORY_LIMIT).all())
    messages.reverse()
    return jsonify([{"role": m.role, "content": m.content} for m in messages])


@assistant_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Type a message first."}), 400
    if len(message) > 2000:
        return jsonify({"error": "That message is too long — try something shorter."}), 400

    recent = (ChatMessage.query.filter_by(user_id=current_user.id)
              .order_by(ChatMessage.created_at.desc()).limit(HISTORY_LIMIT).all())
    recent.reverse()

    db.session.add(ChatMessage(user_id=current_user.id, role="user", content=message))
    db.session.commit()

    try:
        reply = ask_assistant(current_user, message, recent)
    except AssistantNotConfigured as e:
        return jsonify({"error": str(e), "not_configured": True})
    except AssistantError as e:
        return jsonify({"error": str(e)})

    db.session.add(ChatMessage(user_id=current_user.id, role="assistant", content=reply))
    db.session.commit()

    return jsonify({"reply": reply})


@assistant_bp.route("/clear", methods=["POST"])
@login_required
def clear():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"success": True})
