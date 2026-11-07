"""How much stock can be sold right now."""


def available_stock(on_hand: int, reserved: int) -> int:
    """Return the units that can still be sold: on hand minus reserved, never below zero."""
    return max(on_hand - reserved, 0)
