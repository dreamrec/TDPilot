"""Tests for vision diagnostic tools 76-77 (td_capture_frame, td_analyze_frame).

Uses source-file parsing to verify tool registration because the MCP resource
decorator in tool_registry has a pydantic/mcp version incompatibility that
prevents direct import in the test environment. The structural approach is
consistent with how other component extension tests work in this project.

v1.5.0 Phase 2 update: vision tools moved to
``src/td_mcp/registry/tools_vision.py``. These tests now scan
``tool_registry.py`` + all ``registry/tools_*.py`` files so the assertions
keep working whether tools live in the root or in a submodule.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as _registry
from td_mcp.registry import tools_vision

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "td_mcp"
REGISTRY_PATH = _SRC_ROOT / "tool_registry.py"
REGISTRY_PKG = _SRC_ROOT / "registry"
# models.py was split into a package — the original content now lives in models/_legacy.py.
MODELS_PATH = _SRC_ROOT / "models" / "_legacy.py"

VISION_TOOLS = {"td_capture_frame", "td_analyze_frame"}
VISION_MODELS = {"CaptureFrameInput", "AnalyzeFrameInput"}


def _registry_source() -> str:
    """Return concatenated source of tool_registry.py + registry/tools_*.py.

    After Phase 2 module split, tools live across multiple files; tests
    that want to verify "a tool is registered" or "a handler references
    endpoint X" need to see all of them.
    """
    parts = [REGISTRY_PATH.read_text()]
    if REGISTRY_PKG.is_dir():
        for sub in sorted(REGISTRY_PKG.glob("tools_*.py")):
            parts.append(sub.read_text())
    return "\n".join(parts)


def _models_source() -> str:
    return MODELS_PATH.read_text()


def test_vision_tools_registered():
    """Both vision tools must be registered via @mcp.tool(name=...) decorator."""
    source = _registry_source()
    missing = []
    for tool_name in VISION_TOOLS:
        marker = f'name="{tool_name}"'
        if marker not in source:
            missing.append(tool_name)
    assert not missing, f"Missing vision tool registrations: {sorted(missing)}"


def test_vision_models_defined():
    """CaptureFrameInput and AnalyzeFrameInput must be defined in models.py."""
    source = _models_source()
    missing = []
    for model_name in VISION_MODELS:
        if f"class {model_name}(" not in source:
            missing.append(model_name)
    assert not missing, f"Missing vision models: {sorted(missing)}"


def test_vision_models_imported_in_registry():
    """Vision models must be imported in tool_registry.py."""
    source = _registry_source()
    missing = []
    for model_name in VISION_MODELS:
        if model_name not in source:
            missing.append(model_name)
    assert not missing, f"Vision models not found in tool_registry: {sorted(missing)}"


def test_capture_frame_handler_calls_screenshot_endpoint():
    """td_capture_frame handler must call screenshot endpoint."""
    source = _registry_source()
    assert '"screenshot"' in source or "'screenshot'" in source, (
        "td_capture_frame handler does not appear to call the screenshot endpoint"
    )


def test_analyze_frame_handler_calls_analyze_frame_endpoint():
    """td_analyze_frame handler must call analyze_frame endpoint."""
    source = _registry_source()
    assert '"analyze_frame"' in source or "'analyze_frame'" in source, (
        "td_analyze_frame handler does not appear to call the analyze_frame endpoint"
    )


def test_capture_frame_input_has_required_fields():
    """CaptureFrameInput must have path, quality, confirm fields."""
    source = _models_source()
    # Find the class definition section
    start = source.find("class CaptureFrameInput(")
    assert start != -1, "CaptureFrameInput not found"
    end = source.find("\nclass ", start + 1)
    if end == -1:
        end = len(source)
    class_body = source[start:end]
    for field in ("path", "quality", "confirm"):
        assert field in class_body, f"CaptureFrameInput missing field: {field}"


def test_analyze_frame_input_has_required_fields():
    """AnalyzeFrameInput must have path, modes, roi, reference_path fields."""
    source = _models_source()
    start = source.find("class AnalyzeFrameInput(")
    assert start != -1, "AnalyzeFrameInput not found"
    end = source.find("\nclass ", start + 1)
    if end == -1:
        end = len(source)
    class_body = source[start:end]
    for field in ("path", "modes", "roi", "reference_path"):
        assert field in class_body, f"AnalyzeFrameInput missing field: {field}"


class _RecordingClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def request(self, endpoint, body):
        self.calls.append((endpoint, body))
        if endpoint == "screenshot":
            payload = {
                "success": True,
                "path": body["path"],
                "width": 320,
                "height": 180,
                "format": "jpeg",
                "size_bytes": 0 if body.get("include_data") is False else 4,
            }
            if body.get("include_data") is not False:
                payload["data_base64"] = "ZmFrZQ=="
            else:
                payload["data_omitted"] = True
            return payload
        if endpoint == "analyze_frame":
            return {"success": True, "path": body["path"], "modes": body["modes"]}
        raise AssertionError(endpoint)


@pytest.mark.asyncio
async def test_capture_frame_omits_image_data_at_td_endpoint_by_default(monkeypatch):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context={}))

    out = await tools_vision.td_capture_frame(ctx, path="/project1/out1")
    payload = json.loads(out)

    assert client.calls == [("screenshot", {"path": "/project1/out1", "quality": 0.8, "include_data": False})]
    assert payload["success"] is True
    assert payload["data_omitted"] is True
    assert "data_base64" not in payload


@pytest.mark.asyncio
async def test_capture_frame_confirm_requests_image_data(monkeypatch):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context={}))

    out = await tools_vision.td_capture_frame(ctx, path="/project1/out1", quality=0.6, confirm=True)
    payload = json.loads(out)

    assert client.calls == [("screenshot", {"path": "/project1/out1", "quality": 0.6, "include_data": True})]
    assert payload["data_base64"] == "ZmFrZQ=="
