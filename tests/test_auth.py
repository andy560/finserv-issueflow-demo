import pytest
from app.auth import normalize_email, mask_account_number, validate_password_strength


def test_normalize_email_strips_whitespace():
    assert normalize_email("  user@example.com  ") == "user@example.com"


def test_normalize_email_lowercases():
    """BUG: Should lowercase the email but currently doesn't."""
    assert normalize_email("User@Example.COM") == "user@example.com"


def test_normalize_email_strips_and_lowercases():
    """BUG: Combined strip + lowercase."""
    assert normalize_email("  ADMIN@FINSERV.COM  ") == "admin@finserv.com"


def test_mask_account_number_normal():
    assert mask_account_number("1234567890") == "******7890"


def test_mask_account_number_short():
    """BUG: Should raise ValueError for account numbers shorter than 4 digits."""
    with pytest.raises(ValueError, match="Account number too short"):
        mask_account_number("123")


def test_mask_account_number_empty():
    """BUG: Empty string crashes with index out of range."""
    with pytest.raises(ValueError, match="Account number too short"):
        mask_account_number("")


def test_validate_password_too_short():
    assert validate_password_strength("abc1") is False


def test_validate_password_no_digit():
    assert validate_password_strength("abcdefgh") is False


def test_validate_password_valid():
    assert validate_password_strength("secureP4ss") is True
