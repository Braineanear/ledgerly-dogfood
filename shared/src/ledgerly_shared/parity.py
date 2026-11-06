"""Parity helpers for integers.

The contract is int-only. Behaviour for other types is unspecified.
"""


def is_even(n: int) -> bool:
    """Return True when the integer n is even, otherwise False."""
    return n % 2 == 0
