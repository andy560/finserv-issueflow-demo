"""
General utility functions for formatting and data processing.
"""
from datetime import datetime


def format_currency(amount):
    """Format a number as USD currency string. BUG: No 2 decimal place formatting."""
    return f"${amount:.2f}"


def parse_date(date_str):
    """Parse a date string in YYYY-MM-DD format. BUG: No error handling for bad formats."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def calculate_days_overdue(due_date_str):
    """Return number of days a payment is overdue. Returns 0 if not overdue."""
    due = parse_date(due_date_str)
    today = datetime.today()
    delta = (today - due).days
    return max(0, delta)


def truncate_name(name, max_length=20):
    """Truncate a display name to max_length. BUG: Doesn't handle None input."""
    if len(name) <= max_length:
        return name
    return name[:max_length] + "..."
