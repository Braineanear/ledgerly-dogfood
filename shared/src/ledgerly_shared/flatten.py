"""Flatten one level of nested lists."""

from collections.abc import Iterable
from typing import Any


def flatten(items: Iterable[Any]) -> list[Any]:
    """Return a new list with list elements expanded one level.

    Only list instances are expanded; strings, tuples and deeper
    nesting stay intact.
    """
    result: list[Any] = []
    for item in items:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result
