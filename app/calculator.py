"""
Financial calculator utilities.
Used for interest calculations, currency ops, and basic arithmetic.
"""


def divide(a, b):
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def calculate_interest(principal, rate, years):
    """Calculate simple interest. BUG: Doesn't validate negative inputs."""
    return principal * rate * years


def apply_discount(price, discount_pct):
    """Apply a percentage discount to a price. BUG: Doesn't clamp discount to 0-100."""
    return price - (price * discount_pct / 100)


def compound_interest(principal, rate, n, t):
    """Calculate compound interest."""
    return principal * (1 + rate / n) ** (n * t)
