import json

import pytest

from td_mcp import tool_registry
from td_mcp.models import CaptureAndAnalyzeInput


class _DummyRequestContext:
    lifespan_context = {}


class _DummyContext:
    request_context = _DummyRequestContext()


@pytest.mark.asyncio
async def test_capture_and_analyze_requires_explicit_confirmation():
    # Post-Bug-A (v1.5.0 batch 5) signature: ctx first, then explicit args.
    result = await tool_registry.td_capture_and_analyze(
        _DummyContext(),
        path="/project1/out1",
    )
    payload = json.loads(result)

    assert payload["success"] is False
    assert payload["requires_confirmation"] is True
    assert "confirm_image_capture=true" in payload["next_step"]


def test_capture_and_analyze_confirmation_flag_defaults_false():
    params = CaptureAndAnalyzeInput(path="/project1/out1")
    assert params.confirm_image_capture is False


class _RecordingClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def request(self, endpoint, body):
        self.calls.append((endpoint, body))
        if endpoint == "screenshot":
            return {
                "success": True,
                "path": body["path"],
                "format": "jpeg",
                "data_base64": "ZmFrZQ==",
                "size_bytes": 4,
            }
        if endpoint == "analyze_frame":
            return {
                "success": True,
                "path": body["path"],
                "results": {"luminance": {"mean": 0.5}},
            }
        raise AssertionError(endpoint)


@pytest.mark.asyncio
async def test_capture_and_analyze_runs_td_pixel_analysis(monkeypatch):
    client = _RecordingClient()
    monkeypatch.setattr(tool_registry, "_get_client", lambda _ctx: client)

    result = await tool_registry.td_capture_and_analyze(
        _DummyContext(),
        path="/project1/out1",
        quality=0.4,
        confirm_image_capture=True,
        analyze=True,
        analysis_prompt="is it bright?",
    )
    payload = json.loads(result)

    assert client.calls[0] == ("screenshot", {"path": "/project1/out1", "quality": 0.4, "include_data": True})
    assert client.calls[1] == (
        "analyze_frame",
        {"path": "/project1/out1", "modes": ["histogram", "luminance", "alpha_coverage"]},
    )
    assert payload["analysis"]["status"] == "ok"
    assert payload["analysis"]["prompt"] == "is it bright?"
    assert payload["analysis"]["result"]["results"]["luminance"]["mean"] == 0.5
