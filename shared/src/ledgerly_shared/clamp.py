"""Limit a value to an inclusive range."""

from typing import Any, TypeVar

T = TypeVar("T", bound=Any)


def clamp(value: T, low: T, high: T) -> T:
    """Return value limited to the range low..high (inclusive).

    Raises ValueError when low is greater than high. low == high is
    allowed. Behaviour with NaN inputs is unspecified.
    """
    if low > high:
        raise ValueError(
            f"low ({low!r}) must not be greater than high ({high!r})"
        )
    return max(low, min(value, high))
