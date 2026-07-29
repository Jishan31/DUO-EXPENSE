"""
CSV expense import — auto-detects which column is which from common header
name variants, parses each row, and matches/creates categories. Designed to
fail soft on individual bad rows (skip + reason) rather than reject an
entire file over one malformed line.
"""
import csv
import io
from datetime import date as date_cls

from dateutil import parser as date_parser

COLUMN_ALIASES = {
    "date": ["date", "transaction date", "txn date", "expense date", "posted date"],
    "amount": ["amount", "amt", "value", "price", "total", "debit", "debit amount"],
    "name": ["name", "description", "desc", "particulars", "narration", "details", "title"],
    "category": ["category", "cat", "type", "expense category"],
    "merchant": ["merchant", "vendor", "payee", "store", "payee name"],
    "payment_mode": ["payment mode", "mode", "payment method", "channel", "payment type"],
}

REQUIRED_ROLES = ["date", "amount"]


class ImportError_(Exception):
    """Raised when the file structure itself can't be worked with (not a per-row issue)."""
    pass


def detect_columns(headers):
    """Maps each recognized role to the actual header name found, e.g. {'date': 'Txn Date', 'amount': 'Amount'}."""
    normalized = {h: h.strip().lower() for h in headers}
    mapping = {}
    for role, aliases in COLUMN_ALIASES.items():
        for header, norm in normalized.items():
            if norm in aliases:
                mapping[role] = header
                break
    return mapping


def _parse_amount(raw):
    if raw is None:
        return None
    cleaned = str(raw).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "").strip()
    cleaned = cleaned.replace("(", "-").replace(")", "")  # accounting-style negatives
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        return abs(val)  # expenses are always logged as positive amounts in this app
    except ValueError:
        return None


def _parse_date(raw):
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = date_parser.parse(str(raw).strip(), dayfirst=True, fuzzy=True).date()
        if parsed > date_cls.today():
            return None  # future dates are almost certainly a misparse
        return parsed
    except (ValueError, OverflowError):
        return None


def parse_csv(file_stream, available_category_names):
    """
    Returns {
        "mapping": {...} or None if required columns weren't found,
        "headers": [...],
        "rows": [ {row_num, status: 'ok'|'skip', reason, date, amount, name, category, merchant, payment_mode}, ... ],
        "total_rows": int,
    }
    """
    raw_bytes = file_stream.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    mapping = detect_columns(headers)

    missing_required = [r for r in REQUIRED_ROLES if r not in mapping]
    if missing_required:
        return {"mapping": mapping, "headers": headers, "rows": [], "total_rows": 0,
                "missing_required": missing_required}

    category_lookup = {name.lower(): name for name in available_category_names}
    rows = []

    for i, raw_row in enumerate(reader, start=1):
        date_val = _parse_date(raw_row.get(mapping.get("date", ""), ""))
        amount_val = _parse_amount(raw_row.get(mapping.get("amount", ""), ""))

        if date_val is None:
            rows.append({"row_num": i, "status": "skip", "reason": "Couldn't read a valid date", "raw": raw_row})
            continue
        if amount_val is None or amount_val <= 0:
            rows.append({"row_num": i, "status": "skip", "reason": "Couldn't read a valid amount", "raw": raw_row})
            continue

        name = (raw_row.get(mapping.get("name", ""), "") or "").strip() or "Imported expense"
        merchant = (raw_row.get(mapping.get("merchant", ""), "") or "").strip()
        payment_mode = (raw_row.get(mapping.get("payment_mode", ""), "") or "").strip() or "Other"

        category_raw = (raw_row.get(mapping.get("category", ""), "") or "").strip()
        matched_category = category_lookup.get(category_raw.lower()) if category_raw else None

        rows.append({
            "row_num": i, "status": "ok", "reason": None,
            "date": date_val.isoformat(), "amount": amount_val, "name": name,
            "merchant": merchant, "payment_mode": payment_mode,
            "category": matched_category,          # None means "no existing category matched"
            "category_raw": category_raw,           # what the CSV actually said, for creating a new one
        })

    return {"mapping": mapping, "headers": headers, "rows": rows, "total_rows": len(rows),
            "missing_required": []}
