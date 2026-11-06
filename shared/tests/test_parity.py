"""Tests for the parity helper."""

from ledgerly_shared.parity import is_even


def test_positive_even():
    assert is_even(2) is True
    assert is_even(100) is True


def test_positive_odd():
    assert is_even(1) is False
    assert is_even(99) is False


def test_zero():
    assert is_even(0) is True


def test_negative_even():
    assert is_even(-2) is True
    assert is_even(-4) is True


def test_negative_odd():
    assert is_even(-1) is False
    assert is_even(-3) is False


def test_large_values():
    assert is_even(10**30) is True
    assert is_even(10**30 + 1) is False
