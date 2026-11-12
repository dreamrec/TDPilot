"""Shared fixtures for patch/* unit tests."""

from __future__ import annotations

import pytest


class FakeTDClient:
    """Records every request() call; scripted responses per endpoint.

    scripted = {
      "nodes": {...}                       # returns dict unchanged
      "node/create": Exception("boom")      # raises
      "node/create": lambda params: {...}   # computed from call params
    }
    """

    def __init__(self, scripted: dict | None = None) -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.scripted = scripted or {}

    async def request(self, endpoint: str, params: dict | None = None):
        self.calls.append((endpoint, params))
        if endpoint in self.scripted:
            resp = self.scripted[endpoint]
            if isinstance(resp, BaseException):
                raise resp
            if callable(resp):
                return resp(params or {})
            return resp
        return {}


@pytest.fixture
def fake_td():
    return FakeTDClient()


class GuardedUndoTDClient(FakeTDClient):
    """Model a server with genuinely sealed owned undo blocks for rollback tests."""

    def __init__(self, scripted=None):
        super().__init__(scripted)
        self.undo_stack = []

    async def request(self, endpoint, params=None):
        response = await super().request(endpoint, params)
        if endpoint != "project/lifecycle":
            return response
        action = (params or {}).get("action")
        if action == "start_undo_block":
            self.undo_stack.insert(0, params["name"])
        elif action == "undo":
            assert params["expected_undo_stack"] == self.undo_stack
            assert params["expected_undo_label"] == self.undo_stack[0]
            self.undo_stack.pop(0)
        return {
            "success": True,
            "undo": {"guardedUndo": True, "undoStack": list(self.undo_stack)},
            **response,
        }
