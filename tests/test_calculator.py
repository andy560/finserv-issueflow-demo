import pytest
from app.calculator import divide, calculate_interest, apply_discount


def test_divide_normal():
    assert divide(10, 2) == 5.0


def test_divide_by_zero():
    """BUG: Should raise ValueError, currently raises ZeroDivisionError."""
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)


def test_calculate_interest_normal():
    assert calculate_interest(1000, 0.05, 3) == 150.0


def test_calculate_interest_negative_principal():
    """BUG: Negative principal should raise ValueError."""
    with pytest.raises(ValueError, match="Principal must be non-negative"):
        calculate_interest(-1000, 0.05, 3)


def test_calculate_interest_negative_rate():
    """BUG: Negative rate should raise ValueError."""
    with pytest.raises(ValueError, match="Rate must be non-negative"):
        calculate_interest(1000, -0.05, 3)


def test_apply_discount_normal():
    assert apply_discount(100, 10) == 90.0


def test_apply_discount_over_100():
    """BUG: Discount > 100% should raise ValueError."""
    with pytest.raises(ValueError, match="Discount must be between 0 and 100"):
        apply_discount(100, 150)


def test_apply_discount_negative():
    """BUG: Negative discount should raise ValueError."""
    with pytest.raises(ValueError, match="Discount must be between 0 and 100"):
        apply_discount(100, -10)
