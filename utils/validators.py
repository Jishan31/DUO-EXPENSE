"""
Shared validation for registration/account forms: real email format checking,
password strength scoring, and phone numbers validated against the format
of a specific selected region (not just "is this a string of digits").
"""
import re
from email_validator import validate_email as _validate_email, EmailNotValidError
import phonenumbers

# A practical, common subset of regions for the dropdown — not all ~195
# countries, but covers the large majority of a real user base. Each is
# (ISO 3166-1 alpha-2 code, display name, calling code) — phonenumbers
# derives the actual per-region format rules from the ISO code.
REGIONS = [
    ("IN", "India", "+91"), ("US", "United States", "+1"), ("GB", "United Kingdom", "+44"),
    ("CA", "Canada", "+1"), ("AU", "Australia", "+61"), ("AE", "UAE", "+971"),
    ("SG", "Singapore", "+65"), ("DE", "Germany", "+49"), ("FR", "France", "+33"),
    ("JP", "Japan", "+81"), ("BR", "Brazil", "+55"), ("ZA", "South Africa", "+27"),
    ("NZ", "New Zealand", "+64"), ("NL", "Netherlands", "+31"), ("MY", "Malaysia", "+60"),
]
REGION_CODES = {r[0] for r in REGIONS}


def validate_email_format(email):
    """Returns (is_valid, normalized_email_or_error_message)."""
    try:
        result = _validate_email(email, check_deliverability=False)
        return True, result.normalized
    except EmailNotValidError as e:
        return False, str(e)


def validate_phone_for_region(phone, region_code):
    """Returns (is_valid, formatted_number_or_error_message). Phone is optional
    upstream — call this only when a phone number was actually provided."""
    if region_code not in REGION_CODES:
        return False, "Choose a region."
    try:
        parsed = phonenumbers.parse(phone, region_code)
    except phonenumbers.NumberParseException:
        return False, "That doesn't look like a valid phone number."
    if not phonenumbers.is_valid_number(parsed):
        return False, f"That's not a valid phone number for the selected region."
    return True, phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def password_strength(password):
    """
    Returns (level, score) where level is 'weak' | 'moderate' | 'strong' and
    score is 0-4, based on length + character variety. Mirrors the JS meter
    exactly so client and server never disagree about what "strong" means.
    """
    if not password:
        return "weak", 0
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[a-z]", password) and re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[0-9]", password):
        score += 1
    if re.search(r"[^A-Za-z0-9]", password):
        score += 1

    if score <= 2:
        return "weak", score
    if score <= 3:
        return "moderate", score
    return "strong", score


def is_password_strong_enough(password):
    """The actual server-side gate — registration/reset requires at least 'moderate'."""
    level, _ = password_strength(password)
    return level in ("moderate", "strong")
