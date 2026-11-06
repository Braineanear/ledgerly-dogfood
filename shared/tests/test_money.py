"""Tests for the format_money helper."""

import ledgerly_shared
from ledgerly_shared import format_money


def test_typical_amount():
    assert format_money(1250, "USD") == "12.50 USD"


def test_zero():
    assert format_money(0, "USD") == "0.00 USD"


def test_under_one_unit():
    assert format_money(5, "USD") == "0.05 USD"


def test_whole_unit():
    assert format_money(100, "USD") == "1.00 USD"


def test_negative_under_one_unit():
    assert format_money(-50, "USD") == "-0.50 USD"


def test_negative_amount():
    assert format_money(-1250, "USD") == "-12.50 USD"


def test_large_amount():
    assert format_money(123456789012, "EUR") == "1234567890.12 EUR"


def test_exported_in_all():
    assert "format_money" in ledgerly_shared.__all__
