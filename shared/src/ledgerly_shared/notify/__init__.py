"""Minimal in-memory notifier."""

__all__ = ["Notifier"]


class Notifier:
    """Stores sent messages in order, per instance."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, recipient: str, message: str) -> None:
        self.messages.append((recipient, message))
