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
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

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
    CustomParameterSpec,
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
    MacroType,
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
    ParamBound,
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
    await td_client.request("project/lifecycle", {"action": "start_undo_block", "name": label})
    try:
        result = await async_fn(*args)
        return result
    finally:
        try:
            await td_client.request("project/lifecycle", {"action": "end_undo_block"})
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

    # Technique memory — project_name resolution runs AFTER the TD info fetch
    # below so we can fall back to TD's actual project name when the env var is
    # unset (N6 audit: users shouldn't need to set TDPILOT_PROJECT_NAME
    # manually when TD is already telling us what the project is).
    memory_base = os.environ.get("TDPILOT_MEMORY_DIR", "")
    project_name = os.environ.get("TDPILOT_PROJECT_NAME", "")

    logger.info("TouchDesigner MCP server starting (TD %s:%s)", TD_HOST, TD_PORT)

    td_build = ""
    try:
        await td_client.health_check()
        logger.info("TouchDesigner connection healthy")
        try:
            info = await td_client.request("info")
            td_build = str(info.get("build", "")) if isinstance(info, dict) else ""
            # Derive project_name from live TD if env var is unset.
            if not project_name and isinstance(info, dict):
                raw_name = str(info.get("project_name", "") or "").strip()
                if raw_name:
                    # Strip the .toe suffix if present so the derived folder is
                    # clean. "NewProject.1.toe" → "NewProject.1".
                    if raw_name.lower().endswith(".toe"):
                        raw_name = raw_name[:-4]
                    project_name = raw_name
                    logger.info(
                        "Resolved project_name from TD: %r (TDPILOT_PROJECT_NAME unset)",
                        project_name,
                    )
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
                            server_version,
                            component_version,
                        )
                    else:
                        logger.info(
                            "Version match confirmed: server and TD component both v%s", server_version
                        )
        except Exception as exc:
            logger.debug("Could not fetch td_build at startup: %s", exc)
    except TouchDesignerConnectionError as exc:
        logger.warning("TouchDesigner not reachable at startup: %s", exc)

    # Stores init AFTER project_name fallback resolution (N6 audit).
    technique_store = TechniqueStore(
        base_dir=memory_base or None,
        project_name=project_name or None,
    )
    preference_store = PreferenceStore(
        base_dir=memory_base or None,
        project_name=project_name or None,
    )

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


async def _ensure_td_build(ctx: Context) -> str:
    """Return the current TD build string, lazily fetching it if unset.

    N2 audit: ``ServiceContainer.td_build`` is populated once at ``server_lifespan``
    startup. If the MCP server starts before TouchDesigner is reachable (common
    during plugin install / first launch), the initial fetch fails and the field
    stays empty for the entire session — which breaks knowledge-tool provenance
    and ``td_get_build_compatibility`` auto-detect. This helper refetches from
    the live TD client when the cached value is empty and caches the result
    back into the service container.
    """
    services = _get_services(ctx)
    cached = (services.td_build or "").strip()
    if cached:
        return cached
    client = services.td_client
    if not isinstance(client, TDClient):
        return ""
    try:
        info = await client.request("info")
    except Exception:
        return ""
    build = str(info.get("build", "")) if isinstance(info, dict) else ""
    if build:
        services.td_build = build
    return build


async def _ensure_project_scope(ctx: Context) -> None:
    """Lazily bind the memory stores to TD's current project name.

    Background: if the TDPilot server starts before TouchDesigner is reachable,
    `server_lifespan` constructs TechniqueStore and PreferenceStore with
    ``project_name=None``, and every project-scoped tool call fails with
    "TDPILOT_PROJECT_NAME is not set" for the whole session. This was observed
    live against the installed 1.4.0 server while TD *was* reachable — the
    startup-time resolution had silently skipped the fetch.

    Resolution: on every memory-tool call, if the stores are still unbound,
    fetch the project_name from TD on demand and rebind both stores in place.
    Idempotent if already bound. Silent on TD unreachable — tries again next
    call. The TD ``info`` request is cheap (<10ms loopback); no timer-based
    throttling added unless profiling shows it's needed.
    """
    services = _get_services(ctx)
    store = services.technique_store
    pref = services.preference_store
    # Nothing to do if either store is absent or already bound.
    if store is None or pref is None:
        return
    if getattr(store, "_project_name", None):
        return
    client = services.td_client
    if not hasattr(client, "request"):
        return
    try:
        info = await client.request("info")
    except Exception:
        return  # TD still unreachable; retry next call
    if not isinstance(info, dict):
        return
    raw = str(info.get("project_name", "") or "").strip()
    if not raw:
        return
    if raw.lower().endswith(".toe"):
        raw = raw[:-4]
    store.rebind_project_scope(raw)
    pref.rebind_project_scope(raw)
    logger.info("Lazily bound project scope to %r from live TD after startup miss", raw)


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


def _get_card_index(ctx: Context):
    """Per-request accessor for the knowledge CardIndex.

    Defined here (rather than in ``registry/tools_knowledge.py``) because
    several tools OUTSIDE the knowledge submodule (e.g.
    ``td_recommend_official_component``, ``td_find_official_example``,
    ``td_explain_better_way`` in planning/validation) still reference it.
    When those planning tools get extracted into their own submodule they
    can reach this helper via ``_tr._get_card_index(ctx)``.
    """
    svc = _get_services(ctx)
    idx = getattr(svc, "card_index", None)
    if idx is None:
        raise RuntimeError("Knowledge corpus not loaded")
    return idx


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
                "Do you want me to inspect live output frames now? This will increase token usage."
            ),
        }

    return {
        "mode": "metadata_only",
        "advice": (
            "Base64 frame payloads are omitted to reduce token usage. "
            "Call td_screenshot for on-demand frame inspection."
        ),
        "ask_user_prompt": (
            "Do you want me to inspect the visual output now? I can fetch a frame on demand."
        ),
    }


def _vision_confirmation_required_response() -> str:
    return _as_json_output(
        {
            "success": False,
            "requires_confirmation": True,
            "message": (
                "High-token vision mode was requested (include_image=true) without explicit confirmation."
            ),
            "ask_user_prompt": (
                "Do you want me to enable continuous full-frame output now? "
                "This can increase token usage significantly."
            ),
            "next_step": ("After user approval, call again with confirm_high_token_mode=true."),
        }
    )


def _capture_confirmation_required_response() -> str:
    return _as_json_output(
        {
            "success": False,
            "requires_confirmation": True,
            "message": ("Image capture was requested without explicit confirmation."),
            "ask_user_prompt": (
                "Do you want me to capture and inspect output now? This will add image payload tokens."
            ),
            "next_step": ("After user approval, call again with confirm_image_capture=true."),
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


def _build_health_section(
    fps: float,
    cooking_nodes: list,
    issues: list,
    recent_events: list,
) -> dict:
    """Build the health dict used by td_get_state_vector.

    Shares the v1.4.1 unstable heuristic with td_detect_instability so both
    endpoints always agree on whether the scene is healthy (N3 audit).
    """
    unstable, reasons, metrics = _compute_unstable_signal(fps, cooking_nodes, issues)
    return {
        "fps": fps,
        "issues_count": len(issues),
        "event_rate_per_sec": _event_rate_per_sec(recent_events),
        "unstable": unstable,
        "reasons": reasons,
        "target_fps": metrics["target_fps"],
        "frame_budget_ms": metrics["frame_budget_ms"],
        "top_cook_ms": metrics["top_cook_ms"],
        "critical_issues_count": int(metrics["critical_issues_count"]),
    }


def _compute_unstable_signal(
    fps: float,
    cooking_nodes: list,
    issues: list,
    target_fps: float | None = None,
) -> tuple[bool, list[str], dict[str, float]]:
    """Shared unstable-ness heuristic used by both td_detect_instability and
    td_get_state_vector.

    Returns ``(unstable, reasons, metrics)``. The computation mirrors the v1.4.1
    detect_instability logic exactly so both tools always agree (N3 audit).

    Unstable iff any of:
      - FPS missed target by >20%
      - any CRITICAL error (errors field non-empty; warnings ignored)
      - a single node's cook time exceeds the full frame budget
    """
    effective_target = float(target_fps or fps or 60.0) or 60.0
    frame_budget_ms = 1000.0 / effective_target if effective_target > 0 else 16.67

    all_cook = [
        node
        for node in cooking_nodes
        if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) > 0
    ]
    top_cook_ms = max(
        (float(node.get("cookTime", 0.0) or 0.0) for node in all_cook),
        default=0.0,
    )
    critical = [item for item in issues if isinstance(item, dict) and (item.get("errors") or "").strip()]

    fps_missed = effective_target > 0 and fps < effective_target * 0.8
    frame_blown = top_cook_ms >= frame_budget_ms
    unstable = fps_missed or frame_blown or bool(critical)

    reasons: list[str] = []
    if fps_missed:
        reasons.append(f"fps {fps:.1f} is below 80% of target {effective_target:.1f}")
    if frame_blown:
        reasons.append(f"top cook time {top_cook_ms:.2f}ms exceeds frame budget {frame_budget_ms:.2f}ms")
    if critical:
        reasons.append(f"{len(critical)} critical node error(s)")

    metrics = {
        "target_fps": effective_target,
        "frame_budget_ms": round(frame_budget_ms, 3),
        "top_cook_ms": round(top_cook_ms, 3),
        "critical_issues_count": float(len(critical)),
    }
    return unstable, reasons, metrics


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
        "health": _build_health_section(fps, top_nodes, issues, recent_events),
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
    if any(
        token in name
        for token in ("noise", "seed", "detail", "octave", "jitter", "blur", "radius", "feedback")
    ):
        roles.add("complexity")
    if any(
        token in name for token in ("phase", "speed", "period", "freq", "frequency", "beat", "pulse", "bpm")
    ):
        roles.add("motion_rhythm")
    if any(
        token in name for token in ("feedback", "gain", "opacity", "weight", "displace", "blur", "radius")
    ):
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
        {"path": path, "param": name, "value": value} for (path, name), value in sorted(final_values.items())
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


@mcp.tool(name="td_get_info")
async def td_get_info(ctx: Context) -> str:
    return await _forward(ctx, "td_get_info", "info")


@mcp.tool(name="td_list_families")
async def td_list_families(ctx: Context) -> str:
    return await _forward(ctx, "td_list_families", "families")


@mcp.tool(name="td_get_content")
async def td_get_content(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a DAT node", min_length=1),
    ],
) -> str:
    """Read DAT text/table content."""
    return await _forward(ctx, "td_get_content", "node/content", {"path": path})


@mcp.tool(name="td_set_content")
async def td_set_content(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a DAT node", min_length=1),
    ],
    text: Annotated[
        str | None,
        Field(
            default=None,
            description="Text content to write (for Text DATs, Script DATs, etc.)",
        ),
    ] = None,
    table: Annotated[
        list[list[str]] | None,
        Field(
            default=None,
            description="Table content as 2D array of strings (for Table DATs)",
        ),
    ] = None,
) -> str:
    """Write DAT text/table content."""
    body: dict[str, Any] = {"path": path}
    if text is not None:
        body["text"] = text
    if table is not None:
        body["table"] = table
    return await _forward(
        ctx,
        "td_set_content",
        "node/content/set",
        body,
        audit_event="td_set_content",
    )


@mcp.tool(name="td_custom_parameters")
async def td_custom_parameters(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a COMP with custom parameters", min_length=1),
    ],
    page: Annotated[
        str,
        Field(description="Custom page name", min_length=1, max_length=64),
    ],
    params: Annotated[
        list[CustomParameterSpec],
        Field(
            min_length=1,
            description=(
                "One or more parameter specifications to create on the page. "
                "Each spec has kind (float/int/toggle/menu/str/rgb/rgba/pulse/"
                "file/filesave/folder/chop/comp/dat/mat/header), name, and "
                "optional label/size/default/min/max."
            ),
        ),
    ],
) -> str:
    """Create or update a custom parameter page on a COMP."""
    # Re-instantiate so nested CustomParameterSpec.kind validator still runs.
    validated = CustomParametersInput(path=path, page=page, params=params)
    return await _forward(
        ctx,
        "td_custom_parameters",
        "custom-parameters",
        validated.model_dump(),
        audit_event="td_custom_parameters",
    )


@mcp.tool(name="td_exec_python")
async def td_exec_python(
    ctx: Context,
    code: Annotated[
        str,
        Field(
            description=(
                "Python code to execute in TouchDesigner's Python environment. "
                "Has access to: op(), ops(), project, app, absTime, me, "
                "parent(), mod, ui, tdu. "
                "Set __result__ = <value> to return a value to the caller. "
                'Example: \'__result__ = op("/project1/noise1").par.type.ev'
                "al()'"
            ),
            min_length=1,
            max_length=50000,
        ),
    ],
    timeout_ms: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "Optional per-call execution timeout in milliseconds. "
                "When omitted, TouchDesigner uses its configured default. "
                "Bounds: 100-60000 ms."
            ),
            ge=100,
            le=60000,
        ),
    ] = None,
) -> str:
    """Execute Python code inside TouchDesigner."""
    finish = _start_tool(ctx, "td_exec_python")
    try:
        _enforce_exec_mode(code)
        mode = _current_exec_mode()
        body: dict[str, Any] = {
            "code": code,
            "exec_mode": mode,
        }
        # Forward the per-call timeout only when the caller set one. Omitting
        # the key lets the TD-side choose its configured default.
        if timeout_ms is not None:
            body["timeout_ms"] = timeout_ms
        data = await _get_client(ctx).request("exec", body)
        _audit_log(
            ctx,
            "td_exec_python",
            {
                "exec_mode": mode,
                "code_length": len(code),
                "timeout_ms": timeout_ms,
            },
        )
        return _as_json_output(data)
    except Exception as exc:
        _record_tool_error(ctx, "td_exec_python")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_timeline")
async def td_timeline(ctx: Context) -> str:
    return await _forward(ctx, "td_timeline", "timeline")


@mcp.tool(name="td_timeline_set")
async def td_timeline_set(
    ctx: Context,
    action: Annotated[
        str | None,
        Field(
            default=None,
            description="Timeline action: 'play', 'pause', or 'frame' (set specific frame)",
        ),
    ] = None,
    frame: Annotated[
        int | None,
        Field(
            default=None,
            ge=0,
            description="Frame number to jump to (when action='frame')",
        ),
    ] = None,
    fps: Annotated[
        float | None,
        Field(default=None, gt=0, le=240, description="Set cook rate / FPS"),
    ] = None,
) -> str:
    """Control timeline playback: play/pause, jump to frame, set FPS."""
    body: dict[str, Any] = {}
    if action is not None:
        body["action"] = action
    if frame is not None:
        body["frame"] = frame
    if fps is not None:
        body["fps"] = fps
    return await _forward(
        ctx,
        "td_timeline_set",
        "timeline/set",
        body,
        audit_event="td_timeline_set",
    )


@mcp.tool(name="td_project_lifecycle")
async def td_project_lifecycle(
    ctx: Context,
    action: Annotated[
        str,
        Field(
            description=(
                "Lifecycle action: status, save, load, undo, redo, "
                "start_undo_block, end_undo_block, clear_undo"
            ),
            min_length=1,
        ),
    ],
    path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Project path for save/load. For save with no path, "
                "TouchDesigner will perform its default incremental save behavior."
            ),
        ),
    ] = None,
    save_external_toxs: Annotated[
        bool,
        Field(
            default=False,
            description="Also save external tox contents on save",
        ),
    ] = False,
    name: Annotated[
        str | None,
        Field(
            default=None,
            description="Undo block name when action=start_undo_block",
        ),
    ] = None,
    enable: Annotated[
        bool,
        Field(
            default=True,
            description="Whether a started undo block should record undo state",
        ),
    ] = True,
) -> str:
    """Save/load/undo/redo project lifecycle operations."""
    # Re-instantiate so the ProjectLifecycleInput custom @field_validator on
    # ``action`` (allowed-set check) still runs and lowercases the value.
    validated = ProjectLifecycleInput(
        action=action,
        path=path,
        save_external_toxs=save_external_toxs,
        name=name,
        enable=enable,
    )
    return await _forward(
        ctx,
        "td_project_lifecycle",
        "project/lifecycle",
        validated.model_dump(),
        audit_event="td_project_lifecycle",
    )


@mcp.tool(name="td_pulse_param")
async def td_pulse_param(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Node path", min_length=1),
    ],
    param: Annotated[
        str,
        Field(description="Parameter name to pulse", min_length=1),
    ],
) -> str:
    """Pulse a pulse-type parameter (e.g. a button par)."""
    return await _forward(
        ctx,
        "td_pulse_param",
        "pulse",
        {"path": path, "param": param},
        audit_event="td_pulse_param",
    )


@mcp.tool(name="td_python_help")
async def td_python_help(
    ctx: Context,
    target: Annotated[
        str,
        Field(
            description=("Python object/class to get help for (e.g. 'td', 'td.OP', 'tdu', 'td.TOP')"),
            min_length=1,
        ),
    ],
) -> str:
    """Get Python help documentation for a TD class/module."""
    return await _forward(ctx, "td_python_help", "python/help", {"target": target})


@mcp.tool(name="td_python_classes")
async def td_python_classes(ctx: Context) -> str:
    return await _forward(ctx, "td_python_classes", "python/classes")


# Extended tools


@mcp.tool(name="td_create_macro")
async def td_create_macro(
    ctx: Context,
    macro_type: Annotated[
        MacroType,
        Field(description="Macro template to create."),
    ],
    parent_path: Annotated[
        str,
        Field(
            default="/project1",
            description="Parent COMP path where the macro will be instantiated.",
        ),
    ] = "/project1",
    name: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional name prefix for all nodes created by this macro.",
        ),
    ] = None,
    nodeX: Annotated[
        int,
        Field(
            default=0,
            description="Macro origin X position in the network editor.",
        ),
    ] = 0,
    nodeY: Annotated[
        int,
        Field(
            default=0,
            description="Macro origin Y position in the network editor.",
        ),
    ] = 0,
    params: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Override template parameter defaults with custom values.",
        ),
    ] = None,
) -> str:
    """Create a macro template network."""
    finish = _start_tool(ctx, "td_create_macro")
    try:
        engine = _get_macro_engine(ctx)
        data = await engine.create_macro(
            parent_path=parent_path,
            macro_type=macro_type.value,
            name_prefix=name,
            node_x=nodeX,
            node_y=nodeY,
            overrides=params,
        )
        _audit_log(
            ctx,
            "td_create_macro",
            {
                "macro_type": macro_type.value,
                "parent_path": parent_path,
                "name_prefix": name,
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
async def td_get_macro_params(
    ctx: Context,
    macro_type: Annotated[
        MacroType,
        Field(description="Macro template to inspect."),
    ],
) -> str:
    """Inspect parameter schema for a macro template."""
    finish = _start_tool(ctx, "td_get_macro_params")
    try:
        data = _get_macro_engine(ctx).get_macro_params(macro_type.value)
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
async def td_subscribe(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TD node path to monitor, e.g. '/project1/audio1'."),
    ],
    event_types: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Event types: chop_change, par_change, cook_complete, "
                "node_error, timeline. Defaults to ['chop_change', 'par_change']."
            ),
        ),
    ] = None,
    channels: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Specific CHOP channels to monitor. None means all channels.",
        ),
    ] = None,
    params: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Specific parameters to monitor. None means all tracked params.",
        ),
    ] = None,
    threshold: Annotated[
        float | None,
        Field(
            default=None,
            description="Only emit events when delta exceeds this threshold.",
        ),
    ] = None,
    rate_limit: Annotated[
        float,
        Field(
            default=0.016,
            ge=0.001,
            le=10.0,
            description="Minimum seconds between repeated events from same source.",
        ),
    ] = 0.016,
) -> str:
    """Subscribe to runtime TD events for a node."""
    # Re-instantiate so the SubscribeInput @field_validator on event_types
    # (allowed set: chop_change|par_change|cook_complete|node_error|timeline)
    # still runs.
    validated = SubscribeInput(
        path=path,
        event_types=event_types or ["chop_change", "par_change"],
        channels=channels,
        params=params,
        threshold=threshold,
        rate_limit=rate_limit,
    )
    finish = _start_tool(ctx, "td_subscribe")
    try:
        body = validated.model_dump(exclude_none=True)
        provisioning = await _get_client(ctx).request("monitor/subscribe", body)

        event_manager = _get_event_manager(ctx)
        for et in validated.event_types:
            event_manager.register_subscription(validated.path, et, body)

        payload = {
            "success": True,
            "path": validated.path,
            "subscription": body,
            "resource_uris": _build_subscription_resource_uris(validated),
            "provisioning": provisioning,
            "active_subscriptions": len(event_manager.list_subscriptions()),
        }
        _audit_log(
            ctx,
            "td_subscribe",
            {
                "path": validated.path,
                "event_types": validated.event_types,
            },
        )
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_subscribe")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_unsubscribe")
async def td_unsubscribe(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="TD node path to stop monitoring."),
    ],
) -> str:
    """Remove a node subscription."""
    finish = _start_tool(ctx, "td_unsubscribe")
    try:
        provisioning = await _get_client(ctx).request(
            "monitor/unsubscribe",
            {"path": path},
        )

        event_manager = _get_event_manager(ctx)
        removed = event_manager.unregister_all_for_path(path)

        payload = {
            "success": removed > 0,
            "path": path,
            "provisioning": provisioning,
            "active_subscriptions": len(event_manager.list_subscriptions()),
        }
        _audit_log(ctx, "td_unsubscribe", {"path": path})
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_unsubscribe")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_events")
async def td_get_events(
    ctx: Context,
    event_type: Annotated[
        str | None,
        Field(default=None, description="Optional event type filter."),
    ] = None,
    limit: Annotated[
        int,
        Field(
            default=50,
            ge=1,
            le=1000,
            description="Maximum number of events to return.",
        ),
    ] = 50,
) -> str:
    """Read recent event history."""
    finish = _start_tool(ctx, "td_get_events")
    try:
        manager = _get_event_manager(ctx)
        events = manager.get_recent_events(event_type=event_type, limit=limit)
        payload = {
            "schema_version": 1,
            "event_type": event_type,
            "count": len(events),
            "events": events,
        }
        return _as_json_output(payload)
    except Exception as exc:
        _record_tool_error(ctx, "td_get_events")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_state_vector")
async def td_get_state_vector(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            default="/project1",
            description="Root path for aggregated diagnostics.",
        ),
    ] = "/project1",
    force_refresh: Annotated[
        bool,
        Field(
            default=False,
            description="Bypass cache and fetch fresh state.",
        ),
    ] = False,
) -> str:
    """Aggregated scene state vector (cached for TD_STATE_VECTOR_TTL seconds)."""
    finish = _start_tool(ctx, "td_get_state_vector")
    try:
        cache_key = path
        cached = _STATE_VECTOR_CACHE.get(cache_key)
        now = time.time()

        if not force_refresh and cached:
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

        state_vector = await _build_state_vector(path, ctx)
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
async def td_get_timescale_state(
    ctx: Context,
    bpm_hint: Annotated[
        float | None,
        Field(
            default=None,
            gt=0.0,
            le=400.0,
            description="Optional BPM hint. Defaults to 120 when omitted.",
        ),
    ] = None,
    beats_per_bar: Annotated[
        int,
        Field(
            default=4,
            ge=1,
            le=32,
            description="Musical beats per bar for phase calculations.",
        ),
    ] = 4,
) -> str:
    """Beat/phrase derived timeline state."""
    finish = _start_tool(ctx, "td_get_timescale_state")
    try:
        timeline = await _get_client(ctx).request("timeline")
        bpm = float(bpm_hint if bpm_hint is not None else 120.0)

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
                f"Set TD_MCP_EXEC_MODE={required_mode} in the MCP server environment and restart the server."
            ),
            "underlying": str(exc),
        }
    }


# ─────────────────────────────────────────────────────────────
# Registry submodules (v1.5.0 Phase 2 module split)
# ─────────────────────────────────────────────────────────────
# Side-effect imports — each submodule registers its @mcp.tool
# handlers on the shared ``mcp`` instance at import time. Placed
# HERE (after all helpers + remaining in-file tool definitions) so
# that the submodules' ``from td_mcp.tool_registry import ...`` calls
# see fully-initialized names in the partial module cache. See
# src/td_mcp/registry/__init__.py for the full explanation.
# Side-effect import registers the @mcp.tool decorators on the shared
# ``mcp`` instance. The explicit name imports below re-export the tool
# functions at module level so callers using ``from td_mcp import
# tool_registry as registry; registry.td_memory_save(...)`` still work.
# Resource handlers registered via @mcp.resource. Re-exported so tests
# like test_resource_fallbacks.py that import by Python name keep working.
from td_mcp.registry.resources import (  # noqa: E402
    td_resource_chop_channel,
    td_resource_cook,
    td_resource_error,
    td_resource_job,
    td_resource_parameter,
    td_resource_timeline,
    td_resource_top_frame,
)
from td_mcp.registry.tools_data import (  # noqa: E402
    td_chop_data,
    td_cooking_info,
    td_geometry_data,
    td_get_errors,
    td_pop_inspect,
    td_screenshot,
    td_search_nodes,
)
from td_mcp.registry.tools_graph import (  # noqa: E402
    td_connect_nodes,
    td_copy_node,
    td_create_node,
    td_delete_node,
    td_disconnect,
    td_get_connections,
    td_get_node_detail,
    td_get_nodes,
    td_get_params,
    td_rename_node,
    td_set_params,
)
from td_mcp.registry.tools_knowledge import (  # noqa: E402
    td_describe_surface,
    td_get_build_compatibility,
    td_get_operator_doc,
    td_get_paketa12_tutorial,
    td_get_param_help,
    td_get_popx_operator,
    td_get_release_delta,
    td_lookup_palette_component,
    td_lookup_snippets,
    td_search_official_docs,
    td_search_paketa12,
    td_search_popx_docs,
)
from td_mcp.registry.tools_memory import (  # noqa: E402
    td_memory_export,
    td_memory_favorite,
    td_memory_import,
    td_memory_learn,
    td_memory_list,
    td_memory_preferences,
    td_memory_promote,
    td_memory_recall,
    td_memory_replay,
    td_memory_save,
)
from td_mcp.registry.tools_optimizer import (  # noqa: E402
    td_describe_dynamics,
    td_optimize_visual,
)
from td_mcp.registry.tools_planning import (  # noqa: E402
    td_audit_project,
    td_plan_patch,
    td_preflight_patch,
    td_validate_recipe,
)
from td_mcp.registry.tools_recommendations import (  # noqa: E402
    _is_informative_card,
    td_explain_better_way,
    td_find_official_example,
    td_recommend_official_component,
)
from td_mcp.registry.tools_safety import (  # noqa: E402
    td_clear_param_bounds,
    td_detect_instability,
    td_emergency_stabilize,
    td_set_param_bounds,
)
from td_mcp.registry.tools_snapshots import (  # noqa: E402
    td_diff_snapshots,
    td_list_snapshots,
    td_restore_snapshot,
    td_snapshot_scene,
)
from td_mcp.registry.tools_streaming import (  # noqa: E402
    td_capture_and_analyze,
    td_monitor_visual,
    td_stop_monitor_visual,
    td_stop_stream_top,
    td_stream_top,
)
from td_mcp.registry.tools_system import (  # noqa: E402
    td_color_pipeline,
    td_component_standardize,
    td_logger_status,
    td_python_env_status,
    td_tdresources_inspect,
    td_threading_status,
)
from td_mcp.registry.tools_vision import (  # noqa: E402
    td_analyze_frame,
    td_capture_frame,
)

# ─────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server via FastMCP."""
    mcp.run(transport=TD_TRANSPORT)
