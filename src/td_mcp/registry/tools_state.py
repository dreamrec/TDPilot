"""State / timescale / focus tools — aggregated scene state, beat/phrase
timing, and live "where the user is in TD" awareness.

Part of the v1.5.0 Phase 2 module split. v1.6.0 added focus + locations.

Tools in this module (4):
    td_get_state_vector     — cached aggregated scene-state diagnostic
    td_get_timescale_state  — beat/phrase phase from timeline + BPM hint
    td_get_focus            — current network pane, selection, project meta
    td_locations            — save/list/go/delete/rename per-project network
                              locations (host-side JSON storage)

``td_get_state_vector`` reads + writes ``_tr._STATE_VECTOR_CACHE`` (a
module-level dict in tool_registry.py). Module-attribute lookup keeps
the cache shared across requests.

``td_get_focus`` and ``td_locations(action=save|go)`` use TD's existing
``/api/exec`` endpoint (the same one that backs ``td_exec_python``).
This avoids a ``.tox`` rebuild requirement — they ship purely host-side.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import locations_store, tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


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
    """Aggregated scene state vector (cached for _tr.TD_STATE_VECTOR_TTL seconds)."""
    finish = _tr._start_tool(ctx, "td_get_state_vector")
    try:
        cache_key = path
        cached = _tr._STATE_VECTOR_CACHE.get(cache_key)
        now = time.time()

        if not force_refresh and cached:
            cached_at = float(cached.get("cached_at", 0.0) or 0.0)
            age = now - cached_at
            if age <= max(0.0, _tr.TD_STATE_VECTOR_TTL):
                payload = dict(cached["data"])
                payload["cache"] = {
                    "hit": True,
                    "age_sec": age,
                    "ttl_sec": _tr.TD_STATE_VECTOR_TTL,
                }
                return _tr._as_json_output(payload)

        state_vector = await _tr._build_state_vector(path, ctx)
        if len(_tr._STATE_VECTOR_CACHE) >= 100:
            _tr._STATE_VECTOR_CACHE.clear()
        _tr._STATE_VECTOR_CACHE[cache_key] = {
            "cached_at": now,
            "data": state_vector,
        }
        state_vector["cache"] = {
            "hit": False,
            "ttl_sec": _tr.TD_STATE_VECTOR_TTL,
        }
        return _tr._as_json_output(state_vector)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_state_vector")
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
    finish = _tr._start_tool(ctx, "td_get_timescale_state")
    try:
        timeline = await _tr._get_client(ctx).request("timeline")
        bpm = float(bpm_hint if bpm_hint is not None else 120.0)

        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timeline": timeline,
            "timescale": _tr._compute_timescale_from_timeline(
                timeline if isinstance(timeline, dict) else {},
                bpm=bpm,
                beats_per_bar=beats_per_bar,
            ),
            "notes": [
                "BPM is currently hint-based; use an external detector to feed live BPM.",
                "Beat/bar/phrase phases can drive modulation curves or macro transitions.",
            ],
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_timescale_state")
        return format_tool_error(exc)
    finally:
        finish()


# ── Focus + Locations (v1.6.0) ───────────────────────────────────────


_FOCUS_PROBE_CODE = """
def _safe(fn, d=None):
    try:
        return fn()
    except Exception:
        return d

pane = _safe(lambda: ui.panes.current)
owner = _safe(lambda: pane.owner) if pane else None
sel = _safe(lambda: list(owner.selectedChildren), []) if owner else []
sel_paths = []
for c in sel:
    p = _safe(lambda c=c: c.path)
    if p:
        sel_paths.append(p)

__result__ = {
    "active_pane_path": _safe(lambda: owner.path, "/") if owner else "/",
    "active_pane_type": _safe(lambda: pane.type) if pane else None,
    "selected_ops": sel_paths,
    "selected_first": sel_paths[0] if sel_paths else None,
    "project_name": _safe(lambda: project.name),
    "td_build": _safe(lambda: app.build),
    "fps_target": _safe(lambda: float(project.cookRate)),
    "timeline_state": _safe(lambda: "playing" if me.time.play else "paused"),
}
"""


async def _exec_focus_probe(ctx: Context) -> dict[str, Any]:
    """Run the focus-probe Python on TD and return the parsed result dict.

    Wraps the existing /api/exec endpoint so this works against any v1.4+
    .tox without a rebuild. Raises if the exec layer reports failure.
    """
    body = {"code": _FOCUS_PROBE_CODE, "exec_mode": _tr._current_exec_mode()}
    data = await _tr._get_client(ctx).request("exec", body)
    if not isinstance(data, dict) or not data.get("success"):
        err = data.get("error", "exec failed") if isinstance(data, dict) else str(data)
        raise RuntimeError(f"td_get_focus probe failed: {err}")
    result = data.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"td_get_focus probe returned non-dict: {type(result).__name__}")
    return result


@mcp.tool(name="td_get_focus")
async def td_get_focus(
    ctx: Context,
    include_pane_history: Annotated[
        bool,
        Field(
            default=False,
            description="Reserved for future use; pane-history capture is not yet wired.",
        ),
    ] = False,
) -> str:
    """Return where the user currently is in TouchDesigner: active network pane,
    selection, project metadata, timeline state. Reduces the cold-start tax of
    needing to ask the user 'what path are you working in?' before every patch."""
    finish = _tr._start_tool(ctx, "td_get_focus")
    try:
        focus = await _exec_focus_probe(ctx)
        return _tr._as_json_output(focus)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_focus")
        return format_tool_error(exc)
    finally:
        finish()


def _navigate_code(target_path: str) -> str:
    safe = target_path.replace('"', '\\"')
    return f"""
def _safe(fn, d=None):
    try:
        return fn()
    except Exception:
        return d

target = _safe(lambda: op("{safe}"))
if target is None or not _safe(lambda: target.valid, False):
    __result__ = {{"success": False, "error": "path not found or invalid", "path": "{safe}"}}
else:
    pane = _safe(lambda: ui.panes.current)
    if pane is None:
        __result__ = {{"success": False, "error": "no active pane", "path": "{safe}"}}
    else:
        ok = False
        last_err = None
        try:
            pane.owner = target
            ok = True
        except Exception as e:
            last_err = str(e)
        if not ok:
            try:
                target.openViewer()
                ok = True
            except Exception as e:
                last_err = str(e)
        __result__ = {{"success": ok, "error": None if ok else last_err, "navigated_to": "{safe}"}}
"""


async def _navigate_to(ctx: Context, target_path: str) -> dict[str, Any]:
    body = {"code": _navigate_code(target_path), "exec_mode": _tr._current_exec_mode()}
    data = await _tr._get_client(ctx).request("exec", body)
    if not isinstance(data, dict) or not data.get("success"):
        err = data.get("error", "exec failed") if isinstance(data, dict) else str(data)
        return {"success": False, "error": err}
    result = data.get("result")
    return result if isinstance(result, dict) else {"success": False, "error": "non-dict result"}


@mcp.tool(name="td_locations")
async def td_locations(
    ctx: Context,
    action: Annotated[
        str,
        Field(
            description=(
                "Action to perform: 'save' (capture current focus or override path), "
                "'list' (return all per-project locations), 'go' (navigate to a "
                "saved location), 'delete' (remove by name), or 'rename'."
            ),
        ),
    ],
    name: Annotated[
        str | None,
        Field(
            default=None,
            description="Location name. Required for save/go/delete/rename.",
        ),
    ] = None,
    new_name: Annotated[
        str | None,
        Field(
            default=None,
            description="New name (rename action only).",
        ),
    ] = None,
    path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Override path for the save action. Defaults to td_get_focus.active_pane_path."
            ),
        ),
    ] = None,
    description: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional human-readable note (save action).",
        ),
    ] = None,
) -> str:
    """Save, list, jump-to, rename, or delete named network locations per
    project. Storage is host-side JSON in ``~/.tdpilot/locations/<hash>.json``
    and survives session restarts. Pairs with td_get_focus to give the agent
    + user a shared spatial vocabulary for big projects."""
    finish = _tr._start_tool(ctx, "td_locations")
    try:
        action_norm = (action or "").strip().lower()
        valid_actions = {"save", "list", "go", "delete", "rename"}
        if action_norm not in valid_actions:
            return _tr._as_json_output(
                {
                    "success": False,
                    "error": f"invalid action '{action}', expected one of {sorted(valid_actions)}",
                }
            )

        # Resolve project identity from a focus probe (gets project_name).
        # If exec layer is unavailable, fall back to a generic key.
        project_name: str | None = None
        try:
            focus = await _exec_focus_probe(ctx)
            project_name = focus.get("project_name")
        except Exception:
            focus = {}

        store = locations_store.LocationsStore()
        project_hash, project_label = locations_store.derive_project_id(project_name)

        if action_norm == "list":
            entries = store.list_for_project(project_hash)
            return _tr._as_json_output(
                {
                    "success": True,
                    "action": "list",
                    "project_hash": project_hash,
                    "project_label": project_label,
                    "count": len(entries),
                    "locations": entries,
                }
            )

        if name is None or not name.strip():
            return _tr._as_json_output(
                {
                    "success": False,
                    "error": "name is required for save/go/delete/rename actions",
                }
            )
        name_norm = name.strip()

        if action_norm == "save":
            target_path = path or focus.get("active_pane_path") or "/"
            entry = store.save(
                project_hash=project_hash,
                project_label=project_label,
                name=name_norm,
                path=target_path,
                description=description,
            )
            return _tr._as_json_output(
                {
                    "success": True,
                    "action": "save",
                    "project_hash": project_hash,
                    "location": entry,
                }
            )

        if action_norm == "delete":
            removed = store.delete(project_hash, name_norm)
            return _tr._as_json_output(
                {
                    "success": removed,
                    "action": "delete",
                    "project_hash": project_hash,
                    "name": name_norm,
                    "error": None if removed else "no location with that name",
                }
            )

        if action_norm == "rename":
            if not new_name or not new_name.strip():
                return _tr._as_json_output(
                    {"success": False, "error": "new_name is required for rename"}
                )
            renamed = store.rename(project_hash, name_norm, new_name.strip())
            return _tr._as_json_output(
                {
                    "success": renamed,
                    "action": "rename",
                    "project_hash": project_hash,
                    "old_name": name_norm,
                    "new_name": new_name.strip(),
                    "error": None if renamed else "no location with that name",
                }
            )

        # action_norm == "go"
        target = store.get(project_hash, name_norm)
        if target is None:
            return _tr._as_json_output(
                {
                    "success": False,
                    "action": "go",
                    "error": f"no location named '{name_norm}'",
                }
            )
        nav = await _navigate_to(ctx, target["path"])
        return _tr._as_json_output(
            {
                "success": bool(nav.get("success")),
                "action": "go",
                "project_hash": project_hash,
                "location": target,
                "navigation": nav,
            }
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_locations")
        return format_tool_error(exc)
    finally:
        finish()
