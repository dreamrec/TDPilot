"""Integration test: ``_forward()`` auto-attaches read_journal hints.

Confirms that the wiring inside ``tool_registry._forward`` actually runs the
journal on every dispatched call, and that the hint shows up in the JSON
response without changing the rest of the envelope.

Uses the monkeypatch + lambda-client pattern from
``test_runtime_surface_extensions.py`` to bypass the TDClient isinstance
guard in ``_get_client``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as registry
from td_mcp import read_journal


def _make_ctx() -> SimpleNamespace:
    lifespan_state = {"services": object()}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


class _ScriptableClient:
    """Per-call response scripting so we can simulate scene mutation."""

    def __init__(self):
        self.next_response: object = {}

    async def request(self, endpoint: str, body: dict | None = None):
        return self.next_response


@pytest.fixture(autouse=True)
def _reset_journal():
    read_journal.reset()
    yield
    read_journal.reset()


@pytest.mark.asyncio
async def test_forward_injects_read_journal_hint(monkeypatch):
    """First call: hint shows call_count=1, result_unchanged=None."""
    client = _ScriptableClient()
    client.next_response = {"nodes": [{"name": "geo1"}]}
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    output = await registry._forward(
        _make_ctx(),
        "td_get_nodes",
        "nodes/list",
        {"path": "/project1"},
    )

    parsed = json.loads(output)
    assert parsed["nodes"] == [{"name": "geo1"}]
    assert "_read_journal" in parsed
    assert parsed["_read_journal"]["call_count"] == 1
    assert parsed["_read_journal"]["result_unchanged"] is None


@pytest.mark.asyncio
async def test_forward_repeat_call_marks_unchanged(monkeypatch):
    """Repeat call with same args + same TD response: result_unchanged=True."""
    client = _ScriptableClient()
    client.next_response = {"nodes": [{"name": "geo1"}]}
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    ctx = _make_ctx()
    await registry._forward(ctx, "td_get_nodes", "nodes/list", {"path": "/project1"})
    second = await registry._forward(ctx, "td_get_nodes", "nodes/list", {"path": "/project1"})

    parsed = json.loads(second)
    assert parsed["_read_journal"]["call_count"] == 2
    assert parsed["_read_journal"]["result_unchanged"] is True


@pytest.mark.asyncio
async def test_forward_repeat_call_with_changed_data_marks_changed(monkeypatch):
    """Repeat call with same args but different TD response: result_unchanged=False."""
    client = _ScriptableClient()
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    ctx = _make_ctx()
    client.next_response = {"nodes": [{"name": "geo1"}]}
    await registry._forward(ctx, "td_get_nodes", "nodes/list", {"path": "/project1"})

    client.next_response = {"nodes": [{"name": "geo1"}, {"name": "geo2"}]}
    second = await registry._forward(ctx, "td_get_nodes", "nodes/list", {"path": "/project1"})

    parsed = json.loads(second)
    assert parsed["_read_journal"]["call_count"] == 2
    assert parsed["_read_journal"]["result_unchanged"] is False


@pytest.mark.asyncio
async def test_forward_error_path_does_not_record(monkeypatch):
    """When TD raises, journal must not record a phantom successful call."""

    class _BoomClient:
        async def request(self, endpoint, body=None):
            raise RuntimeError("td gone away")

    monkeypatch.setattr(registry, "_get_client", lambda _ctx: _BoomClient())

    await registry._forward(
        _make_ctx(),
        "td_get_nodes",
        "nodes/list",
        {"path": "/project1"},
    )

    assert read_journal.snapshot() == []
