"""
Dataset import — reads an uploaded CSV, guesses which columns hold date/
amount/description, and turns rows into Expense records. Real-world CSVs
vary a lot (bank exports, other apps' exports, spreadsheets people made by
hand), so this favors flexible detection + a confirmation step over
assuming one fixed format.
"""
import csv

from dateutil import parser as date_parser

from utils.ocr import CATEGORY_KEYWORDS

COMMON_DATE_HEADERS = ["date", "transaction date", "txn date", "value date", "posting date", "trans date"]
COMMON_AMOUNT_HEADERS = ["amount", "debit", "withdrawal", "amt", "debit amount", "value",
                          "transaction amount", "withdrawal amt", "withdrawal amount"]
COMMON_DESC_HEADERS = ["description", "narration", "particulars", "details", "merchant",
                        "remarks", "transaction details", "payee", "notes"]
COMMON_CATEGORY_HEADERS = ["category", "type", "transaction type", "tag"]


def sniff_delimiter(sample_text):
    try:
        return csv.Sniffer().sniff(sample_text, delimiters=",;\t").delimiter
    except Exception:
        return ","


def read_csv_rows(file_path):
    """Returns (headers, rows) — rows is a list of dicts keyed by header."""
    with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delimiter = sniff_delimiter(sample)
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        rows = list(reader)
    return headers, rows


def _guess_column(headers, candidates):
    lower_map = {h.strip().lower(): h for h in headers}
    for c in candidates:
        if c in lower_map:
            return lower_map[c]
    for h in headers:
        hl = h.strip().lower()
        if any(c in hl for c in candidates):
            return h
    return None


def guess_mapping(headers):
    return {
        "date_col": _guess_column(headers, COMMON_DATE_HEADERS),
        "amount_col": _guess_column(headers, COMMON_AMOUNT_HEADERS),
        "desc_col": _guess_column(headers, COMMON_DESC_HEADERS),
        "category_col": _guess_column(headers, COMMON_CATEGORY_HEADERS),
    }


def parse_amount(raw):
    """Handles ₹/Rs./commas/parentheses-as-negative/plain signed numbers. Returns float or None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]

    for token in ("₹", "Rs.", "Rs", "INR", "$", ","):
        s = s.replace(token, "")
    s = s.strip()

    if s.startswith("-"):
        negative = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]

    try:
        val = float(s)
    except ValueError:
        return None
    return -val if negative else val


def parse_date_value(raw):
    if not raw or not str(raw).strip():
        return None
    try:
        return date_parser.parse(str(raw).strip(), dayfirst=True, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def suggest_category_for_text(text, available_categories):
    """available_categories: list of Category objects belonging to the user. Returns a Category or None."""
    text_low = (text or "").lower()
    name_map = {c.name.lower(): c for c in available_categories}
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_low for kw in keywords) and cat_name.lower() in name_map:
            return name_map[cat_name.lower()]
    return None
