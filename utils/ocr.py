"""
Bill/receipt OCR pipeline.

extract_text() runs Tesseract on an uploaded image.
parse_receipt() applies regex + keyword heuristics on the raw OCR text to
pull out merchant, date, total amount, GST, candidate line items, and a
suggested category. None of this is perfect — OCR text is messy — so every
field is designed to fail soft (return None / empty rather than raise) and
the frontend always lets the user review and correct before saving.
"""
import os
import re
import platform
from datetime import date

try:
    import pytesseract
    from PIL import Image, ImageOps, ImageFilter
    OCR_AVAILABLE = True

    # Many Windows installers (including Tesseract's) don't add themselves to
    # PATH automatically, so pytesseract can fail to find a genuinely-installed
    # binary. Point it directly at the standard install location if PATH-based
    # lookup won't already work, rather than requiring the user to edit PATH
    # and restart their terminal.
    if platform.system() == "Windows":
        _candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for _path in _candidates:
            if os.path.isfile(_path):
                pytesseract.pytesseract.tesseract_cmd = _path
                break
except ImportError:
    OCR_AVAILABLE = False

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

AMOUNT_KEYWORDS = [
    "grand total", "net payable", "net amount", "amount payable",
    "total amount", "total due", "balance due", "total",
]
GST_KEYWORDS = ["gst", "cgst", "sgst", "igst", "vat", "tax"]
SKIP_LINE_KEYWORDS = [
    "thank you", "welcome", "gstin", "fssai", "cashier", "invoice no",
    "bill no", "receipt no", "phone", "tel:", "www.", "customer copy",
    "terms", "signature", "cash", "change", "tender",
]

NUMBER_RE = re.compile(r"(?:rs\.?|inr|₹)?\s*([\d]{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)", re.IGNORECASE)
DATE_TOKEN_RE = re.compile(
    r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b"
)

CATEGORY_KEYWORDS = {
    "Food": ["restaurant", "cafe", "hotel", "food", "kitchen", "biryani", "pizza",
             "bakery", "sweets", "dhaba", "swiggy", "zomato", "grocer", "supermarket",
             "bigbasket", "mart", "provisions"],
    "Travel": ["airlines", "airways", "airport", "railway", "irctc", "cab", "taxi",
               "ola", "uber", "travels", "tourism", "flight"],
    "Shopping": ["mall", "fashion", "apparel", "footwear", "textiles", "store",
                 "electronics", "mobiles", "myntra", "amazon", "flipkart", "reliance"],
    "Entertainment": ["cinema", "movie", "pvr", "inox", "multiplex", "theatre", "event"],
    "Fuel": ["petrol", "diesel", "fuel", "hpcl", "iocl", "bpcl", "indianoil",
             "bharat petroleum", "filling station", "gas station"],
    "Education": ["school", "college", "university", "tuition", "academy",
                  "books", "institute", "course"],
    "Medical": ["pharmacy", "hospital", "clinic", "medicals", "medical", "diagnostic",
                "chemist", "healthcare", "labs"],
    "Bills": ["electricity", "water bill", "broadband", "internet", "recharge",
              "postpaid", "dth", "utility"],
}


def extract_text(image_path):
    """
    Runs Tesseract OCR on the given image path. Returns raw text (may be empty).
    Raises TesseractNotFoundError as-is (does NOT swallow it) — that specific
    failure means the Tesseract *engine* isn't installed on this machine, which
    is a setup problem, not an image-quality one, and the caller needs to tell
    those two apart to show an accurate message.
    """
    if not OCR_AVAILABLE:
        return ""
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
        img = img.convert("L")

        # Reduce very large images to save memory
        MAX_WIDTH = 1200
        if img.width > MAX_WIDTH:
             ratio = MAX_WIDTH / img.width
             img = img.resize((MAX_WIDTH, int(img.height * ratio)))

        img = img.filter(ImageFilter.SHARPEN)
    except Exception:
        return ""  # couldn't even open/process the image file itself

    try:
        return pytesseract.image_to_string(img)
    except pytesseract.TesseractNotFoundError:
        raise
    except Exception:
        return ""


def _clean_number(raw):
    try:
        return float(raw.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _find_amount(lines):
    # Pass 1: look for an explicit total/amount keyword line
    for keyword in AMOUNT_KEYWORDS:
        for line in lines:
            if keyword in line.lower():
                nums = NUMBER_RE.findall(line)
                candidates = [_clean_number(n) for n in nums if _clean_number(n)]
                if candidates:
                    return max(candidates)

    # Pass 2: fallback — largest currency-looking number anywhere in the receipt
    all_nums = []
    for line in lines:
        if any(skip in line.lower() for skip in SKIP_LINE_KEYWORDS):
            continue
        for n in NUMBER_RE.findall(line):
            val = _clean_number(n)
            if val and val > 1:
                all_nums.append(val)
    return max(all_nums) if all_nums else None


GST_LINE_RE = re.compile(r"\b(c?s?i?gst|vat|tax)\b", re.IGNORECASE)


def _find_gst(lines):
    total_gst = 0.0
    found = False
    for line in lines:
        low = line.lower()
        # "GSTIN" is a tax ID, not a tax amount — must not be mistaken for a GST line
        if "gstin" in low or "total" in low:
            continue
        if GST_LINE_RE.search(low):
            nums = [_clean_number(n) for n in NUMBER_RE.findall(line)]
            nums = [n for n in nums if n]
            if nums:
                total_gst += max(nums)
                found = True
    return round(total_gst, 2) if found else 0.0


def _find_date(text):
    match = DATE_TOKEN_RE.search(text)
    if not match or not date_parser:
        return None
    try:
        parsed = date_parser.parse(match.group(1), dayfirst=True, fuzzy=True)
        if parsed.date() > date.today():
            return None  # receipts aren't from the future — likely a misread
        return parsed.date()
    except (ValueError, OverflowError):
        return None


def _find_merchant(lines):
    for line in lines[:6]:
        clean = line.strip()
        letters = sum(c.isalpha() for c in clean)
        if letters >= 3 and not any(skip in clean.lower() for skip in SKIP_LINE_KEYWORDS):
            return clean.title() if clean.isupper() else clean
    return ""


def _find_products(lines):
    products = []
    item_line_re = re.compile(r"^(.{2,30}?)\s+(\d+(?:\.\d{1,2})?)\s*$")
    for line in lines:
        low = line.lower()
        if any(k in low for k in AMOUNT_KEYWORDS + GST_KEYWORDS + SKIP_LINE_KEYWORDS):
            continue
        m = item_line_re.match(line.strip())
        if m:
            name = m.group(1).strip(" -.:")
            price = _clean_number(m.group(2))
            if name and price and len(name) > 1:
                products.append({"name": name, "price": price})
        if len(products) >= 10:
            break
    return products


def _suggest_category(text, merchant, available_category_names):
    haystack = f"{merchant} {text}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            # only suggest it if the user actually still has a category by this name
            for name in available_category_names:
                if name.lower() == category.lower():
                    return name
    return None


def parse_receipt(raw_text, available_category_names=None):
    available_category_names = available_category_names or []
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    amount = _find_amount(lines)
    gst = _find_gst(lines)
    merchant = _find_merchant(lines)
    found_date = _find_date(raw_text)
    products = _find_products(lines)
    suggested_category = _suggest_category(raw_text, merchant, available_category_names)

    return {
        "merchant": merchant,
        "amount": amount,
        "gst_amount": gst,
        "date": found_date.isoformat() if found_date else None,
        "products": products,
        "suggested_category": suggested_category,
        "raw_text_preview": "\n".join(lines[:20]),
    }
