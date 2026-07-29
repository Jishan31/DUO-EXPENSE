import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from models import Category
from utils.ocr import extract_text, parse_receipt, OCR_AVAILABLE

scanner_bp = Blueprint("scanner", __name__, url_prefix="/scanner")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@scanner_bp.route("/scan", methods=["POST"])
@login_required
def scan_bill():
    if not OCR_AVAILABLE:
        return jsonify({
            "error": "OCR isn't available on this server (Tesseract not installed). "
                     "Please enter the expense details manually.",
            "ocr_available": False,
        }), 200

    file = request.files.get("receipt")
    if not file or file.filename == "":
        return jsonify({"error": "No receipt file was uploaded."}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "Please upload a JPG, PNG, or WEBP image."}), 400

    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "receipts")
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[1].lower()
    stored_name = f"{current_user.id}_{uuid.uuid4().hex[:10]}.{ext}"
    stored_path = os.path.join(upload_dir, stored_name)
    file.save(stored_path)

    try:
        raw_text = extract_text(stored_path)
    except Exception as e:
        if type(e).__name__ == "TesseractNotFoundError":
            return jsonify({
                "error": "The Tesseract OCR engine isn't installed on this machine (pytesseract is just a "
                         "wrapper around it — it needs to be installed separately). This isn't about your "
                         "photo; scanning can't work at all until Tesseract itself is installed. On Windows, "
                         "install it from https://github.com/UB-Mannheim/tesseract/wiki, then restart the app. "
                         "You can still enter this expense manually in the meantime.",
                "ocr_available": False,
            }), 200
        raw_text = ""

    category_names = [c.name for c in Category.query.filter_by(user_id=current_user.id).all()]
    parsed = parse_receipt(raw_text, available_category_names=category_names)

    if not raw_text.strip():
        parsed["warning"] = "Couldn't read any text from this image — try a clearer, well-lit photo, or enter details manually."

    parsed["receipt_url"] = f"/static/uploads/receipts/{stored_name}"
    parsed["ocr_available"] = True
    return jsonify(parsed)
