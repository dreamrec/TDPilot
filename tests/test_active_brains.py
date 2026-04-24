"""Tests for active.json brain gating."""

import json
import tempfile
from pathlib import Path


def _write_active(tmp: Path, brains: list[str]) -> Path:
    """Write an active.json file and return its path."""
    active_path = tmp / "data" / "brains" / "active.json"
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(
        json.dumps(
            {
                "installed_brains": brains,
                "installed_at": "2026-03-15T00:00:00Z",
                "manifest_version": 1,
            }
        )
    )
    return active_path


def test_get_active_brains_returns_none_when_no_file():
    """No active.json = None = load everything."""
    from td_mcp.tool_registry import _get_active_brains

    with tempfile.TemporaryDirectory() as tmp:
        result = _get_active_brains(search_paths=[Path(tmp) / "nonexistent"])
    assert result is None


def test_get_active_brains_returns_set_from_file():
    """active.json with brains returns a set."""
    from td_mcp.tool_registry import _get_active_brains

    with tempfile.TemporaryDirectory() as tmp:
        active_path = _write_active(Path(tmp), ["derivative", "popx"])
        result = _get_active_brains(search_paths=[active_path])
    assert result == {"derivative", "popx"}


def test_get_active_brains_empty_list():
    """active.json with empty list = no brains."""
    from td_mcp.tool_registry import _get_active_brains

    with tempfile.TemporaryDirectory() as tmp:
        active_path = _write_active(Path(tmp), [])
        result = _get_active_brains(search_paths=[active_path])
    assert result == set()


def test_get_active_brains_corrupt_json_returns_none():
    """Corrupt active.json = graceful fallback to None."""
    from td_mcp.tool_registry import _get_active_brains

    with tempfile.TemporaryDirectory() as tmp:
        active_path = Path(tmp) / "data" / "brains" / "active.json"
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text("NOT JSON")
        result = _get_active_brains(search_paths=[active_path])
    assert result is None


def test_brain_is_active_helper():
    """brain_is_active() returns True when brain is in active set or active is None."""
    from td_mcp.tool_registry import brain_is_active

    assert brain_is_active(None, "derivative") is True
    assert brain_is_active({"derivative"}, "derivative") is True
    assert brain_is_active({"derivative"}, "popx") is False
    assert brain_is_active(set(), "derivative") is False
