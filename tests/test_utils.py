import pytest
from app.utils import format_currency, truncate_name, parse_date


def test_format_currency_integer():
    """BUG: Returns '$100' instead of '$100.00'"""
    assert format_currency(100) == "$100.00"


def test_format_currency_float():
    """BUG: Returns '$99.9' instead of '$99.90'"""
    assert format_currency(99.9) == "$99.90"


def test_format_currency_zero():
    assert format_currency(0) == "$0.00"


def test_format_currency_large():
    assert format_currency(1234567.89) == "$1234567.89"


def test_truncate_name_short():
    assert truncate_name("Alice") == "Alice"


def test_truncate_name_long():
    assert truncate_name("Bartholomew Henderson", 10) == "Bartholomew..."


def test_truncate_name_none():
    """BUG: Passing None crashes with TypeError."""
    with pytest.raises(ValueError, match="Name cannot be None"):
        truncate_name(None)


def test_parse_date_valid():
    from datetime import datetime
    assert parse_date("2024-01-15") == datetime(2024, 1, 15)


def test_parse_date_invalid_format():
    """BUG: Bad date format raises unhandled ValueError from strptime."""
    with pytest.raises(ValueError, match="Invalid date format"):
        parse_date("15/01/2024")
