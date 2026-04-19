"""Sanity tests for the shared fixtures in conftest.py.

Per audit B-1, the conftest fixtures had 0 callers outside conftest itself.
These tests both exercise the fixtures (proving they work) and serve as a
reference for new tests that want to adopt them.
"""

from __future__ import annotations

import asyncio


def test_td_client_fixture_records_calls(td_client):
    """RecordingTDClient captures endpoint + body of every request()."""

    async def run():
        result = await td_client.request("info", {"path": "/project1"})
        assert result == {}
        await td_client.request("nodes", {"path": "/project1"})

    asyncio.run(run())
    assert len(td_client.calls) == 2
    assert td_client.calls[0][0] == "info"
    assert td_client.calls[0][1] == {"path": "/project1"}
    assert td_client.last_endpoint == "nodes"


def test_td_client_responds_with_configured_payload(td_client):
    """Configured responses dict returns the right payload per endpoint."""
    td_client.responses["info"] = {"version": "099", "build": "2025.32460"}

    async def run():
        return await td_client.request("info")

    got = asyncio.run(run())
    assert got["build"] == "2025.32460"


def test_mcp_ctx_exposes_service_container(mcp_ctx, service_container, td_client):
    """mcp_ctx wires service_container into lifespan_state for tools to find."""
    # Both the lifespan_state dict and the service_container carry the same td_client.
    services = mcp_ctx.request_context.lifespan_state["services"]
    assert services is service_container
    assert services.td_client is td_client


def test_exec_client_factory_wraps_payload_in_json_envelope(exec_client_factory):
    """The factory pre-wires the /exec endpoint with TD's JSON-string envelope."""
    client = exec_client_factory({"path": "/project1/comp1", "issues": []})

    async def run():
        return await client.request("exec", {"code": "return 1"})

    got = asyncio.run(run())
    import json

    inner = json.loads(got["result"])
    assert inner == {"path": "/project1/comp1", "issues": []}
    assert client.last_code == "return 1"
