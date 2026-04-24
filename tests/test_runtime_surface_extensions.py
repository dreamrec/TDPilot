from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as registry
from td_mcp.models import (
    CustomParametersInput,
    CustomParameterSpec,
    POPInspectInput,
)


def _make_ctx():
    lifespan_state = {"services": object()}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


class _RecordingClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def request(self, endpoint: str, body: dict | None = None):
        payload = body or {}
        self.calls.append((endpoint, payload))
        return {"success": True, "endpoint": endpoint, "payload": payload}


@pytest.mark.asyncio
async def test_new_surface_tools_forward_to_expected_endpoints(monkeypatch):
    client = _RecordingClient()
    ctx = _make_ctx()
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    custom_payload = await registry.td_custom_parameters(
        CustomParametersInput(
            path="/project1/base1",
            page="Controls",
            params=[CustomParameterSpec(kind="float", name="gain", default=0.5)],
        ),
        ctx,
    )
    pop_payload = await registry.td_pop_inspect(
        POPInspectInput(path="/project1/particles1", point_attributes=["P"], count=8),
        ctx,
    )
    # Post-Bug-A (v1.5.0 batch 2) signature: ctx first, then explicit action arg.
    project_payload = await registry.td_project_lifecycle(
        ctx,
        action="status",
    )

    assert json.loads(custom_payload)["endpoint"] == "custom-parameters"
    assert json.loads(pop_payload)["endpoint"] == "pop/inspect"
    assert json.loads(project_payload)["endpoint"] == "project/lifecycle"

    assert client.calls[0][0] == "custom-parameters"
    assert client.calls[1][0] == "pop/inspect"
    assert client.calls[2][0] == "project/lifecycle"
