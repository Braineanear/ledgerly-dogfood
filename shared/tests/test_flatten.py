"""Tests for the flatten helper."""

import ledgerly_shared
from ledgerly_shared import flatten


def test_empty_list():
    assert flatten([]) == []


def test_mixed_scalars_and_lists():
    assert flatten([1, [2, 3], 4, []]) == [1, 2, 3, 4]


def test_one_level_only():
    assert flatten([1, [2, 3], [[4]]]) == [1, 2, 3, [4]]


def test_strings_kept_whole():
    assert flatten(["ab", ["cd"]]) == ["ab", "cd"]


def test_tuples_not_expanded():
    assert flatten([(1, 2), [3]]) == [(1, 2), 3]


def test_generator_input():
    assert flatten([x] for x in range(3)) == [0, 1, 2]


def test_input_not_mutated():
    items = [1, [2, 3]]
    result = flatten(items)
    assert items == [1, [2, 3]]
    assert result is not items


def test_list_subclasses_are_flattened():
    class NestedList(list):
        pass

    assert flatten([NestedList([1, 2])]) == [1, 2]


def test_nested_list_objects_are_not_copied():
    nested = [[{"value": 1}]]

    result = flatten(nested)

    assert result[0] is nested[0][0]


def test_self_referential_nested_list_is_not_recursed():
    nested = []
    nested.append(nested)

    result = flatten([nested])

    assert result == [nested]
    assert result[0] is nested


def test_exported_in_all():
    assert "flatten" in ledgerly_shared.__all__
