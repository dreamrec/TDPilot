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
