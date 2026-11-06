"""Order-preserving dedupe helper.

Duplicates are decided by ==/hash, so 1, 1.0 and True collapse. Each
unhashable item costs O(n) comparisons, always as new == retained.
"""

from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def dedupe(items: Iterable[T]) -> list[T]:
    """Return items without duplicates, keeping first-seen order."""
    result: list[T] = []
    seen: dict = {}
    seen_unhashable: list = []
    for item in items:
        try:
            key = hash(item)
        except TypeError:
            if any(item == r for r in result):
                continue
            seen_unhashable.append(item)
        else:
            bucket = seen.setdefault(key, [])
            if any(item == r for r in bucket):
                continue
            if seen_unhashable and any(item == u for u in seen_unhashable):
                continue
            bucket.append(item)
        result.append(item)
    return result
