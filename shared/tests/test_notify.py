"""Tests for the ledgerly_shared.notify module."""

import ledgerly_shared.notify
from ledgerly_shared.notify import Notifier


def test_notify_module_exports():
    assert hasattr(ledgerly_shared.notify, "Notifier")
    assert "Notifier" in ledgerly_shared.notify.__all__


def test_new_notifier_has_no_messages():
    notifier = Notifier()
    assert notifier.messages == []
    assert isinstance(notifier.messages, list)


def test_send_stores_tuple():
    notifier = Notifier()
    result = notifier.send("alice", "hello")
    assert result is None
    assert notifier.messages == [("alice", "hello")]


def test_send_keyword_arguments():
    notifier = Notifier()
    notifier.send(recipient="bob@example.com", message="Welcome!")
    assert notifier.messages == [("bob@example.com", "Welcome!")]


def test_send_keeps_order():
    notifier = Notifier()
    notifier.send("alice", "one")
    notifier.send("bob", "two")
    notifier.send("alice", "three")
    assert notifier.messages == [
        ("alice", "one"),
        ("bob", "two"),
        ("alice", "three"),
    ]


def test_instances_do_not_share_messages():
    first = Notifier()
    second = Notifier()
    first.send("alice", "hello")
    assert second.messages == []
    assert first.messages is not second.messages


def test_send_empty_strings():
    notifier = Notifier()
    notifier.send("", "")
    assert notifier.messages == [("", "")]


def test_send_unicode_and_multiline():
    notifier = Notifier()
    recipient = "user_ñ#1@domain.org"
    message = "Line 1\nLine 2 with emoji 🚀"
    notifier.send(recipient, message)
    assert notifier.messages == [(recipient, message)]
