"""Tests for the Invoice model and its text rendering."""

from dataclasses import FrozenInstanceError

import pytest

from ledgerly_shared import invoice as invoice_module
from ledgerly_shared.invoice import Invoice, InvoiceLine, render_text


def test_line_total():
    assert InvoiceLine("Widget", 3, 250).total_cents == 750


def test_invoice_total_across_lines():
    inv = Invoice(
        "A1",
        "USD",
        (InvoiceLine("Widget", 2, 100), InvoiceLine("Gadget", 1, 55)),
    )
    assert inv.total_cents == 255


def test_empty_invoice():
    inv = Invoice("A0", "USD")
    assert inv.total_cents == 0
    assert render_text(inv) == "Invoice A0\nTotal: 0.00 USD"


def test_render_two_lines():
    inv = Invoice(
        "A2",
        "USD",
        (InvoiceLine("Widget", 2, 1250), InvoiceLine("Gadget", 1, 5)),
    )
    assert render_text(inv) == (
        "Invoice A2\n"
        "Widget x2 @ 12.50 USD = 25.00 USD\n"
        "Gadget x1 @ 0.05 USD = 0.05 USD\n"
        "Total: 25.05 USD"
    )


@pytest.mark.parametrize("quantity", [0, -1])
def test_bad_quantity_rejected(quantity):
    with pytest.raises(ValueError):
        InvoiceLine("Widget", quantity, 100)


def test_negative_unit_price_rejected():
    with pytest.raises(ValueError):
        InvoiceLine("Widget", 1, unit_price_cents=-1)


def test_zero_unit_price_accepted():
    assert InvoiceLine("Freebie", 1, 0).total_cents == 0


def test_empty_description_rejected():
    with pytest.raises(ValueError):
        InvoiceLine("", 1, 100)


def test_empty_currency_rejected():
    with pytest.raises(ValueError):
        Invoice("A3", "")


def test_immutable():
    line = InvoiceLine("Widget", 1, 100)
    with pytest.raises(FrozenInstanceError):
        line.quantity = 2
    inv = Invoice("A4", "USD")
    with pytest.raises(FrozenInstanceError):
        inv.number = "B"


def test_pdf_rendering_deferred():
    assert not hasattr(invoice_module, "render_pdf")


def test_render_single_line():
    inv = Invoice(
        "INV-001",
        "EUR",
        (InvoiceLine("Service Fee", 1, 5000),),
    )
    assert render_text(inv) == (
        "Invoice INV-001\n"
        "Service Fee x1 @ 50.00 EUR = 50.00 EUR\n"
        "Total: 50.00 EUR"
    )


def test_render_zero_unit_price_line():
    inv = Invoice(
        "INV-002",
        "USD",
        (InvoiceLine("Free Sample", 2, 0),),
    )
    assert render_text(inv) == (
        "Invoice INV-002\n"
        "Free Sample x2 @ 0.00 USD = 0.00 USD\n"
        "Total: 0.00 USD"
    )


def test_large_quantity_and_amount_totals():
    inv = Invoice(
        "INV-999",
        "USD",
        (InvoiceLine("Bulk Item", 10_000, 150_000),),
    )
    assert inv.total_cents == 1_500_000_000
    assert render_text(inv) == (
        "Invoice INV-999\n"
        "Bulk Item x10000 @ 1500.00 USD = 15000000.00 USD\n"
        "Total: 15000000.00 USD"
    )


def test_different_currencies():
    inv = Invoice(
        "INV-006",
        "GBP",
        (InvoiceLine("Consulting", 5, 2000),),
    )
    assert inv.total_cents == 10000
    assert render_text(inv) == (
        "Invoice INV-006\n"
        "Consulting x5 @ 20.00 GBP = 100.00 GBP\n"
        "Total: 100.00 GBP"
    )


def test_invoice_lines_as_list_converted_to_tuple():
    line1 = InvoiceLine("Item 1", 1, 100)
    lines_list = [line1]
    inv = Invoice("INV-003", "USD", lines_list)
    assert isinstance(inv.lines, tuple)


def test_non_integer_quantity_rejected():
    with pytest.raises((TypeError, ValueError)):
        InvoiceLine("Item", 1.5, 100)


def test_non_integer_unit_price_rejected():
    with pytest.raises((TypeError, ValueError)):
        InvoiceLine("Item", 1, 12.5)

