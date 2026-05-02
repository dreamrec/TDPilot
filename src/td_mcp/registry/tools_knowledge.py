"""Knowledge tools — TD docs, palette, snippets, POPx brain.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the package-level explanation of
the intentional-cycle import pattern.

Tools in this module:
    td_search_official_docs
    td_get_operator_doc
    td_get_param_help
    td_lookup_snippets
    td_lookup_palette_component
    td_get_release_delta
    td_get_build_compatibility
    td_describe_surface
    td_search_popx_docs
    td_get_popx_operator

Knowledge-specific helpers also live here:
    _tr._get_card_index(ctx)           — per-ctx CardIndex accessor
    _get_popx_brain(ctx)           — per-ctx POPx Brain accessor
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

# See ``src/td_mcp/registry/__init__.py`` for why this circular-looking
# import works. ``_tr.X(...)`` calls via module-attribute lookup so test
# monkeypatching of ``registry._get_X`` continues to work.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.capabilities import detect_capabilities
from td_mcp.knowledge.freshness import Provenance
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_search_official_docs")
async def td_search_official_docs(
    ctx: Context,
    query: str,
    card_types: list[str] | None = None,
    family: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search the knowledge corpus for operators, palette components, releases, or snippets."""
    idx = _tr._get_card_index(ctx)
    results = idx.search(query, card_types=card_types, family=family, limit=limit)
    svc = _tr._get_services(ctx)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_operator_doc")
async def td_get_operator_doc(
    ctx: Context,
    op_type: str | None = None,
    node_path: str | None = None,
) -> dict[str, Any]:
    """Get full documentation card for an operator type or a specific node."""
    idx = _tr._get_card_index(ctx)
    resolved_type = op_type
    resolved_family = ""  # only populated when we went via node_path
    if resolved_type is None and node_path:
        # Resolve op_type from live node
        try:
            info = await _tr._get_client(ctx).request("node/detail", {"path": node_path})
            resolved_type = info.get("type", "")
            resolved_family = info.get("family", "")
        except Exception:
            return {"error": f"Could not resolve node at {node_path}"}
    if not resolved_type:
        return {"error": "Provide op_type or node_path"}
    # v1.4.6 short-form fallback (mirrors the fix in td_get_param_help).
    # TD's `node/detail` returns short op_types like "glsl", "render" while
    # DocsBrain keys by canonical type+family ("glslTOP", "renderTOP").
    # When the short-form lookup misses, retry with each known family
    # suffix so users typing `td_get_operator_doc("glsl")` get a real card.
    card = idx.get_operator(resolved_type)
    if card is None:
        if resolved_family:
            card = idx.get_operator(resolved_type + resolved_family.upper())
        else:
            # Pure op_type path — try each family suffix in frequency order.
            for fam in ("TOP", "COMP", "CHOP", "SOP", "MAT", "DAT", "POPX", "POP"):
                candidate = idx.get_operator(resolved_type + fam)
                if candidate is not None:
                    card = candidate
                    break
    svc = _tr._get_services(ctx)
    if card is None:
        provenance = Provenance(source="local_card", td_build=svc.td_build)
        return {"error": f"No card found for {resolved_type}", "provenance": provenance.to_dict()}
    provenance = Provenance(
        source="local_card", td_build=svc.td_build, last_verified=card.get("last_verified", "")
    )
    return {"card": card, "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_param_help")
async def td_get_param_help(
    ctx: Context,
    node_path: str,
    param_name: str,
) -> dict[str, Any]:
    """Get help for a specific parameter: live metadata + knowledge card entry + current value."""
    client = _tr._get_client(ctx)
    # Live param lookup — v1.4.6 case-insensitive fallback.
    # TD's built-in parameter names are canonical lowercase; `node/params`
    # filters by exact name. Accepting mixed-case queries like
    # "outputResolution" and retrying with the lowercase form keeps callers
    # from getting a silent `live: null` on a simple casing slip.
    tried_names: list[str] = [param_name]
    lowered = param_name.lower()
    if lowered != param_name:
        tried_names.append(lowered)
    live_param = None
    for name in tried_names:
        try:
            params = await client.request("node/params", {"path": node_path, "names": [name]})
        except Exception as exc:
            return {"error": f"Could not read param: {exc}"}
        candidate = params.get("parameters", {}).get(name)
        if candidate is None:
            candidate = params.get("params", {}).get(name)
        if candidate is not None:
            live_param = candidate
            break
    # Try to get operator card for enrichment
    idx = _tr._get_card_index(ctx)
    card_param = None
    card_source = None
    try:
        info = await client.request("node/detail", {"path": node_path})
        op_type = info.get("type", "")
        family = info.get("family", "")
        # v1.4.6 op_type fallback: TD's `node/detail` returns the short
        # op_type (e.g. `"noise"`) and family (`"TOP"`) separately, while
        # DocsBrain keys operators by the canonical `type+family` form
        # (`"noiseTOP"`). Try the short form first (back-compat for stores
        # that DO key by it, like the legacy JSON CardIndex for some entries),
        # then fall back to the canonical form so DocsBrain resolves.
        card = idx.get_operator(op_type)
        if card is None and op_type and family:
            card = idx.get_operator(op_type + family.upper())
        if card:
            # v1.4.5 Fix 3: accept both CardIndex JSON cards (key_params)
            # and DocsBrain cards (key_params added via normalization), with
            # case-insensitive matching so "outputResolution" and
            # "outputresolution" resolve to the same entry.
            param_name_lc = param_name.lower()
            candidates = card.get("key_params") or []
            # Fallback: if a card somehow has only `parameters` (list of
            # strings), synthesize a minimal key_params list so the match
            # can still fire. Defensive.
            if not candidates and card.get("parameters"):
                candidates = [
                    {"name": p, "source": "parameters-fallback"} if isinstance(p, str) else p
                    for p in card["parameters"]
                ]
            for kp in candidates:
                if not isinstance(kp, dict):
                    continue
                if str(kp.get("name", "")).lower() == param_name_lc:
                    card_param = kp
                    card_source = kp.get("source", "local_card")
                    break
    except Exception:
        pass
    svc = _tr._get_services(ctx)
    # Provenance reflects where the card data actually came from so callers
    # can tell CardIndex JSON cards apart from DocsBrain-normalized ones.
    provenance = Provenance(source=card_source or "local_card", td_build=svc.td_build)
    return {"live": live_param, "card_param": card_param, "provenance": provenance.to_dict()}


@mcp.tool(name="td_lookup_snippets")
async def td_lookup_snippets(
    ctx: Context,
    query: str,
    family: str | None = None,
) -> dict[str, Any]:
    """Search for OP Snippets by keyword and optional family."""
    idx = _tr._get_card_index(ctx)
    results = idx.search(query, card_types=["snippets"], family=family)
    svc = _tr._get_services(ctx)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {"results": results, "count": len(results), "provenance": provenance.to_dict()}


@mcp.tool(name="td_lookup_palette_component")
async def td_lookup_palette_component(
    ctx: Context,
    component_name: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Look up a palette component by name or search by query."""
    idx = _tr._get_card_index(ctx)
    svc = _tr._get_services(ctx)
    if component_name:
        card = idx.get_palette(component_name)
        if card:
            provenance = Provenance(
                source="local_card", td_build=svc.td_build, last_verified=card.get("last_verified", "")
            )
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
    idx = _tr._get_card_index(ctx)
    svc = _tr._get_services(ctx)
    target_build = build or svc.td_build or (await _tr._ensure_td_build(ctx))
    if not target_build:
        return {"error": "No build specified and current build unknown"}
    card = idx.get_release(target_build)
    if card is None:
        provenance = Provenance(source="local_card", td_build=svc.td_build)
        return {"error": f"No release card for build {target_build}", "provenance": provenance.to_dict()}
    provenance = Provenance(
        source="local_card", td_build=svc.td_build, last_verified=card.get("last_verified", "")
    )
    return {"card": card, "provenance": provenance.to_dict()}


@mcp.tool(name="td_get_build_compatibility")
async def td_get_build_compatibility(
    ctx: Context,
    op_type: str,
    build: str | None = None,
) -> dict[str, Any]:
    """Check if an operator type is compatible with a specific build."""
    idx = _tr._get_card_index(ctx)
    svc = _tr._get_services(ctx)
    target_build = build or svc.td_build or (await _tr._ensure_td_build(ctx))
    if not target_build:
        return {"error": "No build specified and current build unknown"}
    result = idx.check_compatibility(op_type, target_build)
    provenance = Provenance(source="local_card", td_build=svc.td_build)
    return {**result, "provenance": provenance.to_dict()}


# ── POPx Brain Tools ─────────────────────────────────────────────────


def _get_popx_brain(ctx: Context):
    svc = _tr._get_services(ctx)
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
        return {
            "error": "POPx brain not installed. Run `npx tdpilot brains add popx` (terminal) "
            "to enable, then restart the MCP client. Alternatively use the "
            "local docs at <repo>/skills/popx-touchdesigner/references/ which "
            "ship with the plugin and don't depend on the brain.",
            "results": [],
            "count": 0,
        }
    results = brain.search(query, limit=limit)
    svc = _tr._get_services(ctx)
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
        return {
            "error": "POPx brain not installed. Run `npx tdpilot brains add popx` (terminal) "
            "to enable, then restart the MCP client. Alternatively use the "
            "local docs at <repo>/skills/popx-touchdesigner/references/ which "
            "ship with the plugin and don't depend on the brain."
        }
    results = brain.search(operator_name, limit=5)
    op_results = [r for r in results if r.get("operator_name", "").lower() == operator_name.lower()]
    if not op_results:
        op_results = results
    svc = _tr._get_services(ctx)
    provenance = Provenance(source="popx_brain", td_build=svc.td_build)
    if op_results:
        return {"operator": op_results[0], "related": op_results[1:], "provenance": provenance.to_dict()}
    return {"error": f"No POPx operator found for '{operator_name}'", "provenance": provenance.to_dict()}


@mcp.tool(name="td_describe_surface")
async def td_describe_surface(ctx: Context) -> dict[str, Any]:
    """Describe the MCP server surface: tool count, resource count, capabilities, version."""
    from td_mcp import __version__

    svc = _tr._get_services(ctx)
    # Lazily populate td_build so capabilities.td_build isn't empty when the
    # MCP server started before TD was reachable (N2 audit).
    td_build = svc.td_build or (await _tr._ensure_td_build(ctx))
    caps = detect_capabilities(ctx, td_build=td_build)
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
