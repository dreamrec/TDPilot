"""Data/inspection tools — query TD state without mutation.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module (7):
    td_screenshot       — capture a TOP as JPEG
    td_chop_data        — read CHOP channel samples
    td_geometry_data    — read SOP/POP point + prim data
    td_pop_inspect      — structured POP metadata + attribute samples
    td_cooking_info     — performance / cook-time breakdown
    td_search_nodes     — find nodes by name/type/family
    td_get_errors       — list errors + warnings in a subtree

All 7 are essentially thin ``_forward()`` wrappers that pass through to
TD endpoints. The cleanest extraction so far — only one external helper
dependency (``_tr._forward``).
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.models import SearchNodesInput
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_screenshot")
async def td_screenshot(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            description=(
                "Path to a TOP node to capture as an image (e.g. '/project1/null1', '/project1/render1')"
            ),
            min_length=1,
        ),
    ],
    quality: Annotated[
        float,
        Field(
            default=0.5,
            ge=0.0,
            le=1.0,
            description=(
                "JPEG quality from 0.0 (smallest) to 1.0 (best). "
                "Default 0.5 gives good diagnostic quality at ~85KB."
            ),
        ),
    ] = 0.5,
) -> str:
    """Capture a TOP frame.

    Ask the user before repeated screenshots because each base64 image can
    consume significant tokens in model context.
    """
    return await _tr._forward(
        ctx,
        "td_screenshot",
        "screenshot",
        {"path": path, "quality": quality},
    )


@mcp.tool(name="td_chop_data")
async def td_chop_data(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a CHOP node", min_length=1),
    ],
    channels: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="List of channel names to read. If None, reads all channels.",
        ),
    ] = None,
    range: Annotated[
        list[int] | None,
        Field(
            default=None,
            description="Sample range [start, end] to read. If None, reads all samples.",
            min_length=2,
            max_length=2,
        ),
    ] = None,
) -> str:
    """Read CHOP channel data (values/samples)."""
    body: dict[str, Any] = {"path": path}
    if channels is not None:
        body["channels"] = channels
    if range is not None:
        body["range"] = range
    return await _tr._forward(ctx, "td_chop_data", "chop/data", body)


@mcp.tool(name="td_geometry_data")
async def td_geometry_data(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a SOP or POP node", min_length=1),
    ],
    include_points: Annotated[
        bool,
        Field(default=True, description="Include point position data"),
    ] = True,
    include_prims: Annotated[
        bool,
        Field(default=False, description="Include primitive data"),
    ] = False,
    limit: Annotated[
        int,
        Field(
            default=500,
            ge=1,
            le=10000,
            description="Max points/prims to return",
        ),
    ] = 500,
) -> str:
    """Read SOP/POP geometry data (points/prims)."""
    return await _tr._forward(
        ctx,
        "td_geometry_data",
        "geometry/data",
        {
            "path": path,
            "include_points": include_points,
            "include_prims": include_prims,
            "limit": limit,
        },
    )


@mcp.tool(name="td_pop_inspect")
async def td_pop_inspect(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Path to a POP node", min_length=1),
    ],
    include_bounds: Annotated[
        bool,
        Field(
            default=True,
            description="Include POP bounds and dimension metadata",
        ),
    ] = True,
    include_attributes: Annotated[
        bool,
        Field(
            default=True,
            description="Include point/prim/vert attribute metadata",
        ),
    ] = True,
    point_attributes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Specific point attributes to sample. If omitted, the tool "
                "samples common attributes such as P, PartVel, PartAge, "
                "Noise, and PartForce when present."
            ),
        ),
    ] = None,
    prim_attributes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Specific primitive attributes to sample. If omitted, no "
                "primitive attribute samples are returned unless requested."
            ),
        ),
    ] = None,
    vert_attributes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Specific vertex attributes to sample. If omitted, no "
                "vertex attribute samples are returned unless requested."
            ),
        ),
    ] = None,
    start: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Starting element index for attribute sampling",
        ),
    ] = 0,
    count: Annotated[
        int,
        Field(
            default=32,
            ge=1,
            le=2048,
            description="Max elements to sample per requested attribute",
        ),
    ] = 32,
    delayed: Annotated[
        bool,
        Field(
            default=False,
            description=("Use TouchDesigner's delayed GPU readback mode where supported to reduce stalls"),
        ),
    ] = False,
) -> str:
    """Read structured POP metadata and attribute samples."""
    return await _tr._forward(
        ctx,
        "td_pop_inspect",
        "pop/inspect",
        {
            "path": path,
            "include_bounds": include_bounds,
            "include_attributes": include_attributes,
            "point_attributes": point_attributes,
            "prim_attributes": prim_attributes,
            "vert_attributes": vert_attributes,
            "start": start,
            "count": count,
            "delayed": delayed,
        },
    )


@mcp.tool(name="td_cooking_info")
async def td_cooking_info(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/", description="Root path to inspect"),
    ] = "/",
    recurse: Annotated[
        bool,
        Field(default=False, description="Recursively inspect children"),
    ] = False,
    sort_by: Annotated[
        str,
        Field(
            default="cookTime",
            description="Sort by: 'cookTime' or 'cpuCookTime'",
        ),
    ] = "cookTime",
    limit: Annotated[
        int,
        Field(default=20, ge=1, le=100, description="Max nodes to return"),
    ] = 20,
) -> str:
    """Get cooking/performance info for a subtree."""
    return await _tr._forward(
        ctx,
        "td_cooking_info",
        "cooking",
        {
            "path": path,
            "recurse": recurse,
            "sort_by": sort_by,
            "limit": limit,
        },
    )


_DAT_TEXT_SCOPE_CODE_TEMPLATE = """
def _safe(fn, d=None):
    try:
        return fn()
    except Exception:
        return d

query_lower = {query!r}.lower()
limit = {limit}
root_path = {path!r}
root = _safe(lambda: op(root_path))
results = []
truncated = False
if root is not None and _safe(lambda: root.valid, False):
    children = _safe(lambda: list(root.findChildren(maxDepth=999)), [])
    candidates = list(children)
    if root not in candidates:
        candidates.append(root)
    for n in candidates[:5000]:
        try:
            fam = _safe(lambda n=n: n.family)
            if fam != 'DAT':
                continue
            text = _safe(lambda n=n: n.text)
            if not isinstance(text, str):
                continue
            text_l = text.lower()
            if query_lower in text_l:
                idx = text_l.find(query_lower)
                start = max(0, idx - 40)
                end = min(len(text), idx + len(query_lower) + 40)
                snippet = text[start:end].replace('\\n', ' ')
                results.append({{
                    "path": _safe(lambda n=n: n.path),
                    "type": _safe(lambda n=n: n.OPType),
                    "scope": "dat_text",
                    "match_field": "content",
                    "snippet": snippet,
                }})
                if len(results) >= limit:
                    truncated = True
                    break
        except Exception:
            pass
__result__ = {{"results": results, "truncated": truncated}}
"""


_PARAM_EXPRS_SCOPE_CODE_TEMPLATE = """
def _safe(fn, d=None):
    try:
        return fn()
    except Exception:
        return d

query_lower = {query!r}.lower()
limit = {limit}
root_path = {path!r}
root = _safe(lambda: op(root_path))
results = []
truncated = False
if root is not None and _safe(lambda: root.valid, False):
    children = _safe(lambda: list(root.findChildren(maxDepth=999)), [])
    candidates = list(children)
    if root not in candidates:
        candidates.append(root)
    for n in candidates[:5000]:
        try:
            pars = _safe(lambda n=n: list(n.pars()), [])
            for p in pars:
                expr = _safe(lambda p=p: p.expr if p.mode.name == 'EXPRESSION' else None)
                if isinstance(expr, str) and expr and query_lower in expr.lower():
                    results.append({{
                        "path": _safe(lambda n=n: n.path),
                        "type": _safe(lambda n=n: n.OPType),
                        "scope": "param_exprs",
                        "match_field": _safe(lambda p=p: p.name),
                        "snippet": expr[:200],
                    }})
                    if len(results) >= limit:
                        truncated = True
                        break
            if truncated:
                break
        except Exception:
            pass
__result__ = {{"results": results, "truncated": truncated}}
"""


async def _exec_dat_text_scope(ctx: Context, query: str, path: str, limit: int) -> dict[str, Any]:
    code = _DAT_TEXT_SCOPE_CODE_TEMPLATE.format(query=query, limit=limit, path=path)
    body = {"code": code, "exec_mode": _tr._current_exec_mode()}
    data = await _tr._get_client(ctx).request("exec", body)
    if not isinstance(data, dict) or not data.get("success"):
        return {"results": [], "error": (data or {}).get("error", "exec failed")}
    return data.get("result") or {"results": []}


async def _exec_param_exprs_scope(ctx: Context, query: str, path: str, limit: int) -> dict[str, Any]:
    code = _PARAM_EXPRS_SCOPE_CODE_TEMPLATE.format(query=query, limit=limit, path=path)
    body = {"code": code, "exec_mode": _tr._current_exec_mode()}
    data = await _tr._get_client(ctx).request("exec", body)
    if not isinstance(data, dict) or not data.get("success"):
        return {"results": [], "error": (data or {}).get("error", "exec failed")}
    return data.get("result") or {"results": []}


@mcp.tool(name="td_search_nodes")
async def td_search_nodes(
    ctx: Context,
    query: Annotated[
        str,
        Field(description="Search string (case-insensitive)", min_length=1),
    ],
    path: Annotated[
        str,
        Field(default="/", description="Root path to search from"),
    ] = "/",
    search_type: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "DEPRECATED — prefer ``scopes``. One of 'name', 'type', 'family', 'all'. "
                "When both are set, ``scopes`` wins."
            ),
        ),
    ] = None,
    scopes: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Search scopes (v1.6.0+). Any of: 'name', 'type', 'family', 'all', "
                "'dat_text' (search DAT text contents), 'param_exprs' (search "
                "parameter expressions). Multiple scopes merge. Defaults to ['all']."
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=200, description="Max results"),
    ] = 50,
) -> str:
    """Search nodes across a subtree.

    Legacy scopes ('name'/'type'/'family'/'all') hit the existing TD-side
    ``/api/search`` endpoint. New v1.6.0 scopes ('dat_text', 'param_exprs')
    iterate via the ``/api/exec`` endpoint — no ``.tox`` rebuild required.
    """
    finish = _tr._start_tool(ctx, "td_search_nodes")
    try:
        validated = SearchNodesInput(
            query=query,
            path=path,
            search_type=search_type,
            scopes=scopes,
            limit=limit,
        )
        effective = validated.effective_scopes()

        legacy_scopes = [s for s in effective if s in SearchNodesInput.LEGACY_SCOPES]
        new_scopes = [s for s in effective if s in SearchNodesInput.NEW_SCOPES]

        merged_results: list[dict[str, Any]] = []
        scopes_searched: list[str] = []
        scopes_with_errors: dict[str, str] = {}
        truncated_any = False

        # Legacy: forward to the existing TD-side search endpoint.
        # If the caller asked for multiple legacy scopes (eg. ['name', 'type']),
        # collapse to a single forward call with search_type='all' since the
        # TD endpoint only accepts a single type. Then tag results with the
        # actual matched scope (best-effort 'all').
        if legacy_scopes:
            collapsed = "all" if len(legacy_scopes) > 1 else legacy_scopes[0]
            payload = {
                "query": validated.query,
                "path": validated.path,
                "search_type": collapsed,
                "limit": validated.limit,
            }
            try:
                data = await _tr._get_client(ctx).request("search", payload)
                if isinstance(data, dict):
                    rows = data.get("results") or data.get("matches") or []
                    if isinstance(rows, list):
                        for row in rows[: validated.limit]:
                            if not isinstance(row, dict):
                                continue
                            entry = dict(row)
                            entry.setdefault("scope", collapsed)
                            merged_results.append(entry)
                    if data.get("truncated"):
                        truncated_any = True
                scopes_searched.extend(legacy_scopes)
            except Exception as exc:
                for s in legacy_scopes:
                    scopes_with_errors[s] = str(exc)

        # New scopes — host-side dispatch via /api/exec
        scope_handlers = {
            "dat_text": _exec_dat_text_scope,
            "param_exprs": _exec_param_exprs_scope,
        }
        per_scope_remaining = max(1, validated.limit - len(merged_results))
        for s in new_scopes:
            handler = scope_handlers.get(s)
            if handler is None:
                scopes_with_errors[s] = f"scope '{s}' is not supported in this build"
                continue
            try:
                outcome = await handler(ctx, validated.query, validated.path, per_scope_remaining)
                rows = outcome.get("results", []) if isinstance(outcome, dict) else []
                if outcome.get("error"):
                    scopes_with_errors[s] = str(outcome["error"])
                else:
                    scopes_searched.append(s)
                if isinstance(rows, list):
                    merged_results.extend(rows[:per_scope_remaining])
                if outcome.get("truncated"):
                    truncated_any = True
                per_scope_remaining = max(0, validated.limit - len(merged_results))
                if per_scope_remaining == 0:
                    truncated_any = True
                    break
            except Exception as exc:
                scopes_with_errors[s] = str(exc)

        return _tr._as_json_output(
            {
                "results": merged_results[: validated.limit],
                "total": len(merged_results),
                "scopes_searched": scopes_searched,
                "scopes_with_errors": scopes_with_errors,
                "truncated": truncated_any,
            }
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_search_nodes")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_errors")
async def td_get_errors(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/", description="Node path to check"),
    ] = "/",
    recurse: Annotated[
        bool,
        Field(default=True, description="Recursively check children"),
    ] = True,
    max_depth: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Max recursion depth (prevents runaway on huge projects)",
        ),
    ] = 10,
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block via td_get_hints. "
                "Auto-injection still fires when the response contains "
                "known error patterns (eg. 'Not enough sources', "
                "'extension', 'missing input')."
            ),
        ),
    ] = False,
) -> str:
    """Get errors + warnings for a node (optionally recursive)."""
    payload = {"path": path, "recurse": recurse, "max_depth": max_depth}
    raw = await _tr._forward(
        ctx,
        "td_get_errors",
        "node/errors",
        payload,
    )
    return _tr._attach_hints(
        raw,
        tool_name="td_get_errors",
        payload=payload,
        force_query={"topic": "render_pipeline"} if include_hints else None,
    )
