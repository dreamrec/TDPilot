"""Streaming + capture-and-analyze tools.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module (5):
    td_capture_and_analyze   — single screenshot + optional AI analysis
    td_monitor_visual        — periodic capture loop (low token cost)
    td_stop_monitor_visual   — stop a running monitor
    td_stream_top            — continuous TOP stream (high-fidelity)
    td_stop_stream_top       — stop a running stream

All gate base64 frame payloads behind ``include_image`` +
``confirm_high_token_mode`` to avoid silent token blow-ups.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.capabilities import detect_capabilities
from td_mcp.errors import format_tool_error
from td_mcp.events.uri import top_frame_uri
from td_mcp.tool_registry import TD_STREAM_MAX_FPS, mcp  # noqa: E402


@mcp.tool(name="td_capture_and_analyze")
async def td_capture_and_analyze(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to TOP node to capture."),
    ],
    quality: Annotated[
        float,
        Field(default=0.5, ge=0.0, le=1.0, description="JPEG quality 0.0-1.0."),
    ] = 0.5,
    confirm_image_capture: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Must be true to execute the capture. "
                "This is an explicit acknowledgement that image payloads can "
                "consume tokens."
            ),
        ),
    ] = False,
    analyze: Annotated[
        bool,
        Field(
            default=False,
            description="Request AI analysis if sampling is supported.",
        ),
    ] = False,
    analysis_prompt: Annotated[
        str | None,
        Field(default=None, description="Custom analysis prompt."),
    ] = None,
    compare_with: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional resource URI to compare against.",
        ),
    ] = None,
) -> str:
    """Screenshot capture with optional AI analysis."""
    finish = _tr._start_tool(ctx, "td_capture_and_analyze")
    try:
        if not confirm_image_capture:
            return _tr._capture_confirmation_required_response()

        screenshot = await _tr._get_client(ctx).request(
            "screenshot",
            {
                "path": path,
                "quality": quality,
            },
        )

        capabilities = detect_capabilities(ctx)
        analysis = None

        if analyze:
            if capabilities.supports_sampling:
                analysis = {
                    "status": "not_implemented",
                    "message": "Sampling capability detected but this runtime does not expose a sampling API.",
                    "prompt": analysis_prompt,
                }
            else:
                analysis = {
                    "status": "unsupported",
                    "message": "Client sampling capability not available.",
                }

        payload = {
            "schema_version": 1,
            "capture": screenshot,
            "analysis": analysis,
            "compare_with": compare_with,
            "token_notice": {
                "advice": (
                    "Image payloads include base64 data and can consume many tokens when repeated. "
                    "Ask the user before running capture loops."
                ),
                "ask_user_prompt": (
                    "Do you want me to inspect output frames now? "
                    "I can do one screenshot first to keep token usage low."
                ),
            },
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_capture_and_analyze")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_monitor_visual")
async def td_monitor_visual(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TOP path to monitor."),
    ],
    interval: Annotated[
        float,
        Field(
            default=2.0,
            ge=0.5,
            le=30.0,
            description="Capture interval seconds.",
        ),
    ] = 2.0,
    quality: Annotated[
        float,
        Field(default=0.3, ge=0.0, le=1.0, description="JPEG quality."),
    ] = 0.3,
    include_image: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "When false (default), monitor events omit base64 image "
                "data to reduce token usage. Set true only when you "
                "explicitly want frame payloads in context."
            ),
        ),
    ] = False,
    confirm_high_token_mode: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Must be true when include_image=true. This is an explicit "
                "acknowledgement that continuous image payloads can consume "
                "many tokens."
            ),
        ),
    ] = False,
    auto_analyze: Annotated[
        bool,
        Field(
            default=False,
            description=("Auto analyze each capture if sampling available."),
        ),
    ] = False,
    analysis_prompt: Annotated[
        str | None,
        Field(default=None, description="Optional analysis prompt."),
    ] = None,
) -> str:
    """Start periodic monitor for a TOP.

    Default mode omits base64 frames to keep token usage low.
    """
    finish = _tr._start_tool(ctx, "td_monitor_visual")
    try:
        if include_image and not confirm_high_token_mode:
            return _tr._vision_confirmation_required_response()

        monitor = _tr._get_visual_monitor(ctx)
        config = await monitor.start_monitor(
            path=path,
            interval=interval,
            quality=quality,
            include_image=include_image,
        )

        payload = {
            "success": True,
            "monitor": config,
            "resource_uri": top_frame_uri(path),
            "active_monitors": monitor.active_monitors(),
            "token_notice": _tr._vision_token_notice(include_image),
        }

        if auto_analyze:
            payload["note"] = (
                "auto_analyze requested; monitor captures are active but auto sampling is not implemented in this runtime."
            )

        _tr._audit_log(
            ctx,
            "td_monitor_visual",
            {
                "path": path,
                "interval": interval,
                "quality": quality,
                "include_image": include_image,
                "confirm_high_token_mode": confirm_high_token_mode,
            },
        )
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_monitor_visual")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_stop_monitor_visual")
async def td_stop_monitor_visual(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TOP path being monitored."),
    ],
) -> str:
    """Stop a running visual monitor."""
    finish = _tr._start_tool(ctx, "td_stop_monitor_visual")
    try:
        monitor = _tr._get_visual_monitor(ctx)
        stopped = await monitor.stop_monitor(path)
        payload = {
            "success": stopped,
            "path": path,
            "active_monitors": monitor.active_monitors(),
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_stop_monitor_visual")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_stream_top")
async def td_stream_top(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TOP path to stream continuously."),
    ],
    fps: Annotated[
        float,
        Field(
            default=8.0,
            ge=0.5,
            le=60.0,
            description="Target stream frame rate.",
        ),
    ] = 8.0,
    quality: Annotated[
        float,
        Field(
            default=0.25,
            ge=0.0,
            le=1.0,
            description="JPEG quality for stream frames.",
        ),
    ] = 0.25,
    include_image: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "When false (default), streamed resource updates omit "
                "base64 image data to reduce token usage. Set true only "
                "when you explicitly want frame payloads in context."
            ),
        ),
    ] = False,
    confirm_high_token_mode: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Must be true when include_image=true. This is an explicit "
                "acknowledgement that continuous image payloads can consume "
                "many tokens."
            ),
        ),
    ] = False,
    emit_unchanged: Annotated[
        bool,
        Field(
            default=False,
            description=("When false, identical consecutive frames are suppressed."),
        ),
    ] = False,
) -> str:
    """Start continuous TOP stream.

    Default mode omits base64 frames to keep token usage low.
    """
    finish = _tr._start_tool(ctx, "td_stream_top")
    try:
        if include_image and not confirm_high_token_mode:
            return _tr._vision_confirmation_required_response()

        streamer = _tr._get_top_streamer(ctx)
        normalized_fps = max(0.5, min(float(fps), TD_STREAM_MAX_FPS))
        config = await streamer.start_stream(
            path=path,
            fps=normalized_fps,
            quality=quality,
            include_image=include_image,
            emit_unchanged=emit_unchanged,
        )
        payload = {
            "success": True,
            "stream": config,
            "resource_uri": top_frame_uri(path),
            "active_streams": streamer.active_streams(),
            "token_notice": _tr._vision_token_notice(include_image),
            "limits": {
                "requested_fps": fps,
                "applied_fps": normalized_fps,
                "max_fps": TD_STREAM_MAX_FPS,
            },
        }
        _tr._audit_log(
            ctx,
            "td_stream_top",
            {
                "path": path,
                "fps": normalized_fps,
                "quality": quality,
                "include_image": include_image,
                "confirm_high_token_mode": confirm_high_token_mode,
                "emit_unchanged": emit_unchanged,
            },
        )
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_stream_top")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_stop_stream_top")
async def td_stop_stream_top(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TOP path being streamed."),
    ],
) -> str:
    """Stop a running TOP stream."""
    finish = _tr._start_tool(ctx, "td_stop_stream_top")
    try:
        streamer = _tr._get_top_streamer(ctx)
        stopped = await streamer.stop_stream(path)
        payload = {
            "success": stopped,
            "path": path,
            "active_streams": streamer.active_streams(),
            "stats": streamer.stats(),
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_stop_stream_top")
        return format_tool_error(exc)
    finally:
        finish()
