#!/usr/bin/env python3
"""Tool registry and runtime lifecycle for TouchDesigner MCP."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import statistics
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from td_mcp import exec_safety
from td_mcp import normalize_transport as _normalize_transport
from td_mcp.audit import AuditLogger
from td_mcp.capabilities import detect_capabilities
from td_mcp.errors import format_tool_error
from td_mcp.events import EventManager
from td_mcp.events.uri import (
    chop_uri,
    cook_uri,
    decode_td_path,
    error_uri,
    par_uri,
    top_frame_uri,
)
from td_mcp.jobs import JobManager
from td_mcp.knowledge.freshness import Provenance
from td_mcp.macros import MacroEngine
from td_mcp.memory import PreferenceStore, SnapshotManager, TechniqueStore
from td_mcp.memory.analyzer import analyze_network
from td_mcp.models import (
    AdjustableParamInput,
    AnalyzeFrameInput,
    AuditProjectInput,
    CaptureAndAnalyzeInput,
    CaptureFrameInput,
    CHOPDataInput,
    ClearBoundsInput,
    ColorPipelineInput,
    ComponentStandardizeInput,
    ConnectNodesInput,
    CookingInfoInput,
    CopyNodeInput,
    CreateMacroInput,
    CreateNodeInput,
    CustomParametersInput,
    DeleteNodeInput,
    DetectInstabilityInput,
    DiffSnapshotsInput,
    DisconnectInput,
    ExecPythonInput,
    ExplainBetterWayInput,
    FindOfficialExampleInput,
    GeometryDataInput,
    GetContentInput,
    GetErrorsInput,
    GetEventsInput,
    GetMacroParamsInput,
    GetNodesInput,
    GetParamsInput,
    ListSnapshotsInput,
    MemoryExportInput,
    MemoryFavoriteInput,
    MemoryImportInput,
    MemoryLearnInput,
    MemoryListInput,
    MemoryPreferencesInput,
    MemoryPromoteInput,
    MemoryRecallInput,
    MemoryReplayInput,
    MemorySaveInput,
    NodePathInput,
    OptimizeVisualInput,
    PlanPatchInput,
    POPInspectInput,
    PreflightPatchInput,
    ProjectLifecycleInput,
    PulseParamInput,
    PythonHelpInput,
    RecommendOfficialInput,
    RenameNodeInput,
    ResponseFormat,
    RestoreSnapshotInput,
    ScreenshotInput,
    SearchNodesInput,
    SetBoundsInput,
    SetContentInput,
    SetParamsInput,
    SnapshotInput,
    StateVectorInput,
    StopMonitorInput,
    StopStreamTopInput,
    StreamTopInput,
    SubscribeInput,
    TDResourcesInspectInput,
    TemporalAnalysisInput,
    TimelineSetInput,
    TimescaleStateInput,
    UnsubscribeInput,
    ValidateRecipeInput,
    VisualMonitorInput,
)
from td_mcp.safety import SafetyManager
from td_mcp.services import ServiceContainer
from td_mcp.td_client import TDClient, TouchDesignerConnectionError
from td_mcp.telemetry import TelemetryCollector
from td_mcp.vision import TopStreamer, VisualMonitor

logger = logging.getLogger("td_mcp")


def _read_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _read_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_exec_mode(value: str) -> str:
    """Deprecated: use td_mcp.exec_safety.normalize_mode."""
    return exec_safety.normalize_mode(value)


TD_HOST = os.environ.get("TD_MCP_HOST", "127.0.0.1")
TD_PORT = _read_int_env("TD_MCP_PORT", 9981)
TD_SCHEME = os.environ.get("TD_MCP_SCHEME", "http")
TD_WS_PORT = _read_int_env("TD_MCP_WS_PORT", 9982)
TD_HTTP_HOST = os.environ.get("TD_MCP_HTTP_HOST", "127.0.0.1")
TD_HTTP_PORT = _read_int_env("TD_MCP_HTTP_PORT", 8765)
TD_TRANSPORT = _normalize_transport(os.environ.get("TD_MCP_TRANSPORT", "stdio"))
TD_EVENT_BUFFER = _read_int_env("TD_MCP_EVENT_BUFFER", 1000)
TD_CAPTURE_QUALITY = _read_float_env("TD_MCP_CAPTURE_QUALITY", 0.3)
TD_STREAM_MAX_FPS = _read_float_env("TD_MCP_STREAM_MAX_FPS", 15.0)
TD_MAX_SNAPSHOTS = _read_int_env("TD_MCP_MAX_SNAPSHOTS", 50)
TD_STATE_VECTOR_TTL = _read_float_env("TD_MCP_STATE_VECTOR_TTL", 2.0)
TD_SNAPSHOT_DIR = (os.environ.get("TD_MCP_SNAPSHOT_DIR") or "").strip() or None
TD_TEMPLATE_DIR = (os.environ.get("TD_MCP_TEMPLATE_DIR") or "").strip() or None
TD_AUDIT_LOG = (os.environ.get("TD_MCP_AUDIT_LOG") or "").strip() or None
TD_SHARED_SECRET = (os.environ.get("TD_MCP_SHARED_SECRET") or "").strip() or None
TD_EXEC_MODE = exec_safety.normalize_mode(os.environ.get("TD_MCP_EXEC_MODE", "restricted"))

# Re-export policy constants for backward compatibility with external callers.
# Prefer importing from td_mcp.exec_safety directly in new code.
RESTRICTED_IMPORT_RE = exec_safety.RESTRICTED_IMPORT_RE
RESTRICTED_TOKENS = exec_safety.RESTRICTED_TOKENS
STANDARD_ALLOWED_IMPORTS = exec_safety.STANDARD_ALLOWED_IMPORTS
STANDARD_BLOCKED_TOKENS = exec_safety.STANDARD_BLOCKED_TOKENS

_STATE_VECTOR_CACHE: dict[str, dict[str, Any]] = {}


async def _with_undo_block(td_client, label: str, async_fn, *args):
    """Wrap an async operation in a TD undo block (start_undo_block / end_undo_block)."""
    await td_client.request("project/lifecycle",
        {"action": "start_undo_block", "name": label})
    try:
        result = await async_fn(*args)
        return result
    finally:
        try:
            await td_client.request("project/lifecycle",
                {"action": "end_undo_block"})
        except Exception:
            pass


def _get_active_brains(search_paths: list[Path] | None = None) -> set[str] | None:
    """Return set of active brain IDs, or None if no active.json (load all).

    Checks paths in order:
    1. ~/.tdpilot/data/brains/active.json (installer path)
    2. <project-root>/data/brains/active.json (dev path)

    Returns None if no active.json found — caller should load all available brains.
    """
    if search_paths is None:
        search_paths = [
            Path.home() / ".tdpilot" / "data" / "brains" / "active.json",
            Path(__file__).resolve().parent.parent.parent / "data" / "brains" / "active.json",
        ]
    for candidate in search_paths:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text("utf-8"))
                return set(data.get("installed_brains", []))
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt active.json at %s, ignoring", candidate)
                return None
    return None


def brain_is_active(active_set: set[str] | None, brain_id: str) -> bool:
    """Check if a brain should be loaded. None means all brains are active."""
    if active_set is None:
        return True
    return brain_id in active_set


@asynccontextmanager
async def server_lifespan(app: FastMCP):
    """Initialize and clean up runtime services for the MCP server."""
    td_client = TDClient(
        host=TD_HOST,
        port=TD_PORT,
        shared_secret=TD_SHARED_SECRET,
        scheme=TD_SCHEME,
    )
    telemetry = TelemetryCollector()
    audit = AuditLogger(TD_AUDIT_LOG)
    macro_engine = MacroEngine(td_client=td_client, user_template_dir=TD_TEMPLATE_DIR)
    event_manager = EventManager(mcp_server=app, port=TD_WS_PORT, max_history=TD_EVENT_BUFFER)
    visual_monitor = VisualMonitor(td_client=td_client, event_manager=event_manager)
    top_streamer = TopStreamer(
        td_client=td_client,
        event_manager=event_manager,
        max_fps=TD_STREAM_MAX_FPS,
    )
    safety_manager = SafetyManager()
    snapshot_manager = SnapshotManager(
        max_snapshots=TD_MAX_SNAPSHOTS,
        storage_dir=TD_SNAPSHOT_DIR,
    )
    job_manager = JobManager(mcp_server=app)

    # Technique memory
    project_name = os.environ.get("TDPILOT_PROJECT_NAME", "")
    memory_base = os.environ.get("TDPILOT_MEMORY_DIR", "")
    technique_store = TechniqueStore(
        base_dir=memory_base or None,
        project_name=project_name or None,
    )
    preference_store = PreferenceStore(
        base_dir=memory_base or None,
        project_name=project_name or None,
    )

    logger.info("TouchDesigner MCP server starting (TD %s:%s)", TD_HOST, TD_PORT)

    td_build = ""
    try:
        await td_client.health_check()
        logger.info("TouchDesigner connection healthy")
        try:
            info = await td_client.request("info")
            td_build = str(info.get("build", "")) if isinstance(info, dict) else ""
            # --- Version negotiation ---
            # Check that the TD component version matches the MCP server version.
            if isinstance(info, dict):
                component_version = info.get("mcp_component_version") or info.get("api_version", "")
                if component_version:
                    from td_mcp import __version__ as server_version
                    if component_version != server_version:
                        logger.warning(
                            "VERSION MISMATCH: MCP server is v%s but TD component reports v%s. "
                            "Re-export the .tox from the latest TDPilot source to avoid stale tool behavior.",
                            server_version, component_version,
                        )
                    else:
                        logger.info("Version match confirmed: server and TD component both v%s", server_version)
        except Exception as exc:
            logger.debug("Could not fetch td_build at startup: %s", exc)
    except TouchDesignerConnectionError as exc:
        logger.warning("TouchDesigner not reachable at startup: %s", exc)

    try:
        await event_manager.start()
        logger.info("Event websocket listener active on ws://127.0.0.1:%s", TD_WS_PORT)
    except Exception as exc:
        logger.warning("Could not start event websocket listener on %s: %s", TD_WS_PORT, exc)

    # Knowledge corpus — gated by active.json
    active_brains = _get_active_brains()
    card_index = None
    if brain_is_active(active_brains, "derivative"):
        try:
            from td_mcp.knowledge.docsbrain import DocsBrain
            brain_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "derivative"
            db_path = brain_dir / "docsbrain.db"
            if db_path.exists():
                card_index = DocsBrain(
                    db_path=db_path,
                    changelog_path=brain_dir / "operator_changelog.json",
                    manifest_path=brain_dir / "build_manifest.json",
                )
                logger.info("DocsBrain loaded (%d chunks)", card_index.count())
        except Exception as exc:
            logger.debug("DocsBrain not available: %s", exc)

    if card_index is None:
        try:
            from td_mcp.knowledge.card_index import CardIndex
            cards_dir = Path(__file__).parent / "knowledge" / "cards"
            if cards_dir.is_dir():
                card_index = CardIndex(cards_dir)
                logger.info("Knowledge corpus loaded (%d cards)", card_index.count())
        except Exception as exc:
            logger.warning("CardIndex failed: %s", exc)

    # POPx brain — loaded only if active
    popx_brain = None
    if brain_is_active(active_brains, "popx"):
        try:
            from td_mcp.knowledge.docsbrain import DocsBrain as _PopxBrain
            popx_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "popx"
            popx_db = popx_dir / "popxbrain.db"
            if popx_db.exists():
                popx_brain = _PopxBrain(
                    db_path=popx_db,
                    changelog_path=popx_dir / "operator_changelog.json",
                    manifest_path=popx_dir / "build_manifest.json",
                )
                logger.info("POPx brain loaded (%d chunks)", popx_brain.count())
        except Exception as exc:
            logger.debug("POPx brain not available: %s", exc)

    # paketa12 tutorial brain — loaded only if active
    paketa12_brain = None
    if brain_is_active(active_brains, "paketa12"):
        try:
            from td_mcp.knowledge.docsbrain import DocsBrain as _Paketa12Brain
            p12_dir = Path(__file__).resolve().parent.parent.parent / "data" / "normalized" / "paketa12"
            p12_db = p12_dir / "paketa12brain.db"
            if p12_db.exists():
                paketa12_brain = _Paketa12Brain(
                    db_path=p12_db,
                    changelog_path=p12_dir / "operator_changelog.json",
                    manifest_path=p12_dir / "build_manifest.json",
                )
                logger.info("paketa12 brain loaded (%d chunks)", paketa12_brain.count())
        except Exception as exc:
            logger.debug("paketa12 brain not available: %s", exc)

    services = ServiceContainer(
        td_client=td_client,
        macro_engine=macro_engine,
        event_manager=event_manager,
        visual_monitor=visual_monitor,
        top_streamer=top_streamer,
        safety_manager=safety_manager,
        snapshot_manager=snapshot_manager,
        job_manager=job_manager,
        technique_store=technique_store,
        preference_store=preference_store,
        telemetry=telemetry,
        audit=audit,
        card_index=card_index,
        popx_brain=popx_brain,
        paketa12_brain=paketa12_brain,
        td_build=td_build,
    )

    try:
        yield {
            "services": services,
            "td_client": td_client,
            "macro_engine": macro_engine,
            "event_manager": event_manager,
            "visual_monitor": visual_monitor,
            "top_streamer": top_streamer,
            "safety_manager": safety_manager,
            "snapshot_manager": snapshot_manager,
            "job_manager": job_manager,
            "technique_store": technique_store,
            "preference_store": preference_store,
            "telemetry": telemetry,
            "audit": audit,
        }
    finally:
        try:
            await top_streamer.stop()
        except Exception:
            pass
        try:
            await visual_monitor.stop()
        except Exception:
            pass
        try:
            await event_manager.stop()
        except Exception:
            pass
        try:
            await job_manager.shutdown()
        except Exception:
            pass
        try:
            await td_client.close()
        except Exception:
            pass
        logger.info("TouchDesigner MCP server stopped")


mcp = FastMCP(
    "touchdesigner_mcp",
    host=TD_HTTP_HOST,
    port=TD_HTTP_PORT,
    lifespan=server_lifespan,
)


def _get_lifespan_state(ctx: Context) -> dict[str, Any]:
    # MCP Python currently exposes request-scoped startup payload as
    # `lifespan_context` (older code used `lifespan_state`).
    state = getattr(ctx.request_context, "lifespan_context", None)
    if state is None:
        state = getattr(ctx.request_context, "lifespan_state", None)
    if isinstance(state, dict):
        return state
    return {}


def _get_services(ctx: Context) -> ServiceContainer:
    state = _get_lifespan_state(ctx)
    services = state.get("services")
    if isinstance(services, ServiceContainer):
        return services
    # Fallback for old state shape.
    return ServiceContainer(
        td_client=state.get("td_client"),
        macro_engine=state.get("macro_engine"),
        event_manager=state.get("event_manager"),
        visual_monitor=state.get("visual_monitor"),
        top_streamer=state.get("top_streamer"),
        safety_manager=state.get("safety_manager"),
        snapshot_manager=state.get("snapshot_manager"),
        job_manager=state.get("job_manager"),
        telemetry=state.get("telemetry"),
        audit=state.get("audit"),
        technique_store=state.get("technique_store"),
        preference_store=state.get("preference_store"),
        card_index=state.get("card_index"),
        td_build=str(state.get("td_build", "")),
    )


def _get_client(ctx: Context) -> TDClient:
    services = _get_services(ctx)
    if not isinstance(services.td_client, TDClient):
        raise RuntimeError("TD client unavailable in lifespan state")
    return services.td_client


def _get_event_manager(ctx: Context) -> EventManager:
    services = _get_services(ctx)
    if not isinstance(services.event_manager, EventManager):
        raise RuntimeError("Event manager unavailable in lifespan state")
    return services.event_manager


def _get_macro_engine(ctx: Context) -> MacroEngine:
    services = _get_services(ctx)
    if not isinstance(services.macro_engine, MacroEngine):
        raise RuntimeError("Macro engine unavailable in lifespan state")
    return services.macro_engine


def _get_visual_monitor(ctx: Context) -> VisualMonitor:
    services = _get_services(ctx)
    if not isinstance(services.visual_monitor, VisualMonitor):
        raise RuntimeError("Visual monitor unavailable in lifespan state")
    return services.visual_monitor


def _get_top_streamer(ctx: Context) -> TopStreamer:
    services = _get_services(ctx)
    if not isinstance(services.top_streamer, TopStreamer):
        raise RuntimeError("Top streamer unavailable in lifespan state")
    return services.top_streamer


def _get_safety_manager(ctx: Context) -> SafetyManager:
    services = _get_services(ctx)
    if not isinstance(services.safety_manager, SafetyManager):
        raise RuntimeError("Safety manager unavailable in lifespan state")
    return services.safety_manager


def _get_snapshot_manager(ctx: Context) -> SnapshotManager:
    services = _get_services(ctx)
    if not isinstance(services.snapshot_manager, SnapshotManager):
        raise RuntimeError("Snapshot manager unavailable in lifespan state")
    return services.snapshot_manager


def _get_technique_store(ctx: Context) -> TechniqueStore:
    services = _get_services(ctx)
    if not isinstance(services.technique_store, TechniqueStore):
        raise RuntimeError("Technique store unavailable in lifespan state")
    return services.technique_store


def _get_preference_store(ctx: Context) -> PreferenceStore:
    services = _get_services(ctx)
    if not isinstance(services.preference_store, PreferenceStore):
        raise RuntimeError("Preference store unavailable in lifespan state")
    return services.preference_store


def _get_job_manager(ctx: Context) -> JobManager:
    services = _get_services(ctx)
    if not isinstance(services.job_manager, JobManager):
        raise RuntimeError("Job manager unavailable in lifespan state")
    return services.job_manager


def _get_telemetry(ctx: Context) -> TelemetryCollector | None:
    services = _get_services(ctx)
    return services.telemetry if isinstance(services.telemetry, TelemetryCollector) else None


def _get_audit(ctx: Context) -> AuditLogger | None:
    services = _get_services(ctx)
    return services.audit if isinstance(services.audit, AuditLogger) else None


def _start_tool(ctx: Context, tool_name: str) -> Callable[[], None]:
    telemetry = _get_telemetry(ctx)
    if telemetry is None:
        return lambda: None

    telemetry.increment("tools.calls_total")
    telemetry.increment(f"tools.{tool_name}.calls")
    return telemetry.timed(tool_name)


def _record_tool_error(ctx: Context, tool_name: str) -> None:
    telemetry = _get_telemetry(ctx)
    if telemetry is None:
        return
    telemetry.increment("tools.errors_total")
    telemetry.increment(f"tools.{tool_name}.errors")


def _invoke_with_lifecycle(tool_name, ctx, func, *args, **kwargs):
    """Runtime helper for tools that want one-line lifecycle wrapping.

    Replaces the repetitive 8-line pattern inside a tool body:

        async def td_foo(params, ctx):
            return await _invoke_with_lifecycle(
                "td_foo", ctx, _td_foo_body, params, ctx
            )

        async def _td_foo_body(params, ctx):
            data = await _get_client(ctx).request("foo", params.model_dump())
            return _as_json_output(data)

    Note: a cleaner ``@tool_lifecycle(name)`` decorator that wraps the whole
    body does NOT work with FastMCP — it reads ``inspect.get_type_hints(func)``
    to build the pydantic model, and ``from __future__ import annotations``
    turns the hints into strings that don't resolve through ``functools.wraps``.
    Refactoring to eliminate the boilerplate needs either dropping
    ``from __future__`` in this file or switching to a schema-aware wrapper
    (e.g., ``makefun``). Tracked as tech debt.
    """
    # Declared for future adoption; currently unused in favor of the inline pattern.
    raise NotImplementedError("use the inline lifecycle pattern — see docstring")


def _audit_log(ctx: Context, event: str, details: dict[str, Any]) -> None:
    audit = _get_audit(ctx)
    if audit is None:
        return
    audit.log(event, details)


def _as_json_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, default=str)


def _vision_token_notice(include_image: bool) -> dict[str, Any]:
    if include_image:
        return {
            "mode": "full_image_payloads",
            "advice": (
                "Continuous base64 frames can consume many tokens. "
                "Use this mode only after explicit user confirmation."
            ),
            "ask_user_prompt": (
                "Do you want me to inspect live output frames now? "
                "This will increase token usage."
            ),
        }

    return {
        "mode": "metadata_only",
        "advice": (
            "Base64 frame payloads are omitted to reduce token usage. "
            "Call td_screenshot for on-demand frame inspection."
        ),
        "ask_user_prompt": (
            "Do you want me to inspect the visual output now? "
            "I can fetch a frame on demand."
        ),
    }


def _vision_confirmation_required_response() -> str:
    return _as_json_output(
        {
            "success": False,
            "requires_confirmation": True,
            "message": (
                "High-token vision mode was requested (include_image=true) "
                "without explicit confirmation."
            ),
            "ask_user_prompt": (
                "Do you want me to enable continuous full-frame output now? "
                "This can increase token usage significantly."
            ),
            "next_step": (
                "After user approval, call again with confirm_high_token_mode=true."
            ),
        }
    )


def _capture_confirmation_required_response() -> str:
    return _as_json_output(
        {
            "success": False,
            "requires_confirmation": True,
            "message": (
                "Image capture was requested without explicit confirmation."
            ),
            "ask_user_prompt": (
                "Do you want me to capture and inspect output now? "
                "This will add image payload tokens."
            ),
            "next_step": (
                "After user approval, call again with confirm_image_capture=true."
            ),
        }
    )


async def _forward(
    ctx: Context,
    tool_name: str,
    endpoint: str,
    body: dict[str, Any] | None = None,
    *,
    audit_event: str | None = None,
    audit_details: dict[str, Any] | None = None,
) -> str:
    finish = _start_tool(ctx, tool_name)
    try:
        data = await _get_client(ctx).request(endpoint, body)
        if audit_event:
            _audit_log(ctx, audit_event, audit_details or (body or {}))
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, tool_name)
        return format_tool_error(exc)
    finally:
        finish()


def _current_exec_mode() -> str:
    """Return the current exec mode, reading env at call time.

    Previously this did a ``sys.modules.get("td_mcp.server")`` lookup so tests
    could monkey-patch ``td_mcp.server.TD_EXEC_MODE``. That hack is gone —
    tests now patch ``TD_MCP_EXEC_MODE`` via env (see tests/test_exec_safety.py).
    """
    return exec_safety.read_mode_from_env(default=TD_EXEC_MODE)


def _restricted_exec_violation(code: str) -> str | None:
    return exec_safety.restricted_violation(code)


def _standard_exec_violation(code: str) -> str | None:
    return exec_safety.standard_violation(code)


def _enforce_exec_mode(code: str) -> None:
    exec_safety.enforce(code, mode=_current_exec_mode())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _apply_safety_to_set_params(
    safety_manager: SafetyManager | None,
    path: str,
    params: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Clamp/reject numeric param writes according to configured bounds."""
    if safety_manager is None:
        return dict(params), []

    adjusted: dict[str, Any] = {}
    warnings: list[str] = []

    for param_name, param_value in params.items():
        bound_key = f"{path}/{param_name}"

        if _is_number(param_value):
            new_value, warning = safety_manager.apply(bound_key, float(param_value))
            adjusted[param_name] = new_value
            if warning:
                warnings.append(warning)
            continue

        if isinstance(param_value, dict):
            copied = dict(param_value)
            maybe_val = copied.get("val")
            if _is_number(maybe_val):
                new_value, warning = safety_manager.apply(bound_key, float(maybe_val))
                copied["val"] = new_value
                if warning:
                    warnings.append(warning)
            adjusted[param_name] = copied
            continue

        adjusted[param_name] = param_value

    return adjusted, warnings


def _format_nodes_markdown(nodes: list[dict[str, Any]], title: str = "Nodes") -> str:
    if not nodes:
        return f"No {title.lower()} found."

    lines = [f"## {title} ({len(nodes)})\n"]
    for node in nodes:
        lines.append(f"- **{node.get('name', '?')}** `{node.get('path', '?')}` - {node.get('type', '?')}")
        if node.get("errors"):
            lines.append(f"  - Error: {node['errors']}")
    return "\n".join(lines)


def _format_params_markdown(parameters: dict[str, Any], path: str) -> str:
    if not parameters:
        return f"No parameters found for `{path}`."

    lines = [f"## Parameters for `{path}`\n"]
    current_page = None

    def sort_key(item: tuple[str, Any]) -> tuple[str, str]:
        name, info = item
        if not isinstance(info, dict):
            return "", name
        return str(info.get("page", "")), name

    for name, info in sorted(parameters.items(), key=sort_key):
        if not isinstance(info, dict):
            continue

        page = str(info.get("page", ""))
        if page != current_page:
            current_page = page
            lines.append(f"\n### {page or 'Default'}\n")

        value = info.get("value", "")
        default = info.get("default", "")
        label = info.get("label", name)
        marker = " (modified)" if value != default else ""
        lines.append(f"- **{label}** (`{name}`): `{value}`{marker}")

    return "\n".join(lines)


async def _collect_scene_state(
    client: TDClient,
    root_path: str,
    *,
    max_nodes: int = 1000,
) -> dict[str, Any]:
    queue = [root_path]
    visited: set[str] = set()
    nodes: dict[str, dict[str, Any]] = {}
    connection_set: set[tuple[str, str, int, int]] = set()

    while queue and len(visited) < max_nodes:
        current = queue.pop(0)
        if current in visited:
            continue

        visited.add(current)
        detail = await client.request("node/detail", {"path": current})
        if detail.get("error"):
            continue

        node_path = detail.get("path", current)
        nodes[node_path] = {
            "name": detail.get("name"),
            "type": detail.get("type"),
            "family": detail.get("family"),
            "params": detail.get("parameters", {}),
        }

        for conn in detail.get("inputs", []):
            if not isinstance(conn, dict):
                continue
            source = conn.get("from")
            target = node_path
            source_index = int(conn.get("from_index", 0) or 0)
            target_index = int(conn.get("to_index", 0) or 0)
            if isinstance(source, str) and source:
                connection_set.add((source, target, source_index, target_index))

        if detail.get("isCOMP"):
            child_offset = 0
            while len(visited) + len(queue) < max_nodes:
                children = await client.request(
                    "nodes",
                    {
                        "path": node_path,
                        "limit": 200,
                        "offset": child_offset,
                        "include_params": False,
                    },
                )
                child_nodes = children.get("nodes", []) if isinstance(children, dict) else []
                if not child_nodes:
                    break

                for child in child_nodes:
                    if not isinstance(child, dict):
                        continue
                    child_path = child.get("path")
                    if isinstance(child_path, str) and child_path and child_path not in visited:
                        queue.append(child_path)

                if not children.get("has_more"):
                    break
                child_offset += len(child_nodes)

    connections = [
        {
            "from": source,
            "to": target,
            "source_index": source_index,
            "target_index": target_index,
        }
        for source, target, source_index, target_index in sorted(connection_set)
    ]

    return {
        "snapshot_schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "root_path": root_path,
        "nodes": nodes,
        "connections": connections,
        "truncated": bool(queue),
        "captured_nodes": len(nodes),
    }


async def _capture_snapshot_payload(
    ctx: Context,
    *,
    path: str,
    include_visual: bool,
) -> dict[str, Any]:
    client = _get_client(ctx)
    return await _capture_snapshot_payload_for_client(
        client,
        path=path,
        include_visual=include_visual,
    )


async def _capture_snapshot_payload_for_client(
    client: TDClient,
    *,
    path: str,
    include_visual: bool,
) -> dict[str, Any]:
    scene = await _collect_scene_state(client, path)

    if include_visual:
        try:
            visual = await client.request(
                "screenshot",
                {
                    "path": path,
                    "quality": max(0.0, min(1.0, TD_CAPTURE_QUALITY)),
                },
            )
            scene["visual"] = {
                "path": visual.get("path", path),
                "format": visual.get("format", "jpeg"),
                "size_bytes": visual.get("size_bytes"),
                "data_base64": visual.get("data_base64"),
            }
        except Exception as exc:
            scene["visual_error"] = str(exc)

    return scene


def _extract_restore_values(node_snapshot: dict[str, Any]) -> dict[str, Any]:
    params = node_snapshot.get("params", node_snapshot.get("parameters", {}))
    if not isinstance(params, dict):
        return {}

    result: dict[str, Any] = {}
    for name, info in params.items():
        if not isinstance(name, str):
            continue
        if isinstance(info, dict) and "value" in info:
            result[name] = info.get("value")
    return result


def _build_subscription_resource_uris(config: SubscribeInput) -> list[str]:
    uris: list[str] = []
    event_types = set(config.event_types)

    if "timeline" in event_types:
        uris.append("td://timeline/state")

    if "chop_change" in event_types:
        channels = config.channels or ["*"]
        uris.extend(chop_uri(config.path, channel) for channel in channels)

    if "par_change" in event_types:
        names = config.params or ["*"]
        uris.extend(par_uri(config.path, name) for name in names)

    if "cook_complete" in event_types:
        uris.append(cook_uri(config.path))

    if "node_error" in event_types:
        uris.append(error_uri(config.path))

    return uris


async def _safe_request(
    client: TDClient,
    endpoint: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        data = await client.request(endpoint, body)
        if isinstance(data, dict):
            return data
        return {"value": data}
    except Exception as exc:
        return {"error": str(exc)}


def _event_rate_per_sec(events: list[dict[str, Any]]) -> float:
    timestamps: list[float] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        value = event.get("timestamp")
        if isinstance(value, (int, float)):
            timestamps.append(float(value))
    if len(timestamps) < 2:
        return 0.0
    timestamps.sort()
    duration = max(0.000001, timestamps[-1] - timestamps[0])
    return len(timestamps) / duration


def _compute_timescale_from_timeline(
    timeline: dict[str, Any],
    *,
    bpm: float,
    beats_per_bar: int,
) -> dict[str, Any]:
    seconds = float(timeline.get("seconds", 0.0) or 0.0)
    fps = float(timeline.get("fps", 60.0) or 60.0)
    frame = int(timeline.get("frame", 0) or 0)

    beats_per_second = bpm / 60.0
    total_beats = seconds * beats_per_second
    beat_index = int(total_beats)
    bar_index = beat_index // beats_per_bar

    beat_phase = total_beats % 1.0
    bar_phase = (total_beats / float(beats_per_bar)) % 1.0
    phrase_bars = 8
    section_bars = 32
    arc_bars = 128
    phrase_phase = (bar_index % phrase_bars + bar_phase) / float(phrase_bars)
    section_phase = (bar_index % section_bars + bar_phase) / float(section_bars)
    arc_phase = (bar_index % arc_bars + bar_phase) / float(arc_bars)

    seconds_per_beat = 60.0 / bpm
    seconds_per_bar = seconds_per_beat * float(beats_per_bar)
    seconds_per_phrase = seconds_per_bar * float(phrase_bars)
    seconds_to_next_beat = max(0.0, seconds_per_beat * (1.0 - beat_phase))
    seconds_to_next_bar = max(0.0, seconds_per_bar * (1.0 - bar_phase))
    seconds_to_next_phrase = max(0.0, seconds_per_phrase * (1.0 - phrase_phase))

    fps_target = 60.0
    fps_health = max(0.0, min(1.0, fps / fps_target))
    collapse_risk = max(0.0, min(1.0, (30.0 - fps) / 30.0))
    plateau_risk = max(0.0, min(1.0, abs(phrase_phase - 0.5) * 0.6))

    arc_stage = "intro"
    if arc_phase >= 0.75:
        arc_stage = "release"
    elif arc_phase >= 0.5:
        arc_stage = "plateau"
    elif arc_phase >= 0.25:
        arc_stage = "build"

    return {
        "frame": frame,
        "seconds": seconds,
        "fps": fps,
        "bpm": bpm,
        "beats_per_bar": beats_per_bar,
        "beat_index": beat_index,
        "bar_index": bar_index,
        "phrase_index_8bar": bar_index // phrase_bars,
        "section_index_32bar": bar_index // section_bars,
        "arc_index_128bar": bar_index // arc_bars,
        "beat_phase": beat_phase,
        "bar_phase": bar_phase,
        "phrase_phase_8bar": phrase_phase,
        "section_phase_32bar": section_phase,
        "arc_phase_128bar": arc_phase,
        "seconds_to_next_beat": seconds_to_next_beat,
        "seconds_to_next_bar": seconds_to_next_bar,
        "seconds_to_next_phrase_8bar": seconds_to_next_phrase,
        "frames_to_next_beat": int(round(seconds_to_next_beat * fps)),
        "frames_to_next_bar": int(round(seconds_to_next_bar * fps)),
        "frames_to_next_phrase_8bar": int(round(seconds_to_next_phrase * fps)),
        "tempo_health": fps_health,
        "plateau_risk": plateau_risk,
        "collapse_risk": collapse_risk,
        "arc_stage": arc_stage,
    }


async def _build_state_vector(path: str, ctx: Context) -> dict[str, Any]:
    client = _get_client(ctx)
    manager = _get_event_manager(ctx)
    monitor = _get_visual_monitor(ctx)
    safety = _get_safety_manager(ctx)
    snapshots = _get_snapshot_manager(ctx)
    jobs = _get_job_manager(ctx)

    info, timeline, cooking, errors = await asyncio.gather(
        _safe_request(client, "info"),
        _safe_request(client, "timeline"),
        _safe_request(
            client,
            "cooking",
            {"path": path, "recurse": True, "limit": 20, "sort_by": "cookTime"},
        ),
        _safe_request(
            client,
            "node/errors",
            {"path": path, "recurse": True, "max_depth": 10},
        ),
    )

    recent_events = manager.get_recent_events(limit=200)
    subscriptions = manager.list_subscriptions()
    active_monitors = monitor.active_monitors()
    issues = errors.get("issues", []) if isinstance(errors, dict) else []
    top_nodes = cooking.get("nodes", []) if isinstance(cooking, dict) else []
    fps = float(cooking.get("fps", timeline.get("fps", 0.0)) if isinstance(cooking, dict) else 0.0)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "project": {
            "name": info.get("project_name"),
            "version": info.get("version"),
            "build": info.get("build"),
        },
        "timeline": {
            "frame": timeline.get("frame"),
            "seconds": timeline.get("seconds"),
            "fps": timeline.get("fps"),
            "playing": timeline.get("playing"),
        },
        "health": {
            "fps": fps,
            "issues_count": len(issues),
            "event_rate_per_sec": _event_rate_per_sec(recent_events),
            "unstable": fps < 30.0 or len(issues) > 0,
        },
        "performance": {
            "top_nodes": top_nodes[:10],
            "realtime": cooking.get("realTime") if isinstance(cooking, dict) else None,
        },
        "events": {
            "recent_count": len(recent_events),
            "subscriptions": len(subscriptions),
            "subscription_paths": sorted(f"{p}:{et}" for p, et in subscriptions.keys()),
        },
        "monitoring": {
            "visual_monitors": len(active_monitors),
            "visual_paths": sorted(active_monitors.keys()),
        },
        "safety": safety.stats(),
        "snapshots": snapshots.stats(),
        "jobs": jobs.stats(),
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(token in text for token in needles)


def _clamp_objective(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def _param_roles(param_name: str) -> set[str]:
    name = param_name.lower()
    roles: set[str] = set()

    if any(token in name for token in ("bright", "exposure", "gain", "amp", "opacity", "mult", "level")):
        roles.add("brightness")
    if any(token in name for token in ("contrast", "gamma", "black", "white")):
        roles.add("contrast")
    if any(token in name for token in ("noise", "seed", "detail", "octave", "jitter", "blur", "radius", "feedback")):
        roles.add("complexity")
    if any(token in name for token in ("phase", "speed", "period", "freq", "frequency", "beat", "pulse", "bpm")):
        roles.add("motion_rhythm")
    if any(token in name for token in ("feedback", "gain", "opacity", "weight", "displace", "blur", "radius")):
        roles.add("risk")

    return roles


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _optimizer_direction_for_param(param_name: str, goal_profile: dict[str, float]) -> int:
    roles = _param_roles(param_name)
    direction = 0

    if "brightness" in roles:
        direction += _sign(goal_profile.get("brightness", 0))
    if "contrast" in roles:
        direction += _sign(goal_profile.get("contrast", 0))
    if "complexity" in roles:
        direction += _sign(goal_profile.get("complexity", 0))
    if "motion_rhythm" in roles:
        direction += _sign(goal_profile.get("motion_rhythm", 0))
    if "risk" in roles:
        # Positive stability goal drives risk params downward.
        direction -= _sign(goal_profile.get("stability", 0))
        # Positive complexity goal can tolerate slightly higher risk.
        direction += _sign(goal_profile.get("complexity", 0))

    return _sign(direction)


def _optimizer_step_multiplier(profile: str) -> float:
    if profile == "conservative":
        return 0.5
    if profile == "aggressive":
        return 1.5
    return 1.0


def _normalize_unit(value: float, min_val: float, max_val: float) -> float:
    span = max_val - min_val
    if span <= 0:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / span))


def _optimizer_score(
    current_values: dict[tuple[str, str], float],
    adjustable_params: list[AdjustableParamInput],
    directions: dict[tuple[str, str], int],
    *,
    unstable: bool,
) -> float:
    scores: list[float] = []
    for adjustable in adjustable_params:
        key = (adjustable.path, adjustable.param)
        value = current_values.get(key)
        if value is None:
            continue

        direction = directions.get(key, 0)
        if direction > 0:
            target = 1.0
        elif direction < 0:
            target = 0.0
        else:
            target = 0.5

        position = _normalize_unit(value, adjustable.min_val, adjustable.max_val)
        scores.append(1.0 - abs(position - target))

    if not scores:
        return 0.0

    score = sum(scores) / len(scores)
    if unstable:
        score *= 0.6
    return max(0.0, min(1.0, score))


async def _read_adjustable_values(
    client: TDClient,
    adjustable_params: list[AdjustableParamInput],
) -> dict[tuple[str, str], float]:
    by_path: dict[str, set[str]] = {}
    for adjustable in adjustable_params:
        by_path.setdefault(adjustable.path, set()).add(adjustable.param)

    values: dict[tuple[str, str], float] = {}
    for path, param_names in by_path.items():
        payload = await _safe_request(client, "node/params", {"path": path, "names": sorted(param_names)})
        parameters = payload.get("parameters", {}) if isinstance(payload, dict) else {}
        if not isinstance(parameters, dict):
            continue

        for param_name in param_names:
            info = parameters.get(param_name)
            if not isinstance(info, dict):
                continue
            raw = info.get("value")
            if isinstance(raw, bool):
                continue
            if isinstance(raw, (int, float)):
                values[(path, param_name)] = float(raw)
                continue
            try:
                values[(path, param_name)] = float(raw)
            except Exception:
                continue

    return values


def _build_optimizer_plan(
    adjustable_params: list[AdjustableParamInput],
    current_values: dict[tuple[str, str], float],
    goal_profile: dict[str, float],
    *,
    safety_profile: str,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int]]:
    step_multiplier = _optimizer_step_multiplier(safety_profile)
    plan: list[dict[str, Any]] = []
    directions: dict[tuple[str, str], int] = {}

    for adjustable in adjustable_params:
        key = (adjustable.path, adjustable.param)
        current = current_values.get(key)
        if current is None:
            continue

        direction = _optimizer_direction_for_param(adjustable.param, goal_profile)
        directions[key] = direction
        if direction == 0:
            continue

        step = adjustable.step * step_multiplier
        proposed = current + direction * step
        clamped = max(adjustable.min_val, min(adjustable.max_val, proposed))

        if math.isclose(clamped, current, rel_tol=0.0, abs_tol=1e-9):
            continue

        plan.append(
            {
                "path": adjustable.path,
                "param": adjustable.param,
                "current": current,
                "proposed": clamped,
                "direction": direction,
                "step": step,
            }
        )

    return plan, directions


async def _apply_optimizer_plan(
    client: TDClient,
    safety_manager: SafetyManager,
    plan: list[dict[str, Any]],
) -> dict[str, Any]:
    by_path: dict[str, dict[str, Any]] = {}
    for item in plan:
        by_path.setdefault(item["path"], {})[item["param"]] = item["proposed"]

    applied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    safety_warnings: list[str] = []

    for path, params in by_path.items():
        try:
            adjusted, warnings = _apply_safety_to_set_params(safety_manager, path, params)
            safety_warnings.extend(warnings)
            await client.request("node/params/set", {"path": path, "params": adjusted})
            for name, value in adjusted.items():
                applied.append({"path": path, "param": name, "value": value})
        except Exception as exc:
            for name in params.keys():
                failed.append({"path": path, "param": name, "error": str(exc)})

    return {
        "applied": applied,
        "failed": failed,
        "safety_warnings": safety_warnings,
    }


async def _compute_instability_snapshot(client: TDClient, path: str) -> dict[str, Any]:
    cooking = await _safe_request(
        client,
        "cooking",
        {"path": path, "recurse": True, "limit": 50, "sort_by": "cookTime"},
    )
    errors = await _safe_request(
        client,
        "node/errors",
        {"path": path, "recurse": True, "max_depth": 10},
    )

    fps = float(cooking.get("fps", 0.0) or 0.0) if isinstance(cooking, dict) else 0.0
    issues = errors.get("issues", []) if isinstance(errors, dict) else []
    heavy_nodes = [
        node
        for node in (cooking.get("nodes", []) if isinstance(cooking, dict) else [])
        if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) >= 0.01
    ]
    unstable = fps < 30.0 or bool(issues) or len(heavy_nodes) >= 5

    return {
        "unstable": unstable,
        "fps": fps,
        "issues_count": len(issues),
        "heavy_nodes_count": len(heavy_nodes),
        "heavy_nodes": heavy_nodes[:10],
        "issues": issues[:20],
    }


async def _restore_snapshot_nodes(
    client: TDClient,
    safety: SafetyManager,
    snapshot_nodes: dict[str, Any],
    *,
    partial_filters: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    restored: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    warnings: list[str] = []

    filters = partial_filters or []
    for node_path, node_snapshot in snapshot_nodes.items():
        if filters and not any(node_path.startswith(prefix) for prefix in filters):
            skipped.append({"path": node_path, "reason": "filtered"})
            continue

        values = _extract_restore_values(node_snapshot if isinstance(node_snapshot, dict) else {})
        if not values:
            skipped.append({"path": node_path, "reason": "no_params"})
            continue

        adjusted, safety_warnings = _apply_safety_to_set_params(safety, node_path, values)
        warnings.extend(safety_warnings)

        if dry_run:
            restored.append(
                {
                    "path": node_path,
                    "param_count": len(adjusted),
                    "dry_run": True,
                }
            )
            continue

        try:
            await client.request("node/params/set", {"path": node_path, "params": adjusted})
            restored.append({"path": node_path, "param_count": len(adjusted)})
        except Exception as exc:
            failures.append({"path": node_path, "error": str(exc)})

    return {
        "restored": restored,
        "skipped": skipped,
        "failures": failures,
        "safety_warnings": warnings,
    }


async def _run_optimizer_iterations(
    *,
    client: TDClient,
    safety: SafetyManager,
    jobs: JobManager,
    job_id: str,
    adjustable_params: list[AdjustableParamInput],
    goal_profile: dict[str, float],
    max_iterations: int,
    convergence_threshold: float,
    safety_profile: str,
    root_path: str,
    progress_start: float = 0.0,
    progress_end: float = 1.0,
    phase_label: str = "optimize",
) -> dict[str, Any]:
    iteration_logs: list[dict[str, Any]] = []
    converged = False
    emergency_stop = False
    stop_reason = "max_iterations"
    final_score = 0.0

    if max_iterations <= 0:
        return {
            "converged": False,
            "emergency_stop": False,
            "stop_reason": "max_iterations_zero",
            "iterations": [],
            "iterations_completed": 0,
            "final_score": 0.0,
            "final_params": [],
        }

    for index in range(max_iterations):
        current_values = await _read_adjustable_values(client, adjustable_params)
        plan, directions = _build_optimizer_plan(
            adjustable_params,
            current_values,
            goal_profile,
            safety_profile=safety_profile,
        )

        if not plan:
            stop_reason = "no_adjustable_changes"
            break

        apply_result = await _apply_optimizer_plan(client, safety, plan)
        instability = await _compute_instability_snapshot(client, root_path)
        updated_values = await _read_adjustable_values(client, adjustable_params)

        final_score = _optimizer_score(
            updated_values,
            adjustable_params,
            directions,
            unstable=bool(instability["unstable"]),
        )

        entry = {
            "phase": phase_label,
            "iteration": index + 1,
            "score": final_score,
            "applied_count": len(apply_result["applied"]),
            "failed_count": len(apply_result["failed"]),
            "safety_warnings": apply_result["safety_warnings"],
            "instability": instability,
            "applied": apply_result["applied"],
            "failed": apply_result["failed"],
        }
        iteration_logs.append(entry)

        phase_progress = float(index + 1) / float(max_iterations)
        progress = progress_start + (progress_end - progress_start) * phase_progress
        jobs.update_job(
            job_id,
            progress=max(0.0, min(1.0, progress)),
            result={
                "phase": phase_label,
                "latest_iteration": entry,
                "iterations_completed": index + 1,
            },
        )

        if instability["unstable"] and safety_profile in {"conservative", "balanced"}:
            try:
                await client.request("timeline/set", {"action": "pause"})
            except Exception:
                pass
            emergency_stop = True
            stop_reason = "instability_guard"
            break

        if final_score >= convergence_threshold:
            converged = True
            stop_reason = "converged"
            break

    final_values = await _read_adjustable_values(client, adjustable_params)
    final_params = [
        {"path": path, "param": name, "value": value}
        for (path, name), value in sorted(final_values.items())
    ]

    return {
        "converged": converged,
        "emergency_stop": emergency_stop,
        "stop_reason": stop_reason,
        "iterations": iteration_logs,
        "iterations_completed": len(iteration_logs),
        "final_score": final_score,
        "final_params": final_params,
    }


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    n = float(len(values))
    x_mean = (n - 1.0) / 2.0
    y_mean = sum(values) / n
    numerator = 0.0
    denominator = 0.0
    for i, value in enumerate(values):
        dx = float(i) - x_mean
        dy = value - y_mean
        numerator += dx * dy
        denominator += dx * dx
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


def _classify_temporal_character(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "overall_character": "static",
            "energy_level": "low",
            "predictability": "high",
            "fps_trend": "stable",
        }

    fps_values = [float(sample.get("fps", 0.0) or 0.0) for sample in samples]
    event_rates = [float(sample.get("event_rate", 0.0) or 0.0) for sample in samples]
    issue_counts = [int(sample.get("issues_count", 0) or 0) for sample in samples]
    heavy_counts = [int(sample.get("heavy_nodes_count", 0) or 0) for sample in samples]

    fps_mean = statistics.fmean(fps_values) if fps_values else 0.0
    fps_stdev = statistics.pstdev(fps_values) if len(fps_values) > 1 else 0.0
    event_mean = statistics.fmean(event_rates) if event_rates else 0.0
    issues_mean = statistics.fmean(issue_counts) if issue_counts else 0.0
    heavy_mean = statistics.fmean(heavy_counts) if heavy_counts else 0.0

    fps_slope = _linear_slope(fps_values)
    if fps_slope > 0.05:
        fps_trend = "increasing"
    elif fps_slope < -0.05:
        fps_trend = "decreasing"
    else:
        fps_trend = "stable"

    if issues_mean > 0.5 or heavy_mean > 5.0:
        overall = "chaotic"
        predictability = "low"
    elif event_mean > 8.0 and fps_stdev < 4.0:
        overall = "rhythmic"
        predictability = "medium"
    elif fps_stdev < 1.0 and event_mean < 1.0:
        overall = "static"
        predictability = "high"
    elif fps_stdev < 3.0:
        overall = "slowly_evolving"
        predictability = "high"
    else:
        overall = "transitioning"
        predictability = "medium"

    if event_mean < 1.0 and fps_stdev < 1.0:
        energy = "low"
    elif event_mean < 5.0:
        energy = "medium"
    else:
        energy = "high"

    return {
        "overall_character": overall,
        "energy_level": energy,
        "predictability": predictability,
        "fps_trend": fps_trend,
        "fps_mean": fps_mean,
        "fps_stdev": fps_stdev,
        "event_rate_mean": event_mean,
    }


# Resources


@mcp.resource("td://timeline/state", name="td_timeline_state")
async def td_resource_timeline() -> str:
    # NOTE: Context injection not supported for parameter-less resources in mcp>=1.3.
    # Clients should use the td_get_timescale_state tool for live timeline data.
    return {
        "resource_schema_version": 1,
        "resource_uri": "td://timeline/state",
        "mode": "static",
        "note": "Use td_get_timescale_state tool for live timeline data.",
    }


@mcp.resource("td://chop/path/{encoded_path}/channel/{channel}", name="td_chop_channel")
async def td_resource_chop_channel(encoded_path: str, channel: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_chop_data tool for live CHOP data.
    path = decode_td_path(encoded_path)
    uri = chop_uri(path, channel)
    try:
        pass  # read-through fallback requires context; see td_chop_data tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "channel": channel,
        "available": False,
        "note": "Use td_chop_data tool for live CHOP channel data.",
    }


@mcp.resource("td://par/path/{encoded_path}/name/{name}", name="td_parameter")
async def td_resource_parameter(encoded_path: str, name: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_get_params tool for live parameter data.
    path = decode_td_path(encoded_path)
    uri = par_uri(path, name)
    try:
        pass  # read-through fallback requires context; see td_get_params tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "name": name,
        "available": False,
        "note": "Use td_get_params tool for live parameter data.",
    }


@mcp.resource("td://cook/path/{encoded_path}", name="td_cook_state")
async def td_resource_cook(encoded_path: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_cooking_info tool for live cook data.
    path = decode_td_path(encoded_path)
    uri = cook_uri(path)
    try:
        pass  # read-through fallback requires context; see td_cooking_info tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "available": False,
        "note": "Use td_cooking_info tool for live cook state data.",
    }


@mcp.resource("td://error/path/{encoded_path}", name="td_error_state")
async def td_resource_error(encoded_path: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_get_errors tool for live error data.
    path = decode_td_path(encoded_path)
    uri = error_uri(path)
    try:
        pass  # read-through fallback requires context; see td_get_errors tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "available": False,
        "note": "Use td_get_errors tool for live error data.",
    }


@mcp.resource("td://top/path/{encoded_path}/frame", name="td_top_frame")
async def td_resource_top_frame(encoded_path: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_screenshot or td_stream_top tool for live TOP frame data.
    path = decode_td_path(encoded_path)
    uri = top_frame_uri(path)
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "available": False,
        "note": "Use td_screenshot or td_stream_top tool for live TOP frame data.",
    }


@mcp.resource("td://job/{job_id}", name="td_job_state")
async def td_resource_job(job_id: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Job state cannot be retrieved via resource; use job tracking tools.
    return {
        "resource_schema_version": 1,
        "resource_uri": f"td://job/{job_id}",
        "mode": "static",
        "job_id": job_id,
        "available": False,
        "note": "Use job tracking tools for live job state.",
    }


# Core tools (v1)


@mcp.tool(name="td_get_info")
async def td_get_info(ctx: Context) -> str:
    return await _forward(ctx, "td_get_info", "info")


@mcp.tool(name="td_list_families")
async def td_list_families(ctx: Context) -> str:
    return await _forward(ctx, "td_list_families", "families")


@mcp.tool(name="td_get_nodes")
async def td_get_nodes(params: GetNodesInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_nodes")
    try:
        data = await _get_client(ctx).request(
            "nodes",
            params.model_dump(exclude={"response_format"}, exclude_none=True),
        )
        if params.response_format == ResponseFormat.MARKDOWN:
            return _format_nodes_markdown(data.get("nodes", []), f"Children of {params.path}")
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_nodes")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_node_detail")
async def td_get_node_detail(params: NodePathInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_node_detail")
    try:
        data = await _get_client(ctx).request("node/detail", {"path": params.path})
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## {data.get('name', '?')} (`{data.get('path', '?')}`)"]
            lines.append(f"- Type: {data.get('type', '?')} ({data.get('family', '?')})")
            if data.get("errors"):
                lines.append(f"- Errors: {data['errors']}")
            if data.get("warnings"):
                lines.append(f"- Warnings: {data['warnings']}")
            if data.get("parameters"):
                lines.append(_format_params_markdown(data["parameters"], params.path))
            return "\n".join(lines)
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_node_detail")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_params")
async def td_get_params(params: GetParamsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_params")
    try:
        data = await _get_client(ctx).request(
            "node/params",
            params.model_dump(exclude={"response_format"}, exclude_none=True),
        )
        if params.response_format == ResponseFormat.MARKDOWN:
            return _format_params_markdown(data.get("parameters", {}), params.path)
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_params")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_set_params")
async def td_set_params(params: SetParamsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_set_params")
    try:
        body = params.model_dump()
        adjusted, warnings = _apply_safety_to_set_params(
            _get_safety_manager(ctx),
            params.path,
            dict(body.get("params", {})),
        )
        body["params"] = adjusted

        data = await _get_client(ctx).request("node/params/set", body)
        if warnings:
            data["safety_warnings"] = warnings

        _audit_log(
            ctx,
            "td_set_params",
            {
                "path": params.path,
                "param_count": len(adjusted),
                "warnings": warnings,
            },
        )
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_set_params")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_create_node")
async def td_create_node(params: CreateNodeInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_create_node",
        "node/create",
        params.model_dump(exclude_none=True),
        audit_event="td_create_node",
    )


@mcp.tool(name="td_delete_node")
async def td_delete_node(params: DeleteNodeInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_delete_node",
        "node/delete",
        params.model_dump(),
        audit_event="td_delete_node",
    )


@mcp.tool(name="td_copy_node")
async def td_copy_node(params: CopyNodeInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_copy_node",
        "node/copy",
        params.model_dump(exclude_none=True),
        audit_event="td_copy_node",
    )


@mcp.tool(name="td_rename_node")
async def td_rename_node(params: RenameNodeInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_rename_node",
        "node/rename",
        params.model_dump(),
        audit_event="td_rename_node",
    )


@mcp.tool(name="td_connect_nodes")
async def td_connect_nodes(params: ConnectNodesInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_connect_nodes",
        "node/connect",
        params.model_dump(),
        audit_event="td_connect_nodes",
    )


@mcp.tool(name="td_disconnect")
async def td_disconnect(params: DisconnectInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_disconnect",
        "node/disconnect",
        params.model_dump(),
        audit_event="td_disconnect",
    )


@mcp.tool(name="td_get_connections")
async def td_get_connections(params: NodePathInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_get_connections",
        "node/connections",
        {"path": params.path},
    )


@mcp.tool(name="td_get_content")
async def td_get_content(params: GetContentInput, ctx: Context) -> str:
    return await _forward(ctx, "td_get_content", "node/content", params.model_dump())


@mcp.tool(name="td_set_content")
async def td_set_content(params: SetContentInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_set_content",
        "node/content/set",
        params.model_dump(exclude_none=True),
        audit_event="td_set_content",
    )


@mcp.tool(name="td_custom_parameters")
async def td_custom_parameters(params: CustomParametersInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_custom_parameters",
        "custom-parameters",
        params.model_dump(),
        audit_event="td_custom_parameters",
    )


@mcp.tool(name="td_exec_python")
async def td_exec_python(params: ExecPythonInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_exec_python")
    try:
        _enforce_exec_mode(params.code)
        mode = _current_exec_mode()
        data = await _get_client(ctx).request(
            "exec",
            {
                "code": params.code,
                "exec_mode": mode,
            },
        )
        _audit_log(
            ctx,
            "td_exec_python",
            {
                "exec_mode": mode,
                "code_length": len(params.code),
            },
        )
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_exec_python")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_screenshot")
async def td_screenshot(params: ScreenshotInput, ctx: Context) -> str:
    """Capture a TOP frame.

    Ask the user before repeated screenshots because each base64 image can
    consume significant tokens in model context.
    """
    return await _forward(ctx, "td_screenshot", "screenshot", params.model_dump())


@mcp.tool(name="td_chop_data")
async def td_chop_data(params: CHOPDataInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_chop_data",
        "chop/data",
        params.model_dump(exclude_none=True),
    )


@mcp.tool(name="td_geometry_data")
async def td_geometry_data(params: GeometryDataInput, ctx: Context) -> str:
    return await _forward(ctx, "td_geometry_data", "geometry/data", params.model_dump())


@mcp.tool(name="td_pop_inspect")
async def td_pop_inspect(params: POPInspectInput, ctx: Context) -> str:
    return await _forward(ctx, "td_pop_inspect", "pop/inspect", params.model_dump())


@mcp.tool(name="td_cooking_info")
async def td_cooking_info(params: CookingInfoInput, ctx: Context) -> str:
    return await _forward(ctx, "td_cooking_info", "cooking", params.model_dump())


@mcp.tool(name="td_search_nodes")
async def td_search_nodes(params: SearchNodesInput, ctx: Context) -> str:
    return await _forward(ctx, "td_search_nodes", "search", params.model_dump())


@mcp.tool(name="td_get_errors")
async def td_get_errors(params: GetErrorsInput, ctx: Context) -> str:
    return await _forward(ctx, "td_get_errors", "node/errors", params.model_dump())


@mcp.tool(name="td_timeline")
async def td_timeline(ctx: Context) -> str:
    return await _forward(ctx, "td_timeline", "timeline")


@mcp.tool(name="td_timeline_set")
async def td_timeline_set(params: TimelineSetInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_timeline_set",
        "timeline/set",
        params.model_dump(exclude_none=True),
        audit_event="td_timeline_set",
    )


@mcp.tool(name="td_project_lifecycle")
async def td_project_lifecycle(params: ProjectLifecycleInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_project_lifecycle",
        "project/lifecycle",
        params.model_dump(),
        audit_event="td_project_lifecycle",
    )


@mcp.tool(name="td_pulse_param")
async def td_pulse_param(params: PulseParamInput, ctx: Context) -> str:
    return await _forward(
        ctx,
        "td_pulse_param",
        "pulse",
        params.model_dump(),
        audit_event="td_pulse_param",
    )


@mcp.tool(name="td_python_help")
async def td_python_help(params: PythonHelpInput, ctx: Context) -> str:
    return await _forward(ctx, "td_python_help", "python/help", params.model_dump())


@mcp.tool(name="td_python_classes")
async def td_python_classes(ctx: Context) -> str:
    return await _forward(ctx, "td_python_classes", "python/classes")


# Extended tools


@mcp.tool(name="td_create_macro")
async def td_create_macro(params: CreateMacroInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_create_macro")
    try:
        engine = _get_macro_engine(ctx)
        data = await engine.create_macro(
            parent_path=params.parent_path,
            macro_type=params.macro_type.value,
            name_prefix=params.name,
            node_x=params.nodeX,
            node_y=params.nodeY,
            overrides=params.params,
        )
        _audit_log(
            ctx,
            "td_create_macro",
            {
                "macro_type": params.macro_type.value,
                "parent_path": params.parent_path,
                "name_prefix": params.name,
            },
        )
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_create_macro")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_list_macros")
async def td_list_macros(ctx: Context) -> str:
    finish = _start_tool(ctx, "td_list_macros")
    try:
        data = _get_macro_engine(ctx).list_macros()
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_list_macros")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_macro_params")
async def td_get_macro_params(params: GetMacroParamsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_macro_params")
    try:
        data = _get_macro_engine(ctx).get_macro_params(params.macro_type.value)
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_macro_params")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_capabilities")
async def td_get_capabilities(ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_capabilities")
    try:
        services = _get_services(ctx)
        capabilities = detect_capabilities(ctx, td_build=services.td_build)
        from td_mcp import __version__ as server_version
        # Check component version if TD is connected
        version_status = {"server_version": server_version}
        try:
            info = await _get_client(ctx).request("info")
            if isinstance(info, dict):
                comp_ver = info.get("mcp_component_version") or info.get("api_version", "")
                version_status["component_version"] = comp_ver
                if comp_ver and comp_ver != server_version:
                    version_status["mismatch"] = True
                    version_status["warning"] = (
                        f"TD component is v{comp_ver} but server is v{server_version}. "
                        f"Re-export the .tox to fix."
                    )
                elif comp_ver:
                    version_status["mismatch"] = False
        except Exception:
            version_status["component_version"] = "unknown (TD not reachable)"

        payload = {
            "schema_version": 1,
            "client_capabilities": capabilities.to_dict(),
            "version": version_status,
            "runtime": {
                "transport": TD_TRANSPORT,
                "exec_mode": _current_exec_mode(),
                "shared_secret_enabled": bool(TD_SHARED_SECRET),
                "event_ws_port": TD_WS_PORT,
                "snapshot_persistence": bool(TD_SNAPSHOT_DIR),
                "stream_max_fps": TD_STREAM_MAX_FPS,
            },
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_capabilities")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_server_metrics")
async def td_get_server_metrics(ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_server_metrics")
    try:
        telemetry = _get_telemetry(ctx)
        event_manager = _get_event_manager(ctx)
        visual_monitor = _get_visual_monitor(ctx)
        top_streamer = _get_top_streamer(ctx)
        safety_manager = _get_safety_manager(ctx)
        snapshot_manager = _get_snapshot_manager(ctx)
        job_manager = _get_job_manager(ctx)

        payload = {
            "schema_version": 1,
            "runtime": {
                "transport": TD_TRANSPORT,
                "exec_mode": _current_exec_mode(),
                "host": TD_HOST,
                "port": TD_PORT,
                "event_ws_port": TD_WS_PORT,
                "stream_max_fps": TD_STREAM_MAX_FPS,
            },
            "telemetry": telemetry.snapshot() if telemetry else {},
            "events": event_manager.stats(),
            "visual_monitor": {
                "active": visual_monitor.active_monitors(),
            },
            "top_stream": top_streamer.stats(),
            "safety": safety_manager.stats(),
            "snapshots": snapshot_manager.stats(),
            "jobs": job_manager.stats(),
            "audit_enabled": bool(_get_audit(ctx) and _get_audit(ctx).enabled()),
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_server_metrics")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_subscribe")
async def td_subscribe(params: SubscribeInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_subscribe")
    try:
        body = params.model_dump(exclude_none=True)
        provisioning = await _get_client(ctx).request("monitor/subscribe", body)

        event_manager = _get_event_manager(ctx)
        for et in params.event_types:
            event_manager.register_subscription(params.path, et, body)

        payload = {
            "success": True,
            "path": params.path,
            "subscription": body,
            "resource_uris": _build_subscription_resource_uris(params),
            "provisioning": provisioning,
            "active_subscriptions": len(event_manager.list_subscriptions()),
        }
        _audit_log(
            ctx,
            "td_subscribe",
            {
                "path": params.path,
                "event_types": params.event_types,
            },
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_subscribe")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_unsubscribe")
async def td_unsubscribe(params: UnsubscribeInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_unsubscribe")
    try:
        provisioning = await _get_client(ctx).request(
            "monitor/unsubscribe",
            params.model_dump(),
        )

        event_manager = _get_event_manager(ctx)
        removed = event_manager.unregister_all_for_path(params.path)

        payload = {
            "success": removed > 0,
            "path": params.path,
            "provisioning": provisioning,
            "active_subscriptions": len(event_manager.list_subscriptions()),
        }
        _audit_log(ctx, "td_unsubscribe", {"path": params.path})
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_unsubscribe")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_events")
async def td_get_events(params: GetEventsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_events")
    try:
        manager = _get_event_manager(ctx)
        events = manager.get_recent_events(event_type=params.event_type, limit=params.limit)
        payload = {
            "schema_version": 1,
            "event_type": params.event_type,
            "count": len(events),
            "events": events,
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_events")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_capture_and_analyze")
async def td_capture_and_analyze(params: CaptureAndAnalyzeInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_capture_and_analyze")
    try:
        if not params.confirm_image_capture:
            return _capture_confirmation_required_response()

        screenshot = await _get_client(ctx).request(
            "screenshot",
            {
                "path": params.path,
                "quality": params.quality,
            },
        )

        capabilities = detect_capabilities(ctx)
        analysis = None

        if params.analyze:
            if capabilities.supports_sampling:
                analysis = {
                    "status": "not_implemented",
                    "message": "Sampling capability detected but this runtime does not expose a sampling API.",
                    "prompt": params.analysis_prompt,
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
            "compare_with": params.compare_with,
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
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_capture_and_analyze")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_monitor_visual")
async def td_monitor_visual(params: VisualMonitorInput, ctx: Context) -> str:
    """Start periodic monitor for a TOP.

    Default mode omits base64 frames to keep token usage low.
    """
    finish = _start_tool(ctx, "td_monitor_visual")
    try:
        if params.include_image and not params.confirm_high_token_mode:
            return _vision_confirmation_required_response()

        monitor = _get_visual_monitor(ctx)
        config = await monitor.start_monitor(
            path=params.path,
            interval=params.interval,
            quality=params.quality,
            include_image=params.include_image,
        )

        payload = {
            "success": True,
            "monitor": config,
            "resource_uri": top_frame_uri(params.path),
            "active_monitors": monitor.active_monitors(),
            "token_notice": _vision_token_notice(params.include_image),
        }

        if params.auto_analyze:
            payload["note"] = "auto_analyze requested; monitor captures are active but auto sampling is not implemented in this runtime."

        _audit_log(
            ctx,
            "td_monitor_visual",
            {
                "path": params.path,
                "interval": params.interval,
                "quality": params.quality,
                "include_image": params.include_image,
                "confirm_high_token_mode": params.confirm_high_token_mode,
            },
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_monitor_visual")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_stop_monitor_visual")
async def td_stop_monitor_visual(params: StopMonitorInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_stop_monitor_visual")
    try:
        monitor = _get_visual_monitor(ctx)
        stopped = await monitor.stop_monitor(params.path)
        payload = {
            "success": stopped,
            "path": params.path,
            "active_monitors": monitor.active_monitors(),
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_stop_monitor_visual")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_stream_top")
async def td_stream_top(params: StreamTopInput, ctx: Context) -> str:
    """Start continuous TOP stream.

    Default mode omits base64 frames to keep token usage low.
    """
    finish = _start_tool(ctx, "td_stream_top")
    try:
        if params.include_image and not params.confirm_high_token_mode:
            return _vision_confirmation_required_response()

        streamer = _get_top_streamer(ctx)
        normalized_fps = max(0.5, min(float(params.fps), TD_STREAM_MAX_FPS))
        config = await streamer.start_stream(
            path=params.path,
            fps=normalized_fps,
            quality=params.quality,
            include_image=params.include_image,
            emit_unchanged=params.emit_unchanged,
        )
        payload = {
            "success": True,
            "stream": config,
            "resource_uri": top_frame_uri(params.path),
            "active_streams": streamer.active_streams(),
            "token_notice": _vision_token_notice(params.include_image),
            "limits": {
                "requested_fps": params.fps,
                "applied_fps": normalized_fps,
                "max_fps": TD_STREAM_MAX_FPS,
            },
        }
        _audit_log(
            ctx,
            "td_stream_top",
            {
                "path": params.path,
                "fps": normalized_fps,
                "quality": params.quality,
                "include_image": params.include_image,
                "confirm_high_token_mode": params.confirm_high_token_mode,
                "emit_unchanged": params.emit_unchanged,
            },
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_stream_top")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_stop_stream_top")
async def td_stop_stream_top(params: StopStreamTopInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_stop_stream_top")
    try:
        streamer = _get_top_streamer(ctx)
        stopped = await streamer.stop_stream(params.path)
        payload = {
            "success": stopped,
            "path": params.path,
            "active_streams": streamer.active_streams(),
            "stats": streamer.stats(),
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_stop_stream_top")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_optimize_visual")
async def td_optimize_visual(params: OptimizeVisualInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_optimize_visual")
    try:
        client = _get_client(ctx)
        safety = _get_safety_manager(ctx)
        snapshots = _get_snapshot_manager(ctx)
        jobs = _get_job_manager(ctx)
        capabilities = detect_capabilities(ctx)

        # Build goal profile from explicit weights or sensible defaults.
        default_weights: dict[str, float] = {
            "brightness": 0.0,
            "contrast": 0.0,
            "stability": 0.4,
            "complexity": 0.3,
            "motion_rhythm": 0.0,
        }
        goal_profile: dict[str, float] = dict(default_weights)
        if params.objective_weights:
            for key, value in params.objective_weights.items():
                if key in goal_profile:
                    try:
                        goal_profile[key] = max(-1.0, min(1.0, float(value)))
                    except Exception:
                        continue

        baseline_snapshot_id: str | None = None
        snapshot_warning: str | None = None
        if params.snapshot_before:
            try:
                snapshot_payload = await _capture_snapshot_payload(
                    ctx,
                    path=params.root_path,
                    include_visual=False,
                )
                saved = snapshots.add_snapshot(
                    snapshot_payload,
                    name=f"optimize_start_{params.output_top.strip('/').replace('/', '_') or 'top'}",
                )
                baseline_snapshot_id = saved["snapshot_id"]
            except Exception as exc:
                snapshot_warning = str(exc)

        async def runner(job_id: str) -> dict[str, Any]:
            optimize_result = await _run_optimizer_iterations(
                client=client,
                safety=safety,
                jobs=jobs,
                job_id=job_id,
                adjustable_params=params.adjustable_params,
                goal_profile=goal_profile,
                max_iterations=params.max_iterations,
                convergence_threshold=params.convergence_threshold,
                safety_profile=params.safety_profile,
                root_path=params.root_path,
                phase_label="optimize_visual",
            )

            return {
                "schema_version": 1,
                "mode": "bounded_search",
                "sampling_supported": capabilities.supports_sampling,
                "goal": params.goal,
                "goal_profile": goal_profile,
                "output_top": params.output_top,
                "root_path": params.root_path,
                "safety_profile": params.safety_profile,
                "snapshot_before": params.snapshot_before,
                "baseline_snapshot_id": baseline_snapshot_id,
                "snapshot_warning": snapshot_warning,
                "converged": optimize_result["converged"],
                "emergency_stop": optimize_result["emergency_stop"],
                "stop_reason": optimize_result["stop_reason"],
                "iterations_completed": optimize_result["iterations_completed"],
                "max_iterations": params.max_iterations,
                "convergence_threshold": params.convergence_threshold,
                "final_score": optimize_result["final_score"],
                "iterations": optimize_result["iterations"],
                "final_params": optimize_result["final_params"],
                "next": [
                    "Read td://job/{job_id} for incremental updates while running.",
                    "If results are unstable, use td_restore_snapshot with baseline_snapshot_id.",
                ],
            }

        job = jobs.start_async(
            description=f"Optimize visual goal: {params.goal}",
            runner=runner,
        )

        _audit_log(
            ctx,
            "td_optimize_visual",
            {
                "goal": params.goal,
                "output_top": params.output_top,
                "adjustable_count": len(params.adjustable_params),
                "max_iterations": params.max_iterations,
                "safety_profile": params.safety_profile,
                "goal_profile": goal_profile,
                "baseline_snapshot_id": baseline_snapshot_id,
            },
        )

        payload = {
            "success": True,
            "job": job,
            "job_id": job["job_id"],
            "job_resource_uri": f"td://job/{job['job_id']}",
            "mode": "bounded_search",
            "sampling_supported": capabilities.supports_sampling,
            "baseline_snapshot_id": baseline_snapshot_id,
            "snapshot_warning": snapshot_warning,
            "goal_profile": goal_profile,
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_optimize_visual")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_describe_dynamics")
async def td_describe_dynamics(params: TemporalAnalysisInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_describe_dynamics")
    try:
        client = _get_client(ctx)
        jobs = _get_job_manager(ctx)
        event_manager = _get_event_manager(ctx)

        sample_interval = max(1.0 / params.sample_rate, 0.01)
        target_samples = max(1, int(round(params.observation_window * params.sample_rate)))

        async def runner(job_id: str) -> dict[str, Any]:
            samples: list[dict[str, Any]] = []
            started = time.perf_counter()

            for index in range(target_samples):
                tick_started = time.perf_counter()

                timeline, cooking, errors = await asyncio.gather(
                    _safe_request(client, "timeline"),
                    _safe_request(
                        client,
                        "cooking",
                        {"path": params.path, "recurse": True, "limit": 20, "sort_by": "cookTime"},
                    ),
                    _safe_request(
                        client,
                        "node/errors",
                        {"path": params.path, "recurse": True, "max_depth": 10},
                    ),
                )

                heavy_nodes = [
                    node
                    for node in (cooking.get("nodes", []) if isinstance(cooking, dict) else [])
                    if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) >= 0.01
                ]
                issues = errors.get("issues", []) if isinstance(errors, dict) else []
                recent_events = event_manager.get_recent_events(limit=200)

                sample = {
                    "index": index + 1,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "frame": int(timeline.get("frame", 0) or 0) if isinstance(timeline, dict) else 0,
                    "seconds": float(timeline.get("seconds", 0.0) or 0.0) if isinstance(timeline, dict) else 0.0,
                    "playing": bool(timeline.get("playing", False)) if isinstance(timeline, dict) else False,
                    "fps": float(cooking.get("fps", 0.0) or 0.0) if isinstance(cooking, dict) else 0.0,
                    "issues_count": len(issues),
                    "heavy_nodes_count": len(heavy_nodes),
                    "event_rate": _event_rate_per_sec(recent_events),
                }
                samples.append(sample)

                jobs.update_job(
                    job_id,
                    progress=float(index + 1) / float(target_samples),
                    result={
                        "latest_sample": sample,
                        "samples_collected": index + 1,
                        "target_samples": target_samples,
                    },
                )

                elapsed_tick = time.perf_counter() - tick_started
                await asyncio.sleep(max(0.0, sample_interval - elapsed_tick))

            elapsed = time.perf_counter() - started
            classifications = _classify_temporal_character(samples)

            return {
                "schema_version": 1,
                "path": params.path,
                "observation": {
                    "duration_sec": elapsed,
                    "requested_window_sec": params.observation_window,
                    "sample_rate": params.sample_rate,
                    "samples": len(samples),
                    "fps_during_mean": classifications.get("fps_mean", 0.0),
                },
                "samples": samples,
                "classifications": classifications,
                "notes": [
                    "Current classifier is heuristic and intended for fast diagnostics.",
                    "Use td_get_state_vector alongside this report for broader context.",
                ],
            }

        job = jobs.start_async(
            description=f"Describe dynamics for {params.path}",
            runner=runner,
        )

        _audit_log(
            ctx,
            "td_describe_dynamics",
            {
                "path": params.path,
                "observation_window": params.observation_window,
                "sample_rate": params.sample_rate,
            },
        )

        payload = {
            "success": True,
            "job": job,
            "job_id": job["job_id"],
            "job_resource_uri": f"td://job/{job['job_id']}",
            "path": params.path,
            "observation_window": params.observation_window,
            "sample_rate": params.sample_rate,
            "target_samples": target_samples,
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_describe_dynamics")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_set_param_bounds")
async def td_set_param_bounds(params: SetBoundsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_set_param_bounds")
    try:
        safety = _get_safety_manager(ctx)
        safety.set_mode(params.enforce_mode)

        for bound in params.bounds:
            key = f"{bound.path}/{bound.param}"
            safety.set_bound(
                key,
                min_val=bound.min_val,
                max_val=bound.max_val,
                max_rate=bound.max_rate,
            )

        payload = {
            "success": True,
            "mode": safety.get_mode(),
            "bounds_count": len(safety.list_bounds()),
            "bounds": safety.list_bounds(),
        }

        _audit_log(
            ctx,
            "td_set_param_bounds",
            {
                "mode": params.enforce_mode,
                "count": len(params.bounds),
            },
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_set_param_bounds")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_clear_param_bounds")
async def td_clear_param_bounds(params: ClearBoundsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_clear_param_bounds")
    try:
        safety = _get_safety_manager(ctx)

        cleared = 0
        if params.paths:
            keys = list(safety.list_bounds().keys())
            for key in keys:
                if any(key.startswith(path.rstrip("/") + "/") or key == path for path in params.paths):
                    if safety.clear_bound(key):
                        cleared += 1
        else:
            cleared = safety.clear_all()

        payload = {
            "success": True,
            "cleared": cleared,
            "remaining": len(safety.list_bounds()),
            "mode": safety.get_mode(),
        }
        _audit_log(
            ctx,
            "td_clear_param_bounds",
            {"paths": params.paths, "cleared": cleared},
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_clear_param_bounds")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_detect_instability")
async def td_detect_instability(params: DetectInstabilityInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_detect_instability")
    try:
        client = _get_client(ctx)
        cooking = await client.request(
            "cooking",
            {
                "path": params.path,
                "recurse": True,
                "limit": 50,
                "sort_by": "cookTime",
            },
        )
        errors = await client.request(
            "node/errors",
            {
                "path": params.path,
                "recurse": True,
                "max_depth": 10,
            },
        )

        fps = float(cooking.get("fps", 0.0) or 0.0)
        realtime = bool(cooking.get("realTime", False))
        # Target FPS drives the frame-budget calculation. Fall back to the
        # reported fps when target isn't available, capped at 60 so we don't
        # silently relax the budget on sub-60 projects.
        target_fps = float(cooking.get("target_fps", fps) or fps or 60.0) or 60.0
        frame_budget_ms = 1000.0 / target_fps if target_fps > 0 else 16.67
        # A node is "heavy" if it cooks for at least 25% of the frame budget.
        # Previous threshold was 0.01 ms which flagged any node that cooked at
        # all, producing a permanent false-positive on even trivial scenes.
        heavy_threshold_ms = max(frame_budget_ms * 0.25, 1.0)
        all_cook_nodes = [
            node
            for node in cooking.get("nodes", [])
            if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) > 0
        ]
        heavy_nodes = [
            node
            for node in all_cook_nodes
            if float(node.get("cookTime", 0.0) or 0.0) >= heavy_threshold_ms
        ]
        top_cook_ms = max(
            (float(node.get("cookTime", 0.0) or 0.0) for node in all_cook_nodes),
            default=0.0,
        )
        issues = errors.get("issues", []) if isinstance(errors, dict) else []
        # Only flag errors (not warnings) as instability signals — TD ships with
        # ~27 stock UI warnings at /ui/** that don't indicate project health.
        critical_issues = [
            item
            for item in issues
            if isinstance(item, dict) and (item.get("errors") or "").strip()
        ]

        # Instability is real if: FPS missed target by >20%, any CRITICAL error
        # exists, or a SINGLE node cooks for more than the full frame budget
        # (can't possibly hit target fps). Heavy-node count is reported as a
        # soft signal only — it shouldn't by itself flip the boolean.
        fps_missed = target_fps > 0 and fps < target_fps * 0.8
        frame_blown = top_cook_ms >= frame_budget_ms
        unstable = fps_missed or frame_blown or bool(critical_issues)

        # Build human-readable reason list so callers don't have to infer which
        # signal fired (biggest UX gap of the previous version).
        reasons: list[str] = []
        if fps_missed:
            reasons.append(
                f"fps {fps:.1f} is below 80% of target {target_fps:.1f}"
            )
        if frame_blown:
            reasons.append(
                f"top cook time {top_cook_ms:.2f}ms exceeds frame budget "
                f"{frame_budget_ms:.2f}ms"
            )
        if critical_issues:
            reasons.append(f"{len(critical_issues)} critical node error(s)")

        payload = {
            "schema_version": 2,
            "path": params.path,
            "unstable": unstable,
            "reasons": reasons,
            "signals": {
                "fps": fps,
                "target_fps": target_fps,
                "frame_budget_ms": round(frame_budget_ms, 3),
                "heavy_threshold_ms": round(heavy_threshold_ms, 3),
                "realtime": realtime,
                "issues_count": len(issues),
                "critical_issues_count": len(critical_issues),
                "heavy_nodes_count": len(heavy_nodes),
                "top_cook_ms": round(top_cook_ms, 3),
            },
            "heavy_nodes": heavy_nodes[:10],
            "issues": issues[:20],
            "suggested_actions": [
                "Pause timeline and inspect top cook-time operators.",
                "Clamp unstable parameters via td_set_param_bounds.",
                "Use td_snapshot_scene before large edits.",
            ],
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_detect_instability")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_emergency_stabilize")
async def td_emergency_stabilize(params: DetectInstabilityInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_emergency_stabilize")
    try:
        client = _get_client(ctx)
        snapshots = _get_snapshot_manager(ctx)

        snapshot_payload = await _capture_snapshot_payload(
            ctx,
            path=params.path,
            include_visual=False,
        )
        saved = snapshots.add_snapshot(snapshot_payload, name="emergency_pre_stabilize")

        actions = []
        timeline = await client.request("timeline")
        if timeline.get("playing"):
            await client.request("timeline/set", {"action": "pause"})
            actions.append("timeline_paused")

        safety = _get_safety_manager(ctx)
        if safety.get_mode() != "clamp":
            safety.set_mode("clamp")
            actions.append("safety_mode_clamp")

        payload = {
            "success": True,
            "path": params.path,
            "actions": actions,
            "snapshot": {
                "snapshot_id": saved["snapshot_id"],
                "name": saved["name"],
                "timestamp": saved["timestamp"],
            },
            "next": [
                "Inspect td_detect_instability for current bottlenecks.",
                "Restore from snapshot if needed with td_restore_snapshot.",
            ],
        }

        _audit_log(
            ctx,
            "td_emergency_stabilize",
            {
                "path": params.path,
                "actions": actions,
                "snapshot_id": saved["snapshot_id"],
            },
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_emergency_stabilize")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_snapshot_scene")
async def td_snapshot_scene(params: SnapshotInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_snapshot_scene")
    try:
        payload = await _capture_snapshot_payload(
            ctx,
            path=params.path,
            include_visual=params.include_visual,
        )
        snapshot = _get_snapshot_manager(ctx).add_snapshot(payload, name=params.name)

        result = {
            "success": True,
            "snapshot_id": snapshot["snapshot_id"],
            "name": snapshot["name"],
            "timestamp": snapshot["timestamp"],
            "summary": {
                "captured_nodes": payload.get("captured_nodes", 0),
                "connection_count": len(payload.get("connections", [])),
                "truncated": payload.get("truncated", False),
                "include_visual": params.include_visual,
            },
        }
        return _as_json_output(result)
    except Exception as exc:
        _record_tool_error(ctx, "td_snapshot_scene")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_list_snapshots")
async def td_list_snapshots(params: ListSnapshotsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_list_snapshots")
    try:
        snapshots = _get_snapshot_manager(ctx).list_snapshots(limit=params.limit)
        return _as_json_output(
            {
                "schema_version": 1,
                "count": len(snapshots),
                "snapshots": snapshots,
            }
        )
    except Exception as exc:
        _record_tool_error(ctx, "td_list_snapshots")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_diff_snapshots")
async def td_diff_snapshots(params: DiffSnapshotsInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_diff_snapshots")
    try:
        manager = _get_snapshot_manager(ctx)

        snap_a = manager.get_snapshot(params.snapshot_a)
        if snap_a is None:
            raise ValueError(f"Snapshot not found: {params.snapshot_a}")

        if params.snapshot_b:
            snap_b = manager.get_snapshot(params.snapshot_b)
            if snap_b is None:
                raise ValueError(f"Snapshot not found: {params.snapshot_b}")
            compare_target = {
                "type": "snapshot",
                "snapshot_id": params.snapshot_b,
            }
            snapshot_b_payload = snap_b["snapshot"]
        else:
            live = await _capture_snapshot_payload(ctx, path=snap_a["snapshot"].get("root_path", "/project1"), include_visual=False)
            compare_target = {
                "type": "live",
                "path": live.get("root_path", "/project1"),
            }
            snapshot_b_payload = live

        diff = manager.diff(snap_a["snapshot"], snapshot_b_payload)
        payload = {
            "schema_version": 1,
            "snapshot_a": params.snapshot_a,
            "compare_target": compare_target,
            "diff": diff,
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_diff_snapshots")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_restore_snapshot")
async def td_restore_snapshot(params: RestoreSnapshotInput, ctx: Context) -> str:
    """Restore parameter values from a previously saved snapshot.

    This tool replays the parameter values captured in the snapshot back onto
    the live TouchDesigner network.  It restores *parameter values only* — it
    does not add, remove, or rewire nodes.  For structural rollback (topology
    changes such as added/deleted nodes or connection changes) use
    TouchDesigner's native Ctrl+Z undo stack instead.

    Use ``dry_run=True`` to preview what would be changed without applying
    anything.  Supply ``partial`` with a list of node paths to limit the
    restore to a subset of the snapshot.
    """
    finish = _start_tool(ctx, "td_restore_snapshot")
    try:
        manager = _get_snapshot_manager(ctx)
        snapshot = manager.get_snapshot(params.snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {params.snapshot_id}")

        snapshot_nodes = snapshot.get("snapshot", {}).get("nodes", {})
        if not isinstance(snapshot_nodes, dict):
            snapshot_nodes = {}

        client = _get_client(ctx)
        safety = _get_safety_manager(ctx)
        restore_result = await _restore_snapshot_nodes(
            client,
            safety,
            snapshot_nodes,
            partial_filters=params.partial or [],
            dry_run=params.dry_run,
        )
        restored = restore_result["restored"]
        skipped = restore_result["skipped"]
        failures = restore_result["failures"]
        warnings = restore_result["safety_warnings"]

        payload = {
            "success": not failures,
            "snapshot_id": params.snapshot_id,
            "dry_run": params.dry_run,
            "restored_count": len(restored),
            "skipped_count": len(skipped),
            "failure_count": len(failures),
            "restored": restored,
            "skipped": skipped,
            "failures": failures,
            "safety_warnings": warnings,
        }

        if not params.dry_run:
            _audit_log(
                ctx,
                "td_restore_snapshot",
                {
                    "snapshot_id": params.snapshot_id,
                    "restored_count": len(restored),
                    "failure_count": len(failures),
                    "partial": params.partial,
                },
            )

        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_restore_snapshot")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_state_vector")
async def td_get_state_vector(params: StateVectorInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_state_vector")
    try:
        cache_key = params.path
        cached = _STATE_VECTOR_CACHE.get(cache_key)
        now = time.time()

        if not params.force_refresh and cached:
            cached_at = float(cached.get("cached_at", 0.0) or 0.0)
            age = now - cached_at
            if age <= max(0.0, TD_STATE_VECTOR_TTL):
                payload = dict(cached["data"])
                payload["cache"] = {
                    "hit": True,
                    "age_sec": age,
                    "ttl_sec": TD_STATE_VECTOR_TTL,
                }
                return _as_json_output(payload)

        state_vector = await _build_state_vector(params.path, ctx)
        if len(_STATE_VECTOR_CACHE) >= 100:
            _STATE_VECTOR_CACHE.clear()
        _STATE_VECTOR_CACHE[cache_key] = {
            "cached_at": now,
            "data": state_vector,
        }
        state_vector["cache"] = {
            "hit": False,
            "ttl_sec": TD_STATE_VECTOR_TTL,
        }
        return _as_json_output(state_vector)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_state_vector")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_timescale_state")
async def td_get_timescale_state(params: TimescaleStateInput, ctx: Context) -> str:
    finish = _start_tool(ctx, "td_get_timescale_state")
    try:
        timeline = await _get_client(ctx).request("timeline")
        bpm = float(params.bpm_hint if params.bpm_hint is not None else 120.0)
        beats_per_bar = int(params.beats_per_bar)

        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timeline": timeline,
            "timescale": _compute_timescale_from_timeline(
                timeline if isinstance(timeline, dict) else {},
                bpm=bpm,
                beats_per_bar=beats_per_bar,
            ),
            "notes": [
                "BPM is currently hint-based; use an external detector to feed live BPM.",
                "Beat/bar/phrase phases can drive modulation curves or macro transitions.",
            ],
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_timescale_state")
        return format_tool_error(exc)
    finally:
        finish()


# ─────────────────────────────────────────────────────────────
# Technique Memory Tools
# ─────────────────────────────────────────────────────────────


@mcp.tool()
async def td_memory_learn(params: MemoryLearnInput, ctx: Context) -> dict:
    """Analyze a network subtree and extract a reusable technique recipe.

    Auto-detects complexity:
    - small (<10 nodes): full recipe with all params and expressions
    - medium (10-20): full recipe
    - large (>20): structure summary + key params only

    Returns the technique dict — pass it to td_memory_save to persist.
    """
    svc = _get_services(ctx)
    client = _get_client(ctx)
    technique = await analyze_network(
        client,
        params.path,
        max_depth=params.max_depth,
        name=params.name,
        description=params.description,
        tags=params.tags,
        td_build=svc.td_build,
    )
    return {"status": "ok", "technique": technique}


@mcp.tool()
async def td_memory_save(params: MemorySaveInput, ctx: Context) -> dict:
    """Save a technique to the project or global library.

    Use the output of td_memory_learn as the technique input,
    or construct a technique dict manually.
    """
    store = _get_technique_store(ctx)
    # Build compatibility dict from technique metadata if present
    tech = params.technique
    td_build = tech.get("td_build", "") if isinstance(tech, dict) else ""
    required_op_types = tech.get("required_op_types", []) if isinstance(tech, dict) else []
    compatibility: dict = {}
    if td_build:
        compatibility["min_build"] = td_build
    if required_op_types:
        compatibility["required_ops"] = required_op_types
    # Fall back to values from the technique dict if caller didn't provide them
    name = params.name or (tech.get("name", "") if isinstance(tech, dict) else "")
    description = params.description or (tech.get("description", "") if isinstance(tech, dict) else "")
    tags = params.tags or (tech.get("tags", []) if isinstance(tech, dict) else [])
    technique_id = store.add(
        technique=params.technique,
        scope=params.scope,
        name=name,
        description=description,
        tags=tags,
        notes=params.notes,
        compatibility=compatibility or None,
    )
    return {"status": "ok", "technique_id": technique_id, "scope": params.scope}


@mcp.tool()
async def td_memory_recall(params: MemoryRecallInput, ctx: Context) -> dict:
    """Search the technique library by text query and/or tags.

    Returns summaries (not full recipes). Use td_memory_replay to rebuild a found technique.
    """
    store = _get_technique_store(ctx)
    results = store.search(
        query=params.query,
        tags=params.tags if params.tags else None,
        scope=params.scope,
        limit=params.limit,
    )
    return {"status": "ok", "count": len(results), "techniques": results}


@mcp.tool()
async def td_memory_replay(params: MemoryReplayInput, ctx: Context) -> dict:
    """Rebuild a saved technique in a new location in the TD project.

    Creates nodes, sets parameters and expressions, wires connections.
    Only works for techniques with a full recipe (small/medium complexity).
    """
    store = _get_technique_store(ctx)
    entry = store.get(params.technique_id, scope=params.scope)
    if not entry:
        return {"status": "error", "message": f"Technique {params.technique_id} not found in {params.scope} scope."}

    technique = entry.get("technique", {})
    recipe = technique.get("recipe")
    if not recipe:
        return {
            "status": "error",
            "message": "This technique has no full recipe (large network — only key params were captured). "
            "You can use the key_params and structure info to manually recreate it.",
            "key_params": technique.get("key_params"),
            "families": technique.get("families"),
            "op_types": technique.get("op_types"),
        }

    # Pre-replay prerequisite check: verify required op types exist in the target TD install
    if not params.force:
        required_ops: list[str] = (
            technique.get("required_op_types")
            or entry.get("compatibility", {}).get("required_ops")
            or []
        )
        if required_ops:
            client = _get_client(ctx)
            try:
                families_resp = await client.request("families", {})
                available_types: set = set()
                if isinstance(families_resp, dict):
                    for fam_types in families_resp.values():
                        if isinstance(fam_types, list):
                            available_types.update(fam_types)
                if available_types:
                    missing_ops = [t for t in required_ops if t not in available_types]
                    if missing_ops:
                        return {
                            "status": "blocked",
                            "reason": "Missing operator types in target TD install",
                            "missing_ops": missing_ops,
                        }
            except Exception:
                pass  # If we can't verify, allow replay (checked at create time anyway)

    client = _get_client(ctx)
    parent = params.parent_path.rstrip("/") or "/"
    prefix = params.name_prefix.strip()

    recipe_nodes = recipe.get("nodes", {})
    if not isinstance(recipe_nodes, dict) or not recipe_nodes:
        return {"status": "error", "message": "Technique recipe has no nodes to replay."}

    created_nodes: dict[str, str] = {"/": parent}
    skipped_nodes: list[dict[str, str]] = []

    # Build shallow-to-deep so nested paths can resolve their parent container.
    create_order = sorted(
        (
            rel_path
            for rel_path in recipe_nodes.keys()
            if isinstance(rel_path, str) and rel_path and rel_path != "/"
        ),
        key=lambda rel_path: rel_path.count("/"),
    )

    created_count = 0
    for rel_path in create_order:
        node_info = recipe_nodes.get(rel_path, {})
        if not isinstance(node_info, dict):
            skipped_nodes.append({"path": rel_path, "reason": "invalid_node_payload"})
            continue

        raw_type = str(node_info.get("type", "")).strip()
        family = str(node_info.get("family", "")).strip().upper()
        if not raw_type:
            skipped_nodes.append({"path": rel_path, "reason": "missing_type"})
            continue

        suffix_by_family = {
            "TOP": "TOP",
            "CHOP": "CHOP",
            "SOP": "SOP",
            "DAT": "DAT",
            "COMP": "COMP",
            "MAT": "MAT",
            "POP": "POP",
        }

        op_type_candidates: list[str] = []
        upper_type = raw_type.upper()
        if any(upper_type.endswith(suffix) for suffix in suffix_by_family.values()):
            op_type_candidates.append(raw_type)
        else:
            suffix = suffix_by_family.get(family)
            if suffix:
                op_type_candidates.append(f"{raw_type}{suffix}")
            op_type_candidates.append(raw_type)

        # Deduplicate while preserving order.
        op_type_candidates = list(dict.fromkeys(op_type_candidates))

        parts = rel_path.strip("/").split("/")
        if len(parts) <= 1:
            parent_rel = "/"
        else:
            parent_rel = "/" + "/".join(parts[:-1])

        target_parent = created_nodes.get(parent_rel)
        if not target_parent:
            skipped_nodes.append({"path": rel_path, "reason": f"missing_parent:{parent_rel}"})
            continue

        base_name = str(node_info.get("name", "")).strip() or parts[-1] or raw_type
        node_name = f"{prefix}_{base_name}" if prefix else base_name

        result: dict[str, Any] | None = None
        create_error: str | None = None
        for candidate_type in op_type_candidates:
            try:
                create_result = await client.request(
                    "node/create",
                    {
                        "parent_path": target_parent,
                        "node_type": candidate_type,
                        "name": node_name,
                    },
                )
                if isinstance(create_result, dict):
                    result = create_result
                    break
                result = {"node": {"path": ""}}
                break
            except Exception as exc:
                create_error = str(exc)

        if result is None:
            skipped_nodes.append(
                {
                    "path": rel_path,
                    "reason": f"create_failed:{create_error or 'unknown'}",
                }
            )
            continue

        node_obj = result.get("node", {}) if isinstance(result, dict) else {}
        actual_path = node_obj.get("path") if isinstance(node_obj, dict) else None
        if not isinstance(actual_path, str) or not actual_path:
            fallback_path = result.get("path") if isinstance(result, dict) else None
            if isinstance(fallback_path, str) and fallback_path:
                actual_path = fallback_path
            else:
                actual_path = f"{target_parent.rstrip('/')}/{node_name}".replace("//", "/")

        created_nodes[rel_path] = actual_path
        created_count += 1

        params_to_set = node_info.get("params", {})
        if isinstance(params_to_set, dict):
            clean_params = {key: value for key, value in params_to_set.items() if value is not None}
            if clean_params:
                await client.request(
                    "node/params/set",
                    {
                        "path": actual_path,
                        "params": clean_params,
                    },
                )

        expressions = node_info.get("expressions", {})
        if isinstance(expressions, dict):
            expr_params = {
                key: {"expr": value}
                for key, value in expressions.items()
                if isinstance(value, str) and value
            }
            if expr_params:
                await client.request(
                    "node/params/set",
                    {
                        "path": actual_path,
                        "params": expr_params,
                    },
                )

    wired = 0
    skipped_connections: list[dict[str, str]] = []
    for conn in recipe.get("connections", []):
        if not isinstance(conn, dict):
            continue

        src_rel = str(conn.get("from", "")).strip()
        dst_rel = str(conn.get("to", "")).strip()
        src_path = created_nodes.get(src_rel)
        dst_path = created_nodes.get(dst_rel)

        if not src_path or not dst_path:
            skipped_connections.append(
                {
                    "from": src_rel,
                    "to": dst_rel,
                    "reason": "missing_node_mapping",
                }
            )
            continue

        await client.request(
            "node/connect",
            {
                "source_path": src_path,
                "target_path": dst_path,
                "source_index": int(conn.get("from_index", 0) or 0),
                "target_index": int(conn.get("to_index", 0) or 0),
            },
        )
        wired += 1

    created_paths = {key: value for key, value in created_nodes.items() if key != "/"}

    # Auto-validate after replay
    validation_result = None
    try:
        error_result = await client.request("node/errors", {"path": parent, "recurse": True, "max_depth": 10})
        errors = error_result.get("issues", []) if isinstance(error_result, dict) else []
        validation_status = "pass" if not errors else "fail"
        validation_result = {
            "status": validation_status,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "td_build": _get_services(ctx).td_build,
            "errors": [str(e) for e in errors[:10]],
            "warnings": [],
        }
        # Auto-promote candidate to validated_local on clean replay
        entry_state = entry.get("state", "candidate")
        if validation_status == "pass" and entry_state == "candidate":
            store.update(params.technique_id, {
                "state": "validated_local",
                "validation_result": validation_result,
            }, scope=params.scope)
        else:
            store.update(params.technique_id, {
                "validation_result": validation_result,
            }, scope=params.scope)
    except Exception:
        pass  # Non-fatal: replay succeeded even if validation check fails

    response = {
        "status": "ok",
        "nodes_created": created_count,
        "connections_wired": wired,
        "created_paths": created_paths,
        "skipped_nodes": skipped_nodes,
        "skipped_connections": skipped_connections,
    }
    if validation_result is not None:
        response["validation_result"] = validation_result

    # Track replay usage
    store.record_replay(params.technique_id, scope=params.scope)

    return response


@mcp.tool()
async def td_memory_favorite(params: MemoryFavoriteInput, ctx: Context) -> dict:
    """Mark a technique as favorite and/or rate it (0-5)."""
    store = _get_technique_store(ctx)
    ok = store.set_favorite(params.technique_id, params.favorite, scope=params.scope)
    if not ok:
        return {"status": "error", "message": f"Technique {params.technique_id} not found."}
    if params.rating >= 0:
        store.set_rating(params.technique_id, params.rating, scope=params.scope)
    return {"status": "ok", "technique_id": params.technique_id, "favorite": params.favorite, "rating": params.rating}


@mcp.tool()
async def td_memory_promote(params: MemoryPromoteInput, ctx: Context) -> dict:
    """Copy a project technique to the global library so it's available across all projects."""
    store = _get_technique_store(ctx)
    new_id = store.promote(params.technique_id)
    if not new_id:
        return {"status": "error", "message": f"Technique {params.technique_id} not found in project scope."}
    return {"status": "ok", "global_technique_id": new_id, "promoted_from": params.technique_id}


@mcp.tool()
async def td_memory_export(params: MemoryExportInput, ctx: Context) -> dict:
    """Export the technique library as a portable JSON object for sharing or backup."""
    store = _get_technique_store(ctx)
    return {"status": "ok", "library": store.export_library(scope=params.scope)}


@mcp.tool()
async def td_memory_import(params: MemoryImportInput, ctx: Context) -> dict:
    """Import techniques from an exported library (from td_memory_export)."""
    store = _get_technique_store(ctx)
    result = store.import_library(params.data, scope=params.scope, overwrite=params.overwrite)
    return {"status": "ok", **result}


@mcp.tool()
async def td_memory_preferences(params: MemoryPreferencesInput, ctx: Context) -> dict:
    """Get, set, list, or delete user preferences.

    Preferences store things like: preferred color palettes, default resolutions,
    favorite operator types, naming conventions, etc.
    """
    pref = _get_preference_store(ctx)
    action = params.action.lower()

    if action == "get":
        if not params.key:
            return {"status": "error", "message": "Key is required for 'get'."}
        value = pref.get(params.key, scope=params.scope)
        return {"status": "ok", "key": params.key, "value": value}

    elif action == "set":
        if not params.key:
            return {"status": "error", "message": "Key is required for 'set'."}
        pref.set(params.key, params.value, scope=params.scope)
        return {"status": "ok", "key": params.key, "value": params.value}

    elif action == "list":
        all_prefs = pref.list_all(scope=params.scope)
        return {"status": "ok", "preferences": all_prefs, "count": len(all_prefs)}

    elif action == "delete":
        if not params.key:
            return {"status": "error", "message": "Key is required for 'delete'."}
        deleted = pref.delete(params.key, scope=params.scope)
        return {"status": "ok", "deleted": deleted, "key": params.key}

    else:
        return {"status": "error", "message": f"Unknown action '{action}'. Use get/set/list/delete."}


@mcp.tool()
async def td_memory_list(params: MemoryListInput, ctx: Context) -> dict:
    """List saved techniques with optional filtering by scope, tags, and favorites."""
    store = _get_technique_store(ctx)
    results = store.list_techniques(
        scope=params.scope,
        tags=params.tags if params.tags else None,
        favorites_only=params.favorites_only,
        limit=params.limit,
    )
    return {"status": "ok", "count": len(results), "techniques": results}


# ─────────────────────────────────────────────────────────────
# Knowledge tools (64-71)
# ─────────────────────────────────────────────────────────────


def _get_card_index(ctx: Context):
    svc = _get_services(ctx)
    idx = getattr(svc, "card_index", None)
    if idx is None:
        raise RuntimeError("Knowledge corpus not loaded")
    return idx


@mcp.tool(name="td_search_official_docs")
async def td_search_official_docs(
    ctx: Context,
    query: str,
    card_types: list[str] | None = None,
    family: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search the knowledge corpus for operators, palette components, releases, or snippets."""
    idx = _get_card_index(ctx)
    results = idx.search(query, card_types=card_types, family=family, limit=limit)
    svc = _get_services(ctx)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_operator_doc")
async def td_get_operator_doc(
    ctx: Context,
    op_type: str | None = None,
    node_path: str | None = None,
) -> dict[str, Any]:
    """Get full documentation card for an operator type or a specific node."""
    idx = _get_card_index(ctx)
    resolved_type = op_type
    if resolved_type is None and node_path:
        # Resolve op_type from live node
        try:
            info = await _get_client(ctx).request("node/detail", {"path": node_path})
            resolved_type = info.get("type", "")
        except Exception:
            return {"error": f"Could not resolve node at {node_path}"}
    if not resolved_type:
        return {"error": "Provide op_type or node_path"}
    card = idx.get_operator(resolved_type)
    svc = _get_services(ctx)
    if card is None:
        provenance = Provenance(source="local_card", td_build=svc.td_build)
        return {"error": f"No card found for {resolved_type}", "provenance": provenance.to_dict()}
    provenance = Provenance(source="local_card", td_build=svc.td_build, last_verified=card.get("last_verified", ""))
    return {"card": card, "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_param_help")
async def td_get_param_help(
    ctx: Context,
    node_path: str,
    param_name: str,
) -> dict[str, Any]:
    """Get help for a specific parameter: live metadata + knowledge card entry + current value."""
    client = _get_client(ctx)
    # Get live param info
    try:
        params = await client.request("node/params", {"path": node_path, "names": [param_name]})
    except Exception as exc:
        return {"error": f"Could not read param: {exc}"}
    live_param = params.get("parameters", {}).get(param_name, params.get("params", {}).get(param_name))
    # Try to get operator card for enrichment
    idx = _get_card_index(ctx)
    card_param = None
    try:
        info = await client.request("node/detail", {"path": node_path})
        op_type = info.get("type", "")
        card = idx.get_operator(op_type)
        if card:
            for kp in card.get("key_params", []):
                if kp.get("name") == param_name:
                    card_param = kp
                    break
    except Exception:
        pass
    svc = _get_services(ctx)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {"live": live_param, "card_param": card_param, "provenance": provenance.to_dict()}


@mcp.tool(name="td_lookup_snippets")
async def td_lookup_snippets(
    ctx: Context,
    query: str,
    family: str | None = None,
) -> dict[str, Any]:
    """Search for OP Snippets by keyword and optional family."""
    idx = _get_card_index(ctx)
    results = idx.search(query, card_types=["snippets"], family=family)
    svc = _get_services(ctx)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_lookup_palette_component")
async def td_lookup_palette_component(
    ctx: Context,
    component_name: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Look up a palette component by name or search by query."""
    idx = _get_card_index(ctx)
    svc = _get_services(ctx)
    if component_name:
        card = idx.get_palette(component_name)
        if card:
            provenance = Provenance(source="local_card", td_build=svc.td_build, last_verified=card.get("last_verified", ""))
            return {"card": card, "provenance": provenance.to_dict()}
        provenance = Provenance(source="local_card", td_build=svc.td_build)
        return {"error": f"No palette card for {component_name}", "provenance": provenance.to_dict()}
    if query:
        results = idx.search(query, card_types=["palette"])
        provenance = Provenance(source="local_card", td_build=svc.td_build)
        return {"results": results, "count": len(results), "provenance": provenance.to_dict()}
    return {"error": "Provide component_name or query"}


@mcp.tool(name="td_get_release_delta")
async def td_get_release_delta(
    ctx: Context,
    build: str | None = None,
) -> dict[str, Any]:
    """Get release notes for a specific build (default: current)."""
    idx = _get_card_index(ctx)
    svc = _get_services(ctx)
    target_build = build or svc.td_build
    if not target_build:
        return {"error": "No build specified and current build unknown"}
    card = idx.get_release(target_build)
    if card is None:
        provenance = Provenance(source="local_card", td_build=svc.td_build)
        return {"error": f"No release card for build {target_build}", "provenance": provenance.to_dict()}
    provenance = Provenance(source="local_card", td_build=svc.td_build, last_verified=card.get("last_verified", ""))
    return {"card": card, "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_build_compatibility")
async def td_get_build_compatibility(
    ctx: Context,
    op_type: str,
    build: str | None = None,
) -> dict[str, Any]:
    """Check if an operator type is compatible with a specific build."""
    idx = _get_card_index(ctx)
    svc = _get_services(ctx)
    target_build = build or svc.td_build
    if not target_build:
        return {"error": "No build specified and current build unknown"}
    result = idx.check_compatibility(op_type, target_build)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {**result, "provenance": provenance.to_dict()}


# ── POPx Brain Tools ─────────────────────────────────────────────────


def _get_popx_brain(ctx: Context):
    svc = _get_services(ctx)
    return getattr(svc, "popx_brain", None)


@mcp.tool(name="td_search_popx_docs")
async def td_search_popx_docs(
    ctx: Context,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search POPx operator documentation — GPU particles, falloffs, simulations."""
    brain = _get_popx_brain(ctx)
    if brain is None:
        return {"error": "POPx brain not installed. Run 'npx tdpilot brains add popx' to enable.", "results": [], "count": 0}
    results = brain.search(query, limit=limit)
    svc = _get_services(ctx)
    provenance = Provenance(source="popx_brain", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_popx_operator")
async def td_get_popx_operator(
    ctx: Context,
    operator_name: str,
) -> dict[str, Any]:
    """Get full documentation for a POPx operator (e.g. 'Particle SIM', 'Shape Falloff')."""
    brain = _get_popx_brain(ctx)
    if brain is None:
        return {"error": "POPx brain not installed. Run 'npx tdpilot brains add popx' to enable."}
    results = brain.search(operator_name, limit=5)
    op_results = [r for r in results if r.get("operator_name", "").lower() == operator_name.lower()]
    if not op_results:
        op_results = results
    svc = _get_services(ctx)
    provenance = Provenance(source="popx_brain", td_build=svc.td_build)
    if op_results:
        return {"operator": op_results[0], "related": op_results[1:], "provenance": provenance.to_dict()}
    return {"error": f"No POPx operator found for '{operator_name}'", "provenance": provenance.to_dict()}


# ── paketa12 Tutorial Brain Tools ────────────────────────────────────


def _get_paketa12_brain(ctx: Context):
    svc = _get_services(ctx)
    return getattr(svc, "paketa12_brain", None)


@mcp.tool(name="td_search_paketa12")
async def td_search_paketa12(
    ctx: Context,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search paketa12 tutorial knowledge — GPU-texture-as-compute, UV math, simulations, GLSL techniques, feedback loops, algorithmic art in TouchDesigner."""
    brain = _get_paketa12_brain(ctx)
    if brain is None:
        return {"error": "paketa12 brain not installed. Run 'npx tdpilot brains add paketa12' to enable.", "results": [], "count": 0}
    results = brain.search(query, limit=limit)
    svc = _get_services(ctx)
    provenance = Provenance(source="paketa12_brain", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_paketa12_tutorial")
async def td_get_paketa12_tutorial(
    ctx: Context,
    topic: str,
) -> dict[str, Any]:
    """Get tutorial chunks for a paketa12 topic (e.g. 'Physarum simulation', 'Verlet integration', 'UV shredder', 'circle packing')."""
    brain = _get_paketa12_brain(ctx)
    if brain is None:
        return {"error": "paketa12 brain not installed. Run 'npx tdpilot brains add paketa12' to enable."}
    results = brain.search(topic, limit=10)
    # Group by tutorial (page_id)
    tutorials: dict[str, list] = {}
    for r in results:
        pid = r.get("page_id", "unknown")
        tutorials.setdefault(pid, []).append(r)
    svc = _get_services(ctx)
    provenance = Provenance(source="paketa12_brain", td_build=svc.td_build)
    return {
        "topic": topic,
        "tutorials_found": len(tutorials),
        "chunks": results,
        "provenance": provenance.to_dict(),
    }


@mcp.tool(name="td_describe_surface")
async def td_describe_surface(ctx: Context) -> dict[str, Any]:
    """Describe the MCP server surface: tool count, resource count, capabilities, version."""
    from td_mcp import __version__
    svc = _get_services(ctx)
    caps = detect_capabilities(ctx, td_build=svc.td_build)
    # FastMCP exposes registered tools/resources via its internal managers.
    # Previous attempts used ``mcp._tools``/``mcp._resources`` which don't exist,
    # so the counts always returned 0. Prefer the public-ish manager APIs and
    # fall back to 0 only if the SDK layout changes.
    tool_count = 0
    resource_count = 0
    prompt_count = 0
    try:
        tool_mgr = getattr(mcp, "_tool_manager", None)
        if tool_mgr is not None:
            tool_count = len(tool_mgr.list_tools())
    except Exception:
        tool_count = 0
    try:
        resource_mgr = getattr(mcp, "_resource_manager", None)
        if resource_mgr is not None:
            resources = list(resource_mgr.list_resources())
            templates = list(resource_mgr.list_templates())
            resource_count = len(resources) + len(templates)
    except Exception:
        resource_count = 0
    try:
        prompt_mgr = getattr(mcp, "_prompt_manager", None)
        if prompt_mgr is not None:
            prompt_count = len(prompt_mgr.list_prompts())
    except Exception:
        prompt_count = 0
    return {
        "version": __version__,
        "tool_count": tool_count,
        "resource_count": resource_count,
        "prompt_count": prompt_count,
        "capabilities": caps.to_dict(),
    }


# ─────────────────────────────────────────────────────────────
# Planning & Validation Tools (72-75)
# ─────────────────────────────────────────────────────────────

# Heuristic intent → macro-template matches. When td_plan_patch is called
# without a recipe_id, these keyword rules produce a concrete suggested step
# instead of returning an empty steps list, which was the most confusing
# part of the old behavior (the caller didn't know the tool was waiting on
# a recipe_id or memory query).
_INTENT_MACRO_KEYWORDS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("feedback displ", "feedback-displacement", "feedback_displacement"),
     "feedback_displacement", "Classic feedback displacement with source noise and composite merge."),
    (("feedback", "trail", "echo"),
     "feedback_loop", "Classic feedback chain: feedback → level → composite → out."),
    (("post-process", "post process", "post_processing", "grade", "bloom blur", "color grade"),
     "post_processing", "Simple post-FX chain: level → blur → out."),
    (("audio reactive", "audio-react", "audio_reactive", "audio analysis"),
     "audio_reactive", "Audio signal preprocessing chain with gain stage and null output."),
    (("particle", "gpu particle", "pop simulation", "particles"),
     "particle_gpu", "Minimal POP chain: particle → noise → render."),
)


def _suggest_macro_for_intent(intent: str) -> dict[str, str] | None:
    """Return a suggested macro match for the intent, or None."""
    text = (intent or "").lower()
    for keywords, macro_type, summary in _INTENT_MACRO_KEYWORDS:
        if any(k in text for k in keywords):
            return {"macro_type": macro_type, "summary": summary}
    return None


@mcp.tool(name="td_plan_patch")
async def td_plan_patch(params: PlanPatchInput, ctx: Context) -> dict[str, Any]:
    """Generate a structured patch plan for an intent without mutating the project.

    Inspects the current state of the target path, validates op types against the
    knowledge corpus, and optionally loads a recipe to generate ordered steps. Returns
    a plan dict that can be validated with td_preflight_patch before execution.

    When no ``recipe_id`` is provided, the tool also performs keyword-based macro
    matching against the intent so callers always get at least one actionable
    suggestion (either a concrete step list or a macro hint).
    """
    finish = _start_tool(ctx, "td_plan_patch")
    try:
        client = _get_client(ctx)
        svc = _get_services(ctx)
        idx = getattr(svc, "card_index", None)

        # Inspect current state of the target path
        current_nodes = []
        try:
            node_data = await client.request("nodes", {"path": params.target_path, "limit": 200})
            current_nodes = node_data if isinstance(node_data, list) else node_data.get("nodes", [])
        except Exception:
            current_nodes = []

        existing_names = {n.get("name", "") for n in current_nodes if isinstance(n, dict)}

        # If a recipe_id is provided, load it and generate steps from its nodes
        recipe_steps = []
        recipe_info = None
        if params.recipe_id:
            try:
                store = _get_technique_store(ctx)
                recipe_info = store.get(params.recipe_id, scope="project")
                if recipe_info is None:
                    recipe_info = store.get(params.recipe_id, scope="global")
                if recipe_info:
                    tech = recipe_info.get("technique", {})
                    recipe_data = tech.get("recipe", {}) if isinstance(tech, dict) else {}
                    nodes = recipe_data.get("nodes", {})
                    if isinstance(nodes, dict):
                        nodes = list(nodes.values())
                    for node in nodes:
                        op_type = node.get("type", "")
                        card_ok = True
                        if idx is not None:
                            card_ok = idx.get_operator(op_type) is not None
                        recipe_steps.append({
                            "op": "create_node",
                            "op_type": op_type,
                            "name": node.get("name", ""),
                            "parent_path": params.target_path,
                            "known_to_knowledge_corpus": card_ok,
                        })
            except Exception as exc:
                recipe_info = {"error": str(exc)}

        # If no recipe was provided or it didn't yield steps, fall back to
        # intent-keyword macro matching so we never return empty steps.
        macro_suggestion = None
        if not recipe_steps:
            macro_suggestion = _suggest_macro_for_intent(params.intent)
            if macro_suggestion is not None:
                recipe_steps.append({
                    "op": "create_macro",
                    "macro_type": macro_suggestion["macro_type"],
                    "parent_path": params.target_path,
                    "summary": macro_suggestion["summary"],
                    "source": "intent_heuristic",
                })

        # Collect actionable next-step hints the caller can use when steps is
        # still empty (no recipe + no heuristic match).
        next_actions: list[str] = []
        if not recipe_steps:
            next_actions.extend([
                "Search the technique library: td_memory_recall(query='<keyword>').",
                "List built-in macros: td_list_macros (see td_get_macro_params for options).",
                "If you already have a recipe, pass recipe_id= to td_plan_patch.",
            ])

        plan = {
            "intent": params.intent,
            "target_path": params.target_path,
            "recipe_id": params.recipe_id,
            "current_node_count": len(current_nodes),
            "existing_names": sorted(existing_names),
            "steps": recipe_steps,
            "note": (
                "This plan does NOT mutate the project. "
                "Validate with td_preflight_patch before execution."
            ),
        }
        if macro_suggestion is not None:
            plan["macro_suggestion"] = macro_suggestion
        if next_actions:
            plan["next_actions"] = next_actions
        if isinstance(recipe_info, dict) and "error" not in recipe_info:
            plan["recipe_name"] = recipe_info.get("name", "")

        _audit_log(ctx, "td_plan_patch", {"intent": params.intent, "target_path": params.target_path})
        return {"success": True, "plan": plan}
    except Exception as exc:
        _record_tool_error(ctx, "td_plan_patch")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_preflight_patch")
async def td_preflight_patch(params: PreflightPatchInput, ctx: Context) -> dict[str, Any]:
    """Validate a plan from td_plan_patch before execution.

    Checks that the target path exists, all op types in steps have knowledge cards,
    and that there are no name conflicts with existing nodes. Returns a validation
    report with any warnings or errors found.
    """
    finish = _start_tool(ctx, "td_preflight_patch")
    try:
        client = _get_client(ctx)
        svc = _get_services(ctx)
        idx = getattr(svc, "card_index", None)

        plan = params.plan
        target_path = plan.get("target_path", "/project1")
        steps = plan.get("steps", [])
        existing_names = set(plan.get("existing_names", []))

        warnings = []
        errors = []

        # Check target path exists
        path_exists = False
        try:
            node_data = await client.request("nodes", {"path": target_path, "limit": 200})
            path_exists = True
            # Refresh existing names from live state
            live_nodes = node_data if isinstance(node_data, list) else node_data.get("nodes", [])
            for n in live_nodes:
                if isinstance(n, dict):
                    existing_names.add(n.get("name", ""))
        except Exception:
            errors.append(f"Target path '{target_path}' does not exist or is unreachable.")

        # Validate each step
        for i, step in enumerate(steps):
            op_type = step.get("op_type", "")
            name = step.get("name", "")

            # Check knowledge card
            if op_type and idx is not None:
                card = idx.get_operator(op_type)
                if card is None:
                    warnings.append(
                        f"Step {i}: op_type '{op_type}' has no knowledge card — verify it is a valid TD operator."
                    )

            # Check name conflicts
            if name and name in existing_names:
                warnings.append(
                    f"Step {i}: name '{name}' already exists at '{target_path}' — will need rename."
                )

        valid = len(errors) == 0
        _audit_log(ctx, "td_preflight_patch", {
            "target_path": target_path,
            "steps": len(steps),
            "valid": valid,
        })
        return {
            "success": True,
            "valid": valid,
            "path_exists": path_exists,
            "errors": errors,
            "warnings": warnings,
            "step_count": len(steps),
        }
    except Exception as exc:
        _record_tool_error(ctx, "td_preflight_patch")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_validate_recipe")
async def td_validate_recipe(params: ValidateRecipeInput, ctx: Context) -> dict[str, Any]:
    """Validate a technique recipe from the library or an inline dict.

    Checks that required op types exist in the knowledge corpus, verifies the recipe
    has the expected structure, and reports build compatibility for current TD version.
    """
    finish = _start_tool(ctx, "td_validate_recipe")
    try:
        svc = _get_services(ctx)
        idx = getattr(svc, "card_index", None)

        recipe = params.recipe
        recipe_id = params.recipe_id

        # Load recipe from store if recipe_id provided and no inline recipe
        if recipe is None and recipe_id:
            try:
                store = _get_technique_store(ctx)
                recipe = store.get(recipe_id, scope=params.scope)
                if recipe is None and params.scope != "global":
                    recipe = store.get(recipe_id, scope="global")
            except Exception as exc:
                return {"error": f"Could not load recipe '{recipe_id}': {exc}"}

        if recipe is not None and "technique" in recipe:
            recipe = recipe.get("technique", {}).get("recipe", recipe)

        if recipe is None:
            return {"error": "No recipe provided (supply recipe_id or inline recipe dict)."}

        errors = []
        warnings = []

        # Check required structure fields
        for field in ("name", "nodes"):
            if field not in recipe:
                warnings.append(f"Recipe missing field: '{field}'")

        # Validate each node op_type against knowledge corpus
        nodes = recipe.get("nodes", {})
        if isinstance(nodes, dict):
            node_items = nodes.values()
        elif isinstance(nodes, list):
            node_items = nodes
        else:
            node_items = []
        unknown_types = []
        compat_issues = []

        for node in node_items:
            if not isinstance(node, dict):
                continue
            op_type = node.get("type", "")
            if not op_type:
                continue
            if idx is not None:
                card = idx.get_operator(op_type)
                if card is None:
                    unknown_types.append(op_type)
                else:
                    # Check build compatibility
                    if svc.td_build:
                        try:
                            compat = idx.check_compatibility(op_type, svc.td_build)
                            if compat.get("status") == "incompatible":
                                compat_issues.append({
                                    "op_type": op_type,
                                    "reason": compat.get("reason", "unknown"),
                                })
                        except Exception:
                            pass

        if unknown_types:
            warnings.append(
                f"Op types not found in knowledge corpus: {unknown_types}"
            )
        if compat_issues:
            warnings.append(
                f"Build compatibility issues: {compat_issues}"
            )

        valid = len(errors) == 0
        _audit_log(ctx, "td_validate_recipe", {
            "recipe_id": recipe_id,
            "scope": params.scope,
            "valid": valid,
        })
        return {
            "success": True,
            "valid": valid,
            "recipe_name": recipe.get("name", ""),
            "node_count": len(nodes),
            "unknown_op_types": unknown_types,
            "compat_issues": compat_issues,
            "errors": errors,
            "warnings": warnings,
        }
    except Exception as exc:
        _record_tool_error(ctx, "td_validate_recipe")
        return {"error": str(exc)}
    finally:
        finish()


# Stock TouchDesigner op types that should never be flagged as "unknown".
# The knowledge corpus intermittently indexes these by display name rather
# than by ``type`` field (e.g. "Box SOP" not "box"), which caused every stock
# audit to report 8+ common ops as unknown. This allowlist short-circuits
# that check. Sourced from the v1.3.4 td_list_families canonical set plus
# common operator types that appear across POP/SOP/TOP/CHOP/DAT/MAT/COMP.
_STOCK_OP_TYPES: frozenset[str] = frozenset({
    # Universal
    "null", "in", "out", "select", "switch", "merge",
    # COMPs
    "base", "container", "geo", "window", "cam", "light", "text", "time",
    "ambient", "animation", "annotate", "button", "environment", "field",
    "geotext", "graph", "list", "opviewer", "parameter", "replicator",
    "slider", "table", "widget",
    # TOPs
    "constant", "noise", "ramp", "level", "blur", "composite", "displace",
    "feedback", "movefilein", "moviefilein", "moviefileout", "render",
    "renderpass", "renderselect", "rendersimple", "transform", "over",
    "add", "multiply", "subtract", "layer", "chopto", "popto", "flip",
    "fit", "crop", "edge", "emboss", "hsvadj", "hsvadjust", "hsvtorgb",
    "inside", "outside", "lookup", "rectangle", "circle", "cacheselect",
    "comp", "convolve", "cornerpin", "cube", "cubemap", "depth", "difference",
    "glslmulti", "glsl", "lumablur", "lumalevel", "math", "matte", "mirror",
    "monochrome", "normalmap", "pack", "panel", "point", "reorder",
    "resolution", "rgbkey", "rgbtohsv", "screen", "screengrab", "script",
    "ssao", "svg", "threshold", "tile", "tonemap",
    # CHOPs
    "wave", "analyze", "beat", "count", "datto", "delete",
    "envelope", "express", "hold", "info", "joystick", "keyframe", "lag",
    "limit", "logic", "midiin", "midiinmap", "midiout", "mousein",
    "object", "par", "perform", "rename", "renderpick", "replace",
    "resample", "shuffle", "speed", "timeline", "timeslice", "topto",
    "trail", "trigger",
    # SOPs (stock)
    "box", "sphere", "torus", "tube", "grid", "line", "filein", "texture",
    "copy", "trace", "extrude",
    # POPs (v1.3+)
    "attcombine", "attconvert", "attribute", "connectivity", "convert",
    "facet", "mathcombine", "mathmix", "normal", "normalize", "pattern",
    "pointgen", "pointgenerator", "primitive", "rerange",
    "triangulate",
    # MATs
    "phong", "pbr", "wireframe", "pointsprite",
    # DATs
    "execute", "chopexec", "datexec", "parexec", "opexec",
    "panelexec", "eval", "examine", "fifo", "fileout", "indices", "insert", "keyboardin", "opfind", "sort", "substitute",
    "transpose", "web", "webclient", "webserver", "websocket",
})


@mcp.tool(name="td_audit_project")
async def td_audit_project(params: AuditProjectInput, ctx: Context) -> dict[str, Any]:
    """Audit a project subtree: count nodes by family and op type, detect palette
    components, find errors, and check build compatibility.

    Returns a comprehensive audit report without mutating the project.
    """
    finish = _start_tool(ctx, "td_audit_project")
    try:
        client = _get_client(ctx)
        svc = _get_services(ctx)
        idx = getattr(svc, "card_index", None)

        # Recursively fetch all nodes in the subtree (breadth-first)
        all_nodes: list[dict[str, Any]] = []
        max_depth = 10
        try:
            queue: list[tuple] = [(params.root_path, 0)]
            visited: set = set()
            while queue:
                container_path, depth = queue.pop(0)
                if container_path in visited:
                    continue
                visited.add(container_path)
                node_data = await client.request("nodes", {"path": container_path, "limit": 500})
                children = node_data if isinstance(node_data, list) else node_data.get("nodes", [])
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    all_nodes.append(child)
                    # Recurse into COMPs (containers that can have children)
                    if depth < max_depth and child.get("isCOMP", False):
                        child_path = child.get("path", "")
                        if child_path and child_path not in visited:
                            queue.append((child_path, depth + 1))
        except Exception as exc:
            return {"error": f"Could not fetch nodes at '{params.root_path}': {exc}"}

        # Count by family and op type
        family_counts: dict[str, int] = {}
        op_type_counts: dict[str, int] = {}
        palette_components = []
        unknown_op_types = []
        compat_issues = []

        for node in all_nodes:
            if not isinstance(node, dict):
                continue
            family = node.get("family", "")
            op_type = node.get("type", "")

            if family:
                family_counts[family] = family_counts.get(family, 0) + 1
            if op_type:
                op_type_counts[op_type] = op_type_counts.get(op_type, 0) + 1

            # Detect palette components (heuristic: name starts with known palette patterns)
            name = node.get("name", "")
            if idx is not None and op_type:
                palette_card = idx.get_palette(op_type)
                if palette_card:
                    palette_components.append({"name": name, "op_type": op_type})

                # Check knowledge corpus. Only flag as unknown when the op type
                # is also not in the stock allowlist — the corpus may not have
                # an explicit card for every stock TD op but they're obviously
                # known to the system, so flagging them produces noise.
                card = idx.get_operator(op_type)
                if card is None and op_type.lower() not in _STOCK_OP_TYPES and op_type not in unknown_op_types:
                    unknown_op_types.append(op_type)
                elif card is not None and svc.td_build:
                    try:
                        compat = idx.check_compatibility(op_type, svc.td_build)
                        if compat.get("status") == "incompatible":
                            compat_issues.append({
                                "node": name,
                                "op_type": op_type,
                                "reason": compat.get("reason", "unknown"),
                            })
                    except Exception:
                        pass

        # Fetch errors for root
        node_errors = []
        try:
            err_data = await client.request("node/errors", {"path": params.root_path, "recurse": True, "max_depth": 10})
            if isinstance(err_data, list):
                node_errors = err_data
            elif isinstance(err_data, dict):
                node_errors = err_data.get("issues", [])
        except Exception:
            pass

        _audit_log(ctx, "td_audit_project", {
            "root_path": params.root_path,
            "node_count": len(all_nodes),
        })
        return {
            "success": True,
            "root_path": params.root_path,
            "total_nodes": len(all_nodes),
            "by_family": family_counts,
            "by_op_type": op_type_counts,
            "palette_components": palette_components,
            "unknown_op_types": unknown_op_types,
            "compat_issues": compat_issues,
            "node_errors": node_errors,
            "error_count": len(node_errors),
        }
    except Exception as exc:
        _record_tool_error(ctx, "td_audit_project")
        return {"error": str(exc)}
    finally:
        finish()


# ─────────────────────────────────────────────────────────────
# Vision Diagnostics (tools 76-77)
# ─────────────────────────────────────────────────────────────

@mcp.tool(name="td_capture_frame")
async def td_capture_frame(params: CaptureFrameInput, ctx: Context) -> str:
    """Capture a single frame from a TOP node and return metadata.

    Returns resolution, format, and byte size. If confirm=True, also includes
    the base64-encoded JPEG image data. Ask the user before setting confirm=True
    because image payloads consume significant model context tokens.
    """
    finish = _start_tool(ctx, "td_capture_frame")
    try:
        client = _get_client(ctx)
        data = await client.request(
            "screenshot",
            {"path": params.path, "quality": params.quality},
        )
        if isinstance(data, dict) and data.get("success"):
            result: dict[str, Any] = {
                "success": True,
                "path": data.get("path", params.path),
                "resolution": [
                    data.get("width", 0),
                    data.get("height", 0),
                ],
                "format": data.get("format", "jpeg"),
                "size_bytes": data.get("size_bytes", 0),
                "quality": params.quality,
            }
            if params.confirm:
                result["data_base64"] = data.get("data_base64", "")
            else:
                result["data_omitted"] = True
                result["note"] = (
                    "Set confirm=True to include base64 image data. "
                    "Each JPEG frame adds significant token cost."
                )
            return _as_json_output(result)
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_capture_frame")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_analyze_frame")
async def td_analyze_frame(params: AnalyzeFrameInput, ctx: Context) -> str:
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
    finish = _start_tool(ctx, "td_analyze_frame")
    try:
        client = _get_client(ctx)
        body: dict[str, Any] = {
            "path": params.path,
            "modes": params.modes,
        }
        if params.roi is not None:
            body["roi"] = params.roi
        if params.reference_path is not None:
            body["reference_path"] = params.reference_path
        data = await client.request("analyze_frame", body)
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_analyze_frame")
        return format_tool_error(exc)
    finally:
        finish()


def _check_exec_not_off() -> dict[str, Any] | None:
    """Return an error dict if exec_mode is 'off', else None."""
    if _current_exec_mode() == "off":
        return {"error": "Python execution is disabled (TD_MCP_EXEC_MODE=off)"}
    return None


_EXEC_MODE_RANK = {"off": 0, "restricted": 1, "standard": 2, "full": 3}


def _check_exec_mode_at_least(minimum: str, tool_name: str) -> dict[str, Any] | None:
    """Return a structured error dict if the configured exec mode is below ``minimum``.

    Several TD 2025 native-system tools (td_python_env_status, td_threading_status,
    td_logger_status, td_color_pipeline, td_component_standardize,
    td_tdresources_inspect) need ``import`` statements that restricted mode forbids.
    Prior behavior was to let the TD side reject the exec and bubble an opaque
    "restricted mode blocks import statements" string up to the caller, which
    gave no hint that the fix is a server-side env var. This helper surfaces the
    condition upfront with a structured, remediable response.
    """
    current = _current_exec_mode()
    required_rank = _EXEC_MODE_RANK.get(minimum, 0)
    current_rank = _EXEC_MODE_RANK.get(current, 0)
    if current_rank >= required_rank:
        return None
    return {
        "error": {
            "code": "EXEC_MODE_INSUFFICIENT",
            "message": (
                f"{tool_name} requires TD_MCP_EXEC_MODE={minimum!r} "
                f"(currently {current!r}). This tool uses Python imports that the "
                f"current mode blocks."
            ),
            "tool": tool_name,
            "current_mode": current,
            "required_mode": minimum,
            "remediation": (
                f"Set TD_MCP_EXEC_MODE={minimum} in the MCP server environment "
                "(and restart the server / TouchDesigner) before calling this tool."
            ),
        }
    }


def _rescue_exec_mode_error(
    exc: Exception,
    *,
    tool_name: str,
    required_mode: str,
) -> dict[str, Any] | None:
    """If ``exc`` is a TD-side exec-mode rejection, return a structured response.

    Returns None when the exception is unrelated to exec-mode policy. Pair with
    the ``except`` branches in each affected tool so the caller sees the same
    remediable EXEC_MODE_INSUFFICIENT payload regardless of whether the guard
    fired early or the TD side vetoed mid-request.
    """
    msg = str(exc).lower()
    tokens = (
        "restricted mode blocks",
        "standard mode blocks",
        "permissionerror",
        "python execution is disabled",
    )
    if not any(token in msg for token in tokens):
        return None
    return {
        "error": {
            "code": "EXEC_MODE_INSUFFICIENT",
            "message": (
                f"{tool_name} was rejected by the active exec-mode policy. "
                f"It requires TD_MCP_EXEC_MODE={required_mode!r}."
            ),
            "tool": tool_name,
            "required_mode": required_mode,
            "remediation": (
                f"Set TD_MCP_EXEC_MODE={required_mode} in the MCP server environment "
                "and restart the server."
            ),
            "underlying": str(exc),
        }
    }


# ─────────────────────────────────────────────────────────────
# TD 2025 Native System Tools (tools 78-83)
# ─────────────────────────────────────────────────────────────

@mcp.tool(name="td_python_env_status")
async def td_python_env_status(ctx: Context) -> dict[str, Any]:
    """Inspect the Python environment inside TouchDesigner: version, installed packages, env manager status.

    Requires 'full' exec mode — uses sys and pkg_resources which are not in the standard allowlist.
    """
    finish = _start_tool(ctx, "td_python_env_status")
    try:
        off_err = _check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _check_exec_mode_at_least("full", "td_python_env_status")
        if mode_err:
            return mode_err
        client = _get_client(ctx)
        code = (
            "import sys, json\n"
            "result = {\n"
            "    'python_version': sys.version,\n"
            "    'executable': sys.executable,\n"
            "    'paths': sys.path[:10],\n"
            "}\n"
            "try:\n"
            "    import pkg_resources\n"
            "    result['installed_packages'] = [str(d) for d in pkg_resources.working_set][:50]\n"
            "except Exception:\n"
            "    result['installed_packages'] = []\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "full"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _audit_log(ctx, "td_python_env_status", {})
        return data
    except Exception as exc:
        _record_tool_error(ctx, "td_python_env_status")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_threading_status")
async def td_threading_status(ctx: Context) -> dict[str, Any]:
    """Inspect the threading status inside TouchDesigner: active threads, cook rate.

    Requires 'full' exec mode — uses threading module which is not in the standard allowlist.
    """
    finish = _start_tool(ctx, "td_threading_status")
    try:
        off_err = _check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _check_exec_mode_at_least("full", "td_threading_status")
        if mode_err:
            return mode_err
        client = _get_client(ctx)
        code = (
            "import threading, json\n"
            "result = {\n"
            "    'active_thread_count': threading.active_count(),\n"
            "    'current_thread': threading.current_thread().name,\n"
            "    'thread_names': [t.name for t in threading.enumerate()],\n"
            "}\n"
            "try:\n"
            "    result['cook_rate'] = project.cookRate\n"
            "except Exception:\n"
            "    pass\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "full"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _audit_log(ctx, "td_threading_status", {})
        return data
    except Exception as exc:
        _record_tool_error(ctx, "td_threading_status")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_logger_status")
async def td_logger_status(ctx: Context) -> dict[str, Any]:
    """Inspect the Python logging configuration inside TouchDesigner: log level, handlers, registered loggers.

    Note: This inspects Python's logging module, not TD's native logging. Requires 'full' exec mode.
    """
    finish = _start_tool(ctx, "td_logger_status")
    try:
        off_err = _check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _check_exec_mode_at_least("full", "td_logger_status")
        if mode_err:
            return mode_err
        client = _get_client(ctx)
        code = (
            "import logging, json\n"
            "root_logger = logging.getLogger()\n"
            "result = {\n"
            "    'root_level': logging.getLevelName(root_logger.level),\n"
            "    'handler_count': len(root_logger.handlers),\n"
            "    'handlers': [type(h).__name__ for h in root_logger.handlers],\n"
            "    'loggers': list(logging.Logger.manager.loggerDict.keys())[:20],\n"
            "}\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "full"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _audit_log(ctx, "td_logger_status", {})
        return data
    except Exception as exc:
        _record_tool_error(ctx, "td_logger_status")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_tdresources_inspect")
async def td_tdresources_inspect(params: TDResourcesInspectInput, ctx: Context) -> dict[str, Any]:
    """Inspect TDResources available in the TouchDesigner installation: fonts, icons, defaults."""
    finish = _start_tool(ctx, "td_tdresources_inspect")
    try:
        off_err = _check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _check_exec_mode_at_least("standard", "td_tdresources_inspect")
        if mode_err:
            return mode_err
        client = _get_client(ctx)
        category_filter = params.category or ""
        safe_filter = json.dumps(category_filter)
        code = (
            "import json\n"
            "result = {'categories': {}, 'total_children': 0}\n"
            "try:\n"
            "    res = op('/sys/TDResources')\n"
            "    if res:\n"
            "        children = res.children\n"
            "        result['total_children'] = len(children)\n"
            "        filt = json.loads(" + repr(safe_filter) + ")\n"
            "        for child in children:\n"
            "            cat = child.type\n"
            "            if filt and filt.lower() not in child.name.lower() and filt.lower() not in cat.lower():\n"
            "                continue\n"
            "            if cat not in result['categories']:\n"
            "                result['categories'][cat] = []\n"
            "            result['categories'][cat].append(child.name)\n"
            "    else:\n"
            "        result['note'] = 'TDResources not found at /sys/TDResources'\n"
            "except Exception as e:\n"
            "    result['error'] = str(e)\n"
            "__result__ = json.dumps(result)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "standard"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        if isinstance(data, dict):
            data["mode"] = "live"
        _audit_log(ctx, "td_tdresources_inspect", {"category": params.category})
        return data
    except Exception as exc:
        _record_tool_error(ctx, "td_tdresources_inspect")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_component_standardize")
async def td_component_standardize(params: ComponentStandardizeInput, ctx: Context) -> dict[str, Any]:
    """Audit or fix COMP standardization: required custom parameters (Version, Help, Creator), extension, naming."""
    finish = _start_tool(ctx, "td_component_standardize")
    try:
        off_err = _check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _check_exec_mode_at_least("standard", "td_component_standardize")
        if mode_err:
            return mode_err
        client = _get_client(ctx)
        path = params.path
        fix = params.fix

        safe_path = json.dumps(path)
        audit_code = (
            "import json\n"
            "_path = json.loads(" + repr(safe_path) + ")\n"
            "result = {'path': _path, 'issues': [], 'fixed': []}\n"
            "try:\n"
            "    comp = op(_path)\n"
            "    if comp is None:\n"
            "        result['error'] = 'Node not found'\n"
            "    else:\n"
            "        for par_name in ('Version', 'Help', 'Creator'):\n"
            "            if not hasattr(comp.par, par_name):\n"
            "                result['issues'].append('Missing custom parameter: ' + par_name)\n"
            "        if not comp.name[0].isupper() and not comp.name[0].isdigit():\n"
            "            result['issues'].append('Name does not start with uppercase: ' + comp.name)\n"
            "        result['has_extension'] = bool(comp.extensions)\n"
            "        result['op_type'] = comp.type\n"
        )

        if fix:
            fix_code = (
                "        page = None\n"
                "        for p in comp.customPages:\n"
                "            if p.name == 'Meta':\n"
                "                page = p\n"
                "                break\n"
                "        if page is None:\n"
                "            page = comp.appendCustomPage('Meta')\n"
                "        for par_name in ('Version', 'Help', 'Creator'):\n"
                "            if not hasattr(comp.par, par_name):\n"
                "                page.appendStr(par_name, label=par_name)\n"
                "                result['fixed'].append('Added parameter: ' + par_name)\n"
            )
            audit_code = audit_code + fix_code

        audit_code = (
            audit_code
            + "        result['issue_count'] = len(result['issues'])\n"
            + "except Exception as e:\n"
            + "    result['error'] = str(e)\n"
            + "__result__ = json.dumps(result)"
        )

        async def _do_audit():
            resp = await client.request("exec", {"code": audit_code, "exec_mode": "standard"})
            raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                return {"raw": raw}

        if fix:
            data = await _with_undo_block(client, f"td_component_standardize:{path}", _do_audit)
        else:
            data = await _do_audit()

        _audit_log(ctx, "td_component_standardize", {"path": path, "fix": fix})
        return data
    except Exception as exc:
        _record_tool_error(ctx, "td_component_standardize")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_color_pipeline")
async def td_color_pipeline(params: ColorPipelineInput, ctx: Context) -> dict[str, Any]:
    """Inspect the color management pipeline in TouchDesigner: color space, gamma, display settings."""
    finish = _start_tool(ctx, "td_color_pipeline")
    try:
        off_err = _check_exec_not_off()
        if off_err:
            return off_err
        mode_err = _check_exec_mode_at_least("standard", "td_color_pipeline")
        if mode_err:
            return mode_err
        client = _get_client(ctx)
        code = (
            "import json\n"
            "result = {}\n"
            "result['defaultParameterColorSpace'] = getattr(project, 'defaultParameterColorSpace', None)\n"
            "result['workingColorSpace'] = getattr(project, 'workingColorSpace', None)\n"
            "result['editorWindowPixelFormat'] = getattr(project, 'editorWindowPixelFormat', None)\n"
            "result['sdrReferenceWhiteNits'] = getattr(project, 'sdrReferenceWhiteNits', None)\n"
            "result['hdrReferenceWhiteNits'] = getattr(project, 'hdrReferenceWhiteNits', None)\n"
            "# Legacy fallbacks\n"
            "result['monitorGamma'] = getattr(project, 'monitorGamma', None)\n"
            "__result__ = json.dumps(result, default=str)"
        )
        resp = await client.request("exec", {"code": code, "exec_mode": "standard"})
        raw = resp.get("result", "{}") if isinstance(resp, dict) else "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            data = {"raw": raw}
        _audit_log(ctx, "td_color_pipeline", {})
        return data
    except Exception as exc:
        _record_tool_error(ctx, "td_color_pipeline")
        return {"error": str(exc)}
    finally:
        finish()


# ─────────────────────────────────────────────────────────────
# Official Recommendation Tools (84-86)
# ─────────────────────────────────────────────────────────────


def _is_informative_card(card: dict) -> bool:
    """Return True only if the card has at least one non-empty identifying field.

    The knowledge corpus occasionally returns skeleton cards (every string field
    is ""). Emitting those as recommendations produces responses like
    ``"Consider using '': "`` which are useless. Filter them out here so
    callers see an honest ``count: 0`` + ``hint`` instead.
    """
    if not isinstance(card, dict):
        return False
    for key in ("op_type", "component_name", "display_name", "snippet_id", "summary"):
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


@mcp.tool(name="td_recommend_official_component")
async def td_recommend_official_component(params: RecommendOfficialInput, ctx: Context) -> dict[str, Any]:
    """Recommend official palette or built-in operator components for a given goal."""
    finish = _start_tool(ctx, "td_recommend_official_component")
    try:
        idx = _get_card_index(ctx)
        svc = _get_services(ctx)
        provenance = Provenance(source="local_card", td_build=svc.td_build)

        # Search palette components
        palette_results = idx.search(params.goal, card_types=["palette"], limit=5)
        # Search operators for built-in alternatives
        operator_results = idx.search(params.goal, card_types=["operators"], limit=5)

        recommendations = []
        for card in palette_results:
            if not _is_informative_card(card):
                continue
            recommendations.append({
                "type": "palette",
                "name": card.get("component_name", ""),
                "display_name": card.get("display_name", ""),
                "summary": card.get("summary", ""),
                "when_to_use": card.get("when_to_use", ""),
            })
        for card in operator_results:
            if not _is_informative_card(card):
                continue
            recommendations.append({
                "type": "operator",
                "name": card.get("op_type", ""),
                "display_name": card.get("display_name", ""),
                "summary": card.get("summary", ""),
                "family": card.get("family", ""),
            })

        payload: dict[str, Any] = {
            "success": True,
            "goal": params.goal,
            "recommendations": recommendations,
            "count": len(recommendations),
            "provenance": provenance.to_dict(),
        }
        if not recommendations:
            payload["hint"] = (
                "No informative palette or operator cards matched. Try "
                "td_search_official_docs for operator docs, td_lookup_palette_component "
                "for palette components, or td_memory_recall for saved techniques."
            )

        _audit_log(ctx, "td_recommend_official_component", {"goal": params.goal})
        return payload
    except Exception as exc:
        _record_tool_error(ctx, "td_recommend_official_component")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_find_official_example")
async def td_find_official_example(params: FindOfficialExampleInput, ctx: Context) -> dict[str, Any]:
    """Search for official examples and snippets matching a query."""
    finish = _start_tool(ctx, "td_find_official_example")
    try:
        idx = _get_card_index(ctx)
        svc = _get_services(ctx)
        provenance = Provenance(source="local_card", td_build=svc.td_build)

        # Search snippets
        snippet_results = idx.search(
            params.query,
            card_types=["snippets"],
            family=params.family,
            limit=5,
        )
        # Search palette for example components
        palette_results = idx.search(
            params.query,
            card_types=["palette"],
            family=params.family,
            limit=5,
        )

        examples = []
        for card in snippet_results:
            examples.append({
                "type": "snippet",
                "id": card.get("snippet_id", ""),
                "display_name": card.get("display_name", ""),
                "summary": card.get("summary", ""),
                "family": card.get("family", ""),
            })
        for card in palette_results:
            examples.append({
                "type": "palette_example",
                "name": card.get("component_name", ""),
                "display_name": card.get("display_name", ""),
                "summary": card.get("summary", ""),
            })

        _audit_log(ctx, "td_find_official_example", {"query": params.query, "family": params.family})
        return {
            "success": True,
            "query": params.query,
            "family": params.family,
            "examples": examples,
            "count": len(examples),
            "provenance": provenance.to_dict(),
        }
    except Exception as exc:
        _record_tool_error(ctx, "td_find_official_example")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_explain_better_way")
async def td_explain_better_way(params: ExplainBetterWayInput, ctx: Context) -> dict[str, Any]:
    """Suggest better official alternatives for a given intent, with gotcha warnings."""
    finish = _start_tool(ctx, "td_explain_better_way")
    try:
        idx = _get_card_index(ctx)
        svc = _get_services(ctx)
        provenance = Provenance(source="local_card", td_build=svc.td_build)

        # Search for official alternatives across all card types. Filter out
        # skeleton cards (every identifying field empty) so we don't emit
        # "Consider using '': " recommendations when the corpus has no match.
        raw_alternatives = idx.search(params.intent, limit=10)
        alternatives = [c for c in raw_alternatives if _is_informative_card(c)]

        # Extract gotchas from operator cards if current_plan mentions specific ops
        gotchas = []
        if params.current_plan:
            for card in idx.search(params.current_plan, card_types=["operators"], limit=10):
                if not _is_informative_card(card):
                    continue
                card_gotchas = card.get("common_gotchas", [])
                if card_gotchas:
                    op_name = card.get("op_type", card.get("display_name", ""))
                    for g in card_gotchas:
                        gotchas.append({"operator": op_name, "gotcha": g})

        # Build recommendation
        official_alternative = None
        if alternatives:
            top = alternatives[0]
            name = top.get("op_type") or top.get("component_name") or top.get("snippet_id", "")
            display_name = top.get("display_name", "") or name
            official_alternative = {
                "name": name,
                "display_name": display_name,
                "summary": top.get("summary", ""),
                "family": top.get("family", ""),
            }

        recommendation_parts: list[str] = []
        if official_alternative:
            label = official_alternative["display_name"] or official_alternative["name"]
            summary = official_alternative["summary"]
            if summary:
                recommendation_parts.append(f"Consider using '{label}': {summary}")
            else:
                recommendation_parts.append(f"Consider using '{label}'")
        if gotchas:
            recommendation_parts.append(
                f"Watch out for {len(gotchas)} known gotcha(s)."
            )
        recommendation = " ".join(recommendation_parts)

        payload: dict[str, Any] = {
            "success": True,
            "intent": params.intent,
            "current_plan": params.current_plan,
            "recommendation": recommendation,
            "official_alternative": official_alternative,
            "gotchas": gotchas,
            "provenance": provenance.to_dict(),
        }
        if not recommendation and not gotchas:
            payload["hint"] = (
                "No informative cards matched this intent. Try "
                "td_recommend_official_component with a broader goal, or "
                "td_memory_recall to look for saved techniques."
            )

        _audit_log(ctx, "td_explain_better_way", {"intent": params.intent})
        return payload
    except Exception as exc:
        _record_tool_error(ctx, "td_explain_better_way")
        return {"error": str(exc)}
    finally:
        finish()


# ─────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────

def main() -> None:
    """Run the MCP server via FastMCP."""
    mcp.run(transport=TD_TRANSPORT)
