"""Shared pytest fixtures for TDPilot tests.

Centralizes the patterns that were previously re-defined in half a dozen
files: a fake TDClient that records requests, a ServiceContainer factory,
and a mock MCP Context wired to a lifespan state dict.

Keep this file small — specialized fakes (POP-inspect, brain-search, etc.)
still belong in the test files that own them. These fixtures cover the
shared ~80% case: "give me something that quacks like TDClient + Context".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest


@dataclass
class RecordingTDClient:
    """A TDClient-shaped stub that records every ``request()`` call.

    Configure ``responses`` as a dict of ``endpoint -> response`` to return
    canned payloads, or pass a ``handler`` callable for dynamic responses.
    Unconfigured endpoints return ``{}``.
    """

    responses: dict[str, Any] = field(default_factory=dict)
    handler: Callable[[str, dict[str, Any]], Any] | None = None
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    last_body: dict[str, Any] | None = None
    last_endpoint: str | None = None

    async def request(self, endpoint: str, body: dict[str, Any] | None = None) -> Any:
        body = body or {}
        self.calls.append((endpoint, body))
        self.last_body = body
        self.last_endpoint = endpoint
        if self.handler is not None:
            return self.handler(endpoint, body)
        if endpoint in self.responses:
            return self.responses[endpoint]
        return {}

    @property
    def last_code(self) -> str | None:
        """For 'exec' endpoint bodies, return the 'code' field."""
        return self.last_body.get("code") if self.last_body else None

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok"}

    async def close(self) -> None:
        return None


@pytest.fixture
def td_client() -> RecordingTDClient:
    """Provide a fresh RecordingTDClient for each test."""
    return RecordingTDClient()


@pytest.fixture
def service_container(td_client: RecordingTDClient):
    """A ServiceContainer with just enough wiring for tool-registry tests.

    Built lazily so tests that don't touch services don't pay the import cost.
    """
    from td_mcp.services import ServiceContainer  # local import: avoids circulars

    return ServiceContainer(
        td_client=td_client,
        technique_store=None,
        preference_store=None,
    )


@pytest.fixture
def mcp_ctx(service_container):
    """A Context-shaped SimpleNamespace pointing at the ServiceContainer."""
    lifespan_state = {"services": service_container}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


@pytest.fixture
def exec_client_factory():
    """Factory returning a RecordingTDClient pre-wired for the /exec endpoint.

    Usage:
        def test_foo(exec_client_factory):
            client = exec_client_factory({"path": "/comp", "issues": []})
            ...

    The exec endpoint wraps the dict in the JSON-string envelope TD returns.
    """
    import json as _json

    def _make(exec_result: Any) -> RecordingTDClient:
        return RecordingTDClient(
            responses={
                "exec": {"result": _json.dumps(exec_result)},
                "project/lifecycle": {"ok": True},
            }
        )

    return _make
