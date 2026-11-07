"""Invoice model with lines and a plain text rendering.

PDF rendering is deferred; only plain text is supported for now.
Credit and negative lines are unsupported. Only 2-decimal
currencies are supported, as in money.py. Amounts are integer cents.
"""

from dataclasses import dataclass

from ledgerly_shared.money import format_money


@dataclass(frozen=True)
class InvoiceLine:
    """One invoice line: a quantity of items at a unit price."""

    description: str
    quantity: int
    unit_price_cents: int

    def __post_init__(self) -> None:
        for name in ("quantity", "unit_price_cents"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int")
        if not self.description:
            raise ValueError("description must not be empty")
        if self.quantity < 1:
            raise ValueError("quantity must be at least 1")
        if self.unit_price_cents < 0:
            raise ValueError("unit_price_cents must not be negative")

    @property
    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass(frozen=True)
class Invoice:
    """An invoice whose lines all share the invoice currency."""

    number: str
    currency: str
    lines: tuple[InvoiceLine, ...] = ()

    def __post_init__(self) -> None:
        if not self.currency:
            raise ValueError("currency must not be empty")
        object.__setattr__(self, "lines", tuple(self.lines))

    @property
    def total_cents(self) -> int:
        return sum(line.total_cents for line in self.lines)


def render_text(invoice: Invoice) -> str:
    """Render the invoice as plain text."""
    cur = invoice.currency
    out = [f"Invoice {invoice.number}"]
    for line in invoice.lines:
        unit = format_money(line.unit_price_cents, cur)
        total = format_money(line.total_cents, cur)
        out.append(
            f"{line.description} x{line.quantity} @ {unit} = {total}"
        )
    out.append(f"Total: {format_money(invoice.total_cents, cur)}")
    return "\n".join(out)
