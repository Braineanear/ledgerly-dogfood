"""Shared model placeholders."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceholderModel:
    """Minimal typed model shared by Ledgerly services."""

    identifier: str
