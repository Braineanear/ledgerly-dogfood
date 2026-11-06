"""Tests for the slugify helper."""

import ledgerly_shared
from ledgerly_shared import slugify


def test_two_words():
    assert slugify("Hello World") == "hello-world"


def test_single_word():
    assert slugify("Widget") == "widget"


def test_mixed_case():
    assert slugify("hELLo WoRLD") == "hello-world"


def test_multiple_internal_spaces():
    assert slugify("a   b    c") == "a-b-c"


def test_leading_and_trailing_whitespace():
    assert slugify("  Hello World \t") == "hello-world"


def test_empty_string():
    assert slugify("") == ""


def test_whitespace_only():
    assert slugify("   \t ") == ""


def test_exported_in_all():
    assert "slugify" in ledgerly_shared.__all__
