"""Money formatting helper.

Every currency is assumed to have 2 decimals. Negative amounts get a
leading "-". The currency string is used as given.
"""


def format_money(cents: int, currency: str) -> str:
    """Format an amount in cents as "12.50 USD"."""
    sign = "-" if cents < 0 else ""
    major, minor = divmod(abs(cents), 100)
    return f"{sign}{major}.{minor:02d} {currency}"
