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

from pathlib import Path

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
