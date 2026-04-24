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
