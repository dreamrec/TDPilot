"""Vision tools — frame capture + pixel analysis.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module:
    td_capture_frame   — single-frame capture with base64-on-confirm
    td_analyze_frame   — server-side pixel analysis (histogram, luminance,
                          alpha_coverage, color_dominant, roi_diff)
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402
from td_mcp.vision.save_path import SavePathError, validate_save_path


@mcp.tool(name="td_capture_frame")
async def td_capture_frame(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a TOP node to capture"),
    ],
    quality: Annotated[
        float,
        Field(
            default=0.8,
            ge=0.0,
            le=1.0,
            description="JPEG quality 0.0-1.0",
        ),
    ] = 0.8,
    confirm: Annotated[
        bool,
        Field(
            default=False,
            description="If True, include base64 image in response",
        ),
    ] = False,
    save_path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional disk destination. When set, TouchDesigner writes the "
                "frame to this path and the tool returns metadata + the saved "
                "path with NO base64 payload (overrides confirm). Accepts an "
                "absolute path under your home directory or a bare filename "
                "(saved under ~/.tdpilot/captures/). Extension must be "
                ".png/.jpg/.jpeg."
            ),
        ),
    ] = None,
) -> str:
    """Capture a single frame from a TOP node and return metadata.

    Returns resolution, format, and byte size. If save_path is set the frame
    is written to disk TD-side and only metadata + the saved path come back —
    the cheap visual-verify loop. Otherwise, if confirm=True, the response
    includes the base64-encoded JPEG image data. Ask the user before setting
    confirm=True because image payloads consume significant model context
    tokens.
    """
    finish = _tr._start_tool(ctx, "td_capture_frame")
    try:
        body: dict[str, Any] = {"path": path, "quality": quality}
        if save_path is not None:
            try:
                body["save_path"] = validate_save_path(save_path)
            except SavePathError as exc:
                return format_tool_error(exc)
            body["include_data"] = False
        else:
            body["include_data"] = bool(confirm)
        client = _tr._get_client(ctx)
        data = await client.request("screenshot", body)
        if isinstance(data, dict) and data.get("success"):
            result: dict[str, Any] = {
                "success": True,
                "path": data.get("path", path),
                "resolution": [
                    data.get("width", 0),
                    data.get("height", 0),
                ],
                "format": data.get("format", "jpeg"),
                "size_bytes": data.get("size_bytes", 0),
                "quality": quality,
            }
            if save_path is not None:
                result["data_omitted"] = True
                result["saved_to"] = data.get("saved_to", body["save_path"])
            elif confirm:
                result["data_base64"] = data.get("data_base64", "")
            else:
                result["data_omitted"] = True
                result["note"] = (
                    "Set confirm=True to include base64 image data (or pass "
                    "save_path to write to disk with no token cost). "
                    "Each JPEG frame adds significant token cost."
                )
            return _tr._as_json_output(result)
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_capture_frame")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_analyze_frame")
async def td_analyze_frame(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a TOP node to analyze"),
    ],
    modes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Analysis modes: histogram, luminance, alpha_coverage, "
                "color_dominant, roi_diff. Defaults to "
                "['histogram', 'luminance'] when omitted."
            ),
        ),
    ] = None,
    roi: Annotated[
        list[int] | None,
        Field(
            default=None,
            description="Region of interest [x, y, w, h] for roi_diff mode",
        ),
    ] = None,
    reference_path: Annotated[
        str | None,
        Field(
            default=None,
            description="Reference TOP path for roi_diff mode",
        ),
    ] = None,
    sample_grid: Annotated[
        int,
        Field(
            default=20,
            ge=2,
            le=128,
            description="Grid size used by TD-side sample() fallback and normalized quality metrics.",
        ),
    ] = 20,
    thresholds: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Optional visual-quality threshold overrides.",
        ),
    ] = None,
    quality_mode: Annotated[
        bool,
        Field(
            default=True,
            description="If True, include normalized visual-quality metrics in the TD response.",
        ),
    ] = True,
) -> str:
    """Analyze pixel data of a TOP node without transferring full image data.

    Runs server-side numpy analysis inside TouchDesigner and returns statistical
    results per requested mode. Supported modes:
    - histogram: per-channel (RGB) pixel value histograms
    - luminance: mean, min, max, std, p5, p95 of perceived luminance
    - alpha_coverage: alpha channel statistics (requires RGBA TOP)
    - color_dominant: most frequent quantized color in the frame
    - roi_diff: pixel-level diff between a region and a reference TOP

    For roi_diff, also pass roi=[x, y, w, h] and reference_path.
    """
    finish = _tr._start_tool(ctx, "td_analyze_frame")
    try:
        client = _tr._get_client(ctx)
        body: dict[str, Any] = {
            "path": path,
            "modes": modes or ["histogram", "luminance"],
            "sample_grid": sample_grid,
            "thresholds": thresholds,
            "quality_mode": quality_mode,
        }
        if roi is not None:
            body["roi"] = roi
        if reference_path is not None:
            body["reference_path"] = reference_path
        data = await client.request("analyze_frame", body)
        return _tr._as_json_output(data)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_analyze_frame")
        return format_tool_error(exc)
    finally:
        finish()
