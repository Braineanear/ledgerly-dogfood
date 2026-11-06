"""Tests for the clamp helper."""

from datetime import date, datetime
from decimal import Decimal

import pytest

import ledgerly_shared
from ledgerly_shared.clamp import clamp


def test_inside_range():
    assert clamp(5, 0, 10) == 5


def test_below_range():
    assert clamp(-3, 0, 10) == 0


def test_above_range():
    assert clamp(42, 0, 10) == 10


def test_at_low_bound():
    assert clamp(0, 0, 10) == 0


def test_at_high_bound():
    assert clamp(10, 0, 10) == 10


def test_low_equals_high():
    assert clamp(7, 3, 3) == 3
    assert clamp(3, 3, 3) == 3
    assert clamp(-1, 3, 3) == 3


def test_floats():
    assert clamp(0.5, 0.0, 1.0) == 0.5
    assert clamp(-0.1, 0.0, 1.0) == 0.0
    assert clamp(1.5, 0.0, 1.0) == 1.0


def test_negative_range():
    assert clamp(-5, -10, -2) == -5
    assert clamp(-20, -10, -2) == -10
    assert clamp(0, -10, -2) == -2


def test_low_greater_than_high_raises():
    with pytest.raises(ValueError, match="must not be greater"):
        clamp(5, 10, 0)


def test_package_export():
    assert hasattr(ledgerly_shared, "clamp")
    assert ledgerly_shared.clamp(5, 0, 10) == 5


def test_infinity():
    assert clamp(100.0, 0.0, float("inf")) == 100.0
    assert clamp(float("inf"), 0.0, 100.0) == 100.0
    assert clamp(float("-inf"), 0.0, 100.0) == 0.0
    assert clamp(5.0, float("-inf"), float("inf")) == 5.0


def test_decimal():
    low = Decimal("10.00")
    high = Decimal("50.00")
    assert clamp(Decimal("25.50"), low, high) == Decimal("25.50")
    assert clamp(Decimal("5.00"), low, high) == Decimal("10.00")
    assert clamp(Decimal("100.00"), low, high) == Decimal("50.00")


def test_datetime_and_date():
    d_low = date(2025, 1, 1)
    d_high = date(2025, 12, 31)
    assert clamp(date(2025, 6, 15), d_low, d_high) == date(2025, 6, 15)
    assert clamp(date(2024, 1, 1), d_low, d_high) == d_low
    assert clamp(date(2026, 1, 1), d_low, d_high) == d_high

    dt_low = datetime(2025, 1, 1, 0, 0, 0)
    dt_high = datetime(2025, 1, 1, 23, 59, 59)
    assert clamp(datetime(2025, 1, 1, 12, 0, 0), dt_low, dt_high) == datetime(
        2025, 1, 1, 12, 0, 0
    )


def test_strings():
    assert clamp("c", "a", "z") == "c"
    assert clamp("0", "a", "z") == "a"
    assert clamp("z1", "a", "z") == "z"


def test_low_greater_than_high_float_and_negative_raises():
    with pytest.raises(ValueError, match="must not be greater"):
        clamp(-5.0, -2.0, -10.0)
