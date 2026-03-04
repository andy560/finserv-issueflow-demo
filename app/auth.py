"""
Authentication and user identity utilities.
"""
import re


def normalize_email(email):
    """Normalize an email address. BUG: Doesn't lowercase the email."""
    return email.strip()


def is_valid_email(email):
    """Check if email format is valid."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def mask_account_number(account_number):
    """Mask all but last 4 digits."""
    if len(account_number) < 4:
        raise ValueError("Account number too short")
    return "*" * (len(account_number) - 4) + account_number[-4:]


def validate_password_strength(password):
    """Return True if password meets minimum requirements (8+ chars, 1 digit)."""
    if len(password) < 8:
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True
