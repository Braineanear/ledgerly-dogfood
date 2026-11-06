"""Tests for the dedupe helper."""

import ledgerly_shared
from ledgerly_shared import dedupe


class Box:
    __hash__ = None

    def __eq__(self, other):
        return other == 1


def test_order_preserved():
    assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]


def test_empty_list():
    assert dedupe([]) == []


def test_all_duplicates():
    assert dedupe([2, 2, 2]) == [2]


def test_no_duplicates():
    assert dedupe([1, 2, 3]) == [1, 2, 3]


def test_generator_input():
    assert dedupe(x % 2 for x in range(5)) == [0, 1]


def test_tuple_input():
    assert dedupe(("a", "b", "a")) == ["a", "b"]


def test_nested_lists():
    assert dedupe([[1], [2], [1]]) == [[1], [2]]


def test_dicts():
    assert dedupe([{"a": 1}, {"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]


def test_mixed_hashable_and_unhashable():
    assert dedupe([1, [1], "x", [1], 1, "x", [2]]) == [1, [1], "x", [2]]


def test_unhashable_then_equal_hashable():
    box = Box()
    assert dedupe([box, 1]) == [box]


def test_hashable_then_equal_unhashable():
    box = Box()
    assert dedupe([1, box]) == [1]


def test_hashable_duplicates_use_new_item_equality():
    class Directional:
        def __init__(self, name, equal_to):
            self.name = name
            self.equal_to = equal_to

        def __hash__(self):
            return 0

        def __eq__(self, other):
            return self.equal_to == other.name

    first = Directional("first", "never")
    second = Directional("second", "first")

    result = dedupe([first, second])

    assert len(result) == 1
    assert result[0] is first


def test_one_float_true_collapse():
    assert dedupe([1, 1.0, True]) == [1]


def test_input_not_mutated():
    items = [1, 1, 2]
    result = dedupe(items)
    assert items == [1, 1, 2]
    assert result is not items


def test_exported_in_all():
    assert "dedupe" in ledgerly_shared.__all__
