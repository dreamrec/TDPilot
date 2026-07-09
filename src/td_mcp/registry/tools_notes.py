"""Component notes tool — per-COMP markdown notes addressable from the agent.

``td_component_notes`` is a host-side dispatcher. Default storage is external
JSON in ``~/.tdpilot/component_notes/<project_hash>.json`` (no .toe bloat).
Optional ``embed=True`` mode also writes a hidden Text DAT named
``tdpilot_notes`` inside the target COMP — for that we round-trip via
``/api/exec`` so it works against any v1.4+ .tox without a rebuild.

Pairs with v1.6.0's ``td_search_nodes(scopes=['notes', ...])`` (future)
and ``td_get_node_detail(include_notes=True)``.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from td_mcp import component_notes_store, locations_store  # noqa: E402
from td_mcp import tool_registry as _tr
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


def _embed_code(comp_path: str, body: str, tags: list[str]) -> str:
    path_literal = json.dumps(comp_path)
    body_literal = json.dumps(body)
    tags_literal = json.dumps(list(tags or []))
    return f"""
def _safe(fn, d=None):
    try:
        return fn()
    except Exception:
        return d

target_path = {path_literal}
note_body = {body_literal}
note_tags = {tags_literal}

target = _safe(lambda: op(target_path))
if target is None or not _safe(lambda: target.valid, False):
    __result__ = {{"success": False, "error": "comp not found", "path": target_path}}
elif not _safe(lambda: target.isCOMP, False):
    __result__ = {{"success": False, "error": "target is not a COMP", "path": target_path}}
else:
    existing = _safe(lambda: target.op("tdpilot_notes"))
    if existing is None:
        try:
            dat = target.create(textDAT, "tdpilot_notes")
        except Exception as e:
            dat = None
            err = str(e)
        if dat is None:
            __result__ = {{"success": False, "error": err if 'err' in dir() else "create failed"}}
        else:
            try:
                dat.viewer = False
                dat.text = note_body
                __result__ = {{"success": True, "embedded_at": dat.path, "tags": note_tags}}
            except Exception as e:
                __result__ = {{"success": False, "error": "write failed: " + str(e)}}
    else:
        try:
            existing.text = note_body
            __result__ = {{"success": True, "embedded_at": existing.path, "tags": note_tags, "overwrote_existing": True}}
        except Exception as e:
            __result__ = {{"success": False, "error": "overwrite failed: " + str(e)}}
"""


async def _embed_to_dat(ctx: Context, comp_path: str, body: str, tags: list[str]) -> dict[str, Any]:
    code = _embed_code(comp_path, body, tags or [])
    payload = {"code": code, "exec_mode": _tr._current_exec_mode()}
    data = await _tr._get_client(ctx).request("exec", payload)
    if not isinstance(data, dict) or not data.get("success"):
        return {"success": False, "error": (data or {}).get("error", "exec failed")}
    result = data.get("result")
    return result if isinstance(result, dict) else {"success": False, "error": "non-dict result"}


_FOCUS_PROBE_PROJECT = """
def _safe(fn, d=None):
    try:
        return fn()
    except Exception:
        return d
__result__ = {"project_name": _safe(lambda: project.name)}
"""


async def _resolve_project_id(ctx: Context) -> tuple[str, str]:
    """Return (project_hash, project_label) for the live TD project."""
    try:
        body = {"code": _FOCUS_PROBE_PROJECT, "exec_mode": _tr._current_exec_mode()}
        data = await _tr._get_client(ctx).request("exec", body)
        if isinstance(data, dict) and data.get("success"):
            result = data.get("result") or {}
            if isinstance(result, dict):
                project_name = result.get("project_name")
                return locations_store.derive_project_id(project_name)
    except Exception:
        pass
    return locations_store.derive_project_id(None)


@mcp.tool(
    name="td_component_notes",
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
    ),
)
async def td_component_notes(
    ctx: Context,
    action: Annotated[
        str,
        Field(
            description=(
                "One of: 'get' (fetch a single note), 'set' (write/overwrite), "
                "'append' (append with timestamp divider), 'delete', 'index' "
                "(list every note for the project), 'summarize' (markdown digest)."
            ),
        ),
    ],
    path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "COMP path (required for get/set/append/delete; optional for "
                "summarize as a subtree filter; omit for index/summarize-all)."
            ),
        ),
    ] = None,
    body: Annotated[
        str | None,
        Field(
            default=None,
            description="Note body (markdown). Required for set/append.",
        ),
    ] = None,
    embed: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True (set action only), also write a hidden Text DAT named "
                "`tdpilot_notes` inside the target COMP. Lets the note travel "
                "with the .tox/.toe but bloats save files; default is external-only."
            ),
        ),
    ] = False,
    tags: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Optional tags for indexing/search (set/append actions).",
        ),
    ] = None,
) -> str:
    """Per-COMP markdown notes — what this subnet does, why it's wired this way,
    gotchas, TODOs. External JSON storage by default; ``embed=True`` also
    writes a hidden Text DAT inside the COMP for portability."""
    finish = _tr._start_tool(ctx, "td_component_notes")
    try:
        action_norm = (action or "").strip().lower()
        valid = {"get", "set", "append", "delete", "index", "summarize"}
        if action_norm not in valid:
            return _tr._as_json_output(
                {"success": False, "error": f"invalid action '{action}'", "expected": sorted(valid)}
            )

        project_hash, project_label = await _resolve_project_id(ctx)
        store = component_notes_store.ComponentNotesStore()

        if action_norm == "index":
            entries = store.index(project_hash)
            return _tr._as_json_output(
                {
                    "success": True,
                    "action": "index",
                    "project_hash": project_hash,
                    "project_label": project_label,
                    "count": len(entries),
                    "notes": entries,
                }
            )

        if action_norm == "summarize":
            md = store.summarize(project_hash, scope_path=path)
            return _tr._as_json_output(
                {
                    "success": True,
                    "action": "summarize",
                    "project_hash": project_hash,
                    "scope": path,
                    "markdown": md,
                }
            )

        if not path or not path.strip():
            return _tr._as_json_output(
                {"success": False, "error": "path is required for get/set/append/delete"}
            )
        comp_path = path.strip()

        if action_norm == "get":
            entry = store.get(project_hash, comp_path)
            return _tr._as_json_output(
                {
                    "success": entry is not None,
                    "action": "get",
                    "project_hash": project_hash,
                    "path": comp_path,
                    "note": entry,
                }
            )

        if action_norm == "delete":
            removed = store.delete(project_hash, comp_path)
            return _tr._as_json_output(
                {
                    "success": removed,
                    "action": "delete",
                    "project_hash": project_hash,
                    "path": comp_path,
                    "error": None if removed else "no note at that path",
                }
            )

        # set / append require body
        if not body or not body.strip():
            return _tr._as_json_output({"success": False, "error": "body is required for set/append"})
        body_norm = body

        if action_norm == "set":
            entry = store.set(
                project_hash=project_hash,
                project_label=project_label,
                comp_path=comp_path,
                body=body_norm,
                tags=tags,
                embedded=embed,
            )
            embed_result: dict[str, Any] | None = None
            if embed:
                embed_result = await _embed_to_dat(ctx, comp_path, body_norm, list(tags or []))
            return _tr._as_json_output(
                {
                    "success": True,
                    "action": "set",
                    "project_hash": project_hash,
                    "path": comp_path,
                    "note": entry,
                    "embed": embed_result,
                }
            )

        # action_norm == "append"
        entry = store.append(
            project_hash=project_hash,
            project_label=project_label,
            comp_path=comp_path,
            body=body_norm,
            tags=tags,
        )
        return _tr._as_json_output(
            {
                "success": True,
                "action": "append",
                "project_hash": project_hash,
                "path": comp_path,
                "note": entry,
            }
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_component_notes")
        return format_tool_error(exc)
    finally:
        finish()
