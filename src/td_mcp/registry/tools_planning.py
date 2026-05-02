"""Planning & Validation tools — plan_patch, preflight, validate_recipe, audit_project.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module:
    td_plan_patch       — generate a structured patch plan from intent + recipe
    td_preflight_patch  — validate a plan against live state before apply
    td_validate_recipe  — check recipe for known op types + build compat
    td_audit_project    — count nodes by family/type, find palette COMPs,
                           report build-compat issues

Module-local helpers:
    _legacy_plan_dict(plan, ...)       — translate a typed PatchPlan back
                                          into the pre-v1.5.0 dict shape
                                          so legacy td_plan_patch callers
                                          see no change.
    _STOCK_OP_TYPES: frozenset[str]    — allowlist so stock TD ops (base,
                                          null, noise, etc.) don't get
                                          flagged as "unknown" by audit.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import patch  # noqa: E402
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


def _legacy_plan_dict(
    plan,
    *,
    intent: str,
    target_path: str,
    recipe_id: str | None,
    current_node_count: int = 0,
    existing_names: list[str] | None = None,
) -> dict[str, Any]:
    """Translate a typed PatchPlan into the pre-v1.5.0 dict shape so
    legacy callers of td_plan_patch see no change. `current_node_count`
    and `existing_names` should be freshly probed by the caller to match
    the original td_plan_patch behaviour.

    Note: `plan.required_ops` uses the 'unknown:<op_type>' sentinel
    convention established in patch.planner (Chunk 3). The
    `known_to_knowledge_corpus` derivation here relies on that exact
    string format.
    """
    steps: list[dict[str, Any]] = []
    for op in plan.operations:
        if op.kind == "create_node":
            steps.append(
                {
                    "op": "create_node",
                    "op_type": op.args.get("op_type", ""),
                    "name": op.args.get("name", ""),
                    "parent_path": op.target or target_path,
                    "known_to_knowledge_corpus": not any(
                        r == f"unknown:{op.args.get('op_type', '')}" for r in plan.required_ops
                    ),
                }
            )
        elif op.kind == "macro":
            steps.append(
                {
                    "op": "create_macro",
                    "macro_type": op.args.get("macro_type", ""),
                    "parent_path": op.target or target_path,
                    "summary": op.args.get("summary", ""),
                    "source": "intent_heuristic",
                }
            )

    dict_out: dict[str, Any] = {
        "intent": intent,
        "target_path": target_path,
        "recipe_id": recipe_id,
        "current_node_count": current_node_count,
        "existing_names": existing_names or [],
        "steps": steps,
        "note": ("This plan does NOT mutate the project. Validate with td_preflight_patch before execution."),
    }
    # Macro suggestion surfacing (legacy had this for intent-only plans)
    for step in steps:
        if step.get("op") == "create_macro":
            dict_out["macro_suggestion"] = {
                "macro_type": step["macro_type"],
                "summary": step.get("summary", ""),
            }
            break
    if not steps:
        dict_out["next_actions"] = [
            "Search the technique library: td_memory_recall(query='<keyword>').",
            "List built-in macros: td_list_macros (see td_get_macro_params for options).",
            "If you already have a recipe, pass recipe_id= to td_plan_patch.",
        ]
    return dict_out


@mcp.tool(name="td_plan_patch")
async def td_plan_patch(
    ctx: Context,
    intent: Annotated[
        str,
        Field(description="What you want to achieve", min_length=1),
    ],
    target_path: Annotated[
        str,
        Field(
            default="/project1",
            description="Target path to plan changes for",
        ),
    ] = "/project1",
    recipe_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional recipe ID to base plan on",
        ),
    ] = None,
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block via td_get_hints. "
                "Auto-injection still fires when the plan touches feedback, "
                "GLSL, or audio-reactive territory."
            ),
        ),
    ] = False,
) -> dict[str, Any]:
    """Generate a structured patch plan for an intent without mutating the project.

    Inspects the current state of the target path, validates op types against the
    knowledge corpus, and optionally loads a recipe to generate ordered steps. Returns
    a plan dict that can be validated with td_preflight_patch before execution.

    When no ``recipe_id`` is provided, the tool also performs keyword-based macro
    matching against the intent so callers always get at least one actionable
    suggestion (either a concrete step list or a macro hint).
    """
    finish = _tr._start_tool(ctx, "td_plan_patch")
    try:
        client = _tr._get_client(ctx)
        svc = _tr._get_services(ctx)
        store = _tr._get_technique_store(ctx)
        card_index = getattr(svc, "card_index", None)

        # Probe live state for legacy shape fidelity (Option A)
        current_nodes = []
        try:
            node_data = await client.request("nodes", {"path": target_path, "limit": 200})
            current_nodes = node_data if isinstance(node_data, list) else node_data.get("nodes", [])
        except Exception:
            current_nodes = []
        existing_names = sorted({n.get("name", "") for n in current_nodes if isinstance(n, dict)})

        plan = await patch.build_plan(
            td_client=client,
            target_root=target_path,
            intent=intent,
            recipe_id=recipe_id,
            technique_store=store,
            card_index=card_index,
        )
        legacy_dict = _legacy_plan_dict(
            plan,
            intent=intent,
            target_path=target_path,
            recipe_id=recipe_id,
            current_node_count=len(current_nodes),
            existing_names=existing_names,
        )
        _tr._audit_log(ctx, "td_plan_patch", {"intent": intent, "target_path": target_path})
        result = {"success": True, "plan": legacy_dict}
        return _tr._attach_hints(
            result,
            tool_name="td_plan_patch",
            payload={"intent": intent, "target_path": target_path, "recipe_id": recipe_id},
            force_query={"intent": intent} if include_hints else None,
        )
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_plan_patch")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_preflight_patch")
async def td_preflight_patch(
    ctx: Context,
    plan: Annotated[
        dict[str, Any],
        Field(description="Plan dict from td_plan_patch to validate"),
    ],
) -> dict[str, Any]:
    """Validate a plan from td_plan_patch before execution.

    Checks that the target path exists, all op types in steps have knowledge cards,
    and that there are no name conflicts with existing nodes. Returns a validation
    report with any warnings or errors found.
    """
    # TODO(v1.5.4): delegate to patch.preview_plan once the dict↔PatchPlan
    # adapter lands. Signatures differ (this tool takes the MCP-friendly
    # dict shape; patch.preview_plan takes a typed PatchPlan), so the
    # delegation needs a deserializer + parity tests against this body.
    finish = _tr._start_tool(ctx, "td_preflight_patch")
    try:
        client = _tr._get_client(ctx)
        svc = _tr._get_services(ctx)
        idx = getattr(svc, "card_index", None)

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
        _tr._audit_log(
            ctx,
            "td_preflight_patch",
            {
                "target_path": target_path,
                "steps": len(steps),
                "valid": valid,
            },
        )
        return {
            "success": True,
            "valid": valid,
            "path_exists": path_exists,
            "errors": errors,
            "warnings": warnings,
            "step_count": len(steps),
        }
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_preflight_patch")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_validate_recipe")
async def td_validate_recipe(
    ctx: Context,
    recipe_id: Annotated[
        str | None,
        Field(default=None, description="Recipe ID to validate"),
    ] = None,
    recipe: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Inline recipe dict to validate",
        ),
    ] = None,
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'"),
    ] = "project",
) -> dict[str, Any]:
    """Validate a technique recipe from the library or an inline dict.

    Checks that required op types exist in the knowledge corpus, verifies the recipe
    has the expected structure, and reports build compatibility for current TD version.
    """
    finish = _tr._start_tool(ctx, "td_validate_recipe")
    try:
        svc = _tr._get_services(ctx)
        idx = getattr(svc, "card_index", None)

        # Load recipe from store if recipe_id provided and no inline recipe
        if recipe is None and recipe_id:
            try:
                store = _tr._get_technique_store(ctx)
                recipe = store.get(recipe_id, scope=scope)
                if recipe is None and scope != "global":
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
                    # Apply the same stock-op allowlist td_audit_project uses
                    # so common TD types (base, constant, feedback, null, etc.)
                    # don't surface as "unknown" just because the corpus didn't
                    # index them by type name. N7 audit: the allowlist fix
                    # previously only landed in td_audit_project; extended here.
                    if op_type.lower() not in _STOCK_OP_TYPES:
                        unknown_types.append(op_type)
                else:
                    # Check build compatibility
                    if svc.td_build:
                        try:
                            compat = idx.check_compatibility(op_type, svc.td_build)
                            if compat.get("status") == "incompatible":
                                compat_issues.append(
                                    {
                                        "op_type": op_type,
                                        "reason": compat.get("reason", "unknown"),
                                    }
                                )
                        except Exception:
                            pass

        if unknown_types:
            warnings.append(f"Op types not found in knowledge corpus: {unknown_types}")
        if compat_issues:
            warnings.append(f"Build compatibility issues: {compat_issues}")

        valid = len(errors) == 0
        _tr._audit_log(
            ctx,
            "td_validate_recipe",
            {
                "recipe_id": recipe_id,
                "scope": scope,
                "valid": valid,
            },
        )
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
        _tr._record_tool_error(ctx, "td_validate_recipe")
        return {"error": str(exc)}
    finally:
        finish()


# Stock TouchDesigner op types that should never be flagged as "unknown".
# The knowledge corpus intermittently indexes these by display name rather
# than by ``type`` field (e.g. "Box SOP" not "box"), which caused every stock
# audit to report 8+ common ops as unknown. This allowlist short-circuits
# that check. Sourced from the v1.3.4 td_list_families canonical set plus
# common operator types that appear across POP/SOP/TOP/CHOP/DAT/MAT/COMP.
_STOCK_OP_TYPES: frozenset[str] = frozenset(
    {
        # Universal
        "null",
        "in",
        "out",
        "select",
        "switch",
        "merge",
        # COMPs
        "base",
        "container",
        "geo",
        "window",
        "cam",
        "light",
        "text",
        "time",
        "ambient",
        "animation",
        "annotate",
        "button",
        "environment",
        "field",
        "geotext",
        "graph",
        "list",
        "opviewer",
        "parameter",
        "replicator",
        "slider",
        "table",
        "widget",
        # TOPs
        "constant",
        "noise",
        "ramp",
        "level",
        "blur",
        "composite",
        "displace",
        "feedback",
        "movefilein",
        "moviefilein",
        "moviefileout",
        "render",
        "renderpass",
        "renderselect",
        "rendersimple",
        "transform",
        "over",
        "add",
        "multiply",
        "subtract",
        "layer",
        "chopto",
        "popto",
        "flip",
        "fit",
        "crop",
        "edge",
        "emboss",
        "hsvadj",
        "hsvadjust",
        "hsvtorgb",
        "inside",
        "outside",
        "lookup",
        "rectangle",
        "circle",
        "cacheselect",
        "comp",
        "convolve",
        "cornerpin",
        "cube",
        "cubemap",
        "depth",
        "difference",
        "glslmulti",
        "glsl",
        "lumablur",
        "lumalevel",
        "math",
        "matte",
        "mirror",
        "monochrome",
        "normalmap",
        "pack",
        "panel",
        "point",
        "reorder",
        "resolution",
        "rgbkey",
        "rgbtohsv",
        "screen",
        "screengrab",
        "script",
        "ssao",
        "svg",
        "threshold",
        "tile",
        "tonemap",
        # CHOPs
        "wave",
        "analyze",
        "beat",
        "count",
        "datto",
        "delete",
        "envelope",
        "express",
        "hold",
        "info",
        "joystick",
        "keyframe",
        "lag",
        "limit",
        "logic",
        "midiin",
        "midiinmap",
        "midiout",
        "mousein",
        "object",
        "par",
        "perform",
        "rename",
        "renderpick",
        "replace",
        "resample",
        "shuffle",
        "speed",
        "timeline",
        "timeslice",
        "topto",
        "trail",
        "trigger",
        # SOPs (stock)
        "box",
        "sphere",
        "torus",
        "tube",
        "grid",
        "line",
        "filein",
        "texture",
        "copy",
        "trace",
        "extrude",
        # POPs (v1.3+)
        "attcombine",
        "attconvert",
        "attribute",
        "connectivity",
        "convert",
        "facet",
        "mathcombine",
        "mathmix",
        "normal",
        "normalize",
        "pattern",
        "pointgen",
        "pointgenerator",
        "primitive",
        "rerange",
        "triangulate",
        # MATs
        "phong",
        "pbr",
        "wireframe",
        "pointsprite",
        # DATs
        "execute",
        "chopexec",
        "datexec",
        "parexec",
        "opexec",
        "panelexec",
        "eval",
        "examine",
        "fifo",
        "fileout",
        "indices",
        "insert",
        "keyboardin",
        "opfind",
        "sort",
        "substitute",
        "transpose",
        "web",
        "webclient",
        "webserver",
        "websocket",
    }
)


@mcp.tool(name="td_audit_project")
async def td_audit_project(
    ctx: Context,
    root_path: Annotated[
        str,
        Field(default="/project1", description="Root path to audit"),
    ] = "/project1",
) -> dict[str, Any]:
    """Audit a project subtree: count nodes by family and op type, detect palette
    components, find errors, and check build compatibility.

    Returns a comprehensive audit report without mutating the project.
    """
    finish = _tr._start_tool(ctx, "td_audit_project")
    try:
        client = _tr._get_client(ctx)
        svc = _tr._get_services(ctx)
        idx = getattr(svc, "card_index", None)

        # Recursively fetch all nodes in the subtree (breadth-first)
        all_nodes: list[dict[str, Any]] = []
        max_depth = 10
        try:
            queue: list[tuple] = [(root_path, 0)]
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
            return {"error": f"Could not fetch nodes at '{root_path}': {exc}"}

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

            # Detect palette components.
            # v1.4.6 Bug T fix: previously ANY op whose CardIndex `get_palette`
            # returned truthy got flagged — which misfired for stock ops like
            # noise/transform/null/level because the production CardIndex
            # stores palette-adjacent cards for them too. Stock TD ops are
            # by definition NOT palette components (palette components are
            # installed palette COMPs like POPX, StreamDiffusionTD, etc.).
            # Gate the flagging on `op_type NOT in _STOCK_OP_TYPES` so only
            # non-stock ops with a palette card get listed.
            name = node.get("name", "")
            if idx is not None and op_type and op_type.lower() not in _STOCK_OP_TYPES:
                palette_card = idx.get_palette(op_type)
                if palette_card:
                    palette_components.append({"name": name, "op_type": op_type})

                # Check knowledge corpus. Only flag as unknown when the op type
                # is also not in the stock allowlist — the corpus may not have
                # an explicit card for every stock TD op but they're obviously
                # known to the system, so flagging them produces noise.
                card = idx.get_operator(op_type)
                if (
                    card is None
                    and op_type.lower() not in _STOCK_OP_TYPES
                    and op_type not in unknown_op_types
                ):
                    unknown_op_types.append(op_type)
                elif card is not None and svc.td_build:
                    try:
                        compat = idx.check_compatibility(op_type, svc.td_build)
                        if compat.get("status") == "incompatible":
                            compat_issues.append(
                                {
                                    "node": name,
                                    "op_type": op_type,
                                    "reason": compat.get("reason", "unknown"),
                                }
                            )
                    except Exception:
                        pass

        # Fetch errors for root
        node_errors = []
        try:
            err_data = await client.request(
                "node/errors", {"path": root_path, "recurse": True, "max_depth": 10}
            )
            if isinstance(err_data, list):
                node_errors = err_data
            elif isinstance(err_data, dict):
                node_errors = err_data.get("issues", [])
        except Exception:
            pass

        _tr._audit_log(
            ctx,
            "td_audit_project",
            {
                "root_path": root_path,
                "node_count": len(all_nodes),
            },
        )
        return {
            "success": True,
            "root_path": root_path,
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
        _tr._record_tool_error(ctx, "td_audit_project")
        return {"error": str(exc)}
    finally:
        finish()
