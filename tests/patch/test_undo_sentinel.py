"""Tests for src/td_mcp/patch/undo_sentinel.py."""

from __future__ import annotations

import pytest

from td_mcp.patch.undo_sentinel import UndoBlockSentinel


def test_fresh_sentinel_inactive():
    s = UndoBlockSentinel()
    assert s.is_active() is False
    assert s.active_label is None


def test_mark_active():
    s = UndoBlockSentinel()
    s.mark_active("feedback trail")
    assert s.is_active() is True
    assert s.active_label == "feedback trail"


def test_mark_active_while_active_raises():
    s = UndoBlockSentinel()
    s.mark_active("first")
    with pytest.raises(RuntimeError, match="already active"):
        s.mark_active("second")


def test_mark_inactive_resets():
    s = UndoBlockSentinel()
    s.mark_active("x")
    s.mark_inactive()
    assert s.is_active() is False
    assert s.active_label is None


def test_mark_inactive_while_inactive_is_noop():
    s = UndoBlockSentinel()
    s.mark_inactive()  # should not raise
    assert s.is_active() is False
