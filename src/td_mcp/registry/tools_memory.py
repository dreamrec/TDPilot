"""Memory tools (td_memory_*) — Technique storage + retrieval.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the package-level explanation of
the circular-import pattern and why this module imports from
``td_mcp.tool_registry``.

Tools in this module:
    td_memory_learn
    td_memory_save
    td_memory_recall
    td_memory_replay
    td_memory_favorite
    td_memory_promote
    td_memory_export
    td_memory_import
    td_memory_preferences
    td_memory_list

All tools were migrated from ``params: InputModel`` to explicit-args
signatures in v1.5.0 Bug A batch 4 (commit 1ece5b9). The ``@mcp.tool``
decorators register each tool on the shared ``mcp`` instance at import
time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional "cycle" import: ``tool_registry.py`` triggers this module at
# the end of its own import (after ``mcp``, helpers, and all other tool
# groups are already bound). Python resolves the partial-module lookup
# successfully because those names are already module globals by then.
# Intentional cycle: tool_registry.py triggers THIS module at the end of
# its own import, after ``mcp`` and all helpers are bound as globals.
# We use MODULE-ATTRIBUTE lookup (``tool_registry._get_client(ctx)``) rather
# than direct name import so that test monkeypatching of
# ``registry._get_client`` continues to work — patches affect the module
# dict, which is what attribute lookup reads at call time.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.memory.analyzer import analyze_network
from td_mcp.models import MemoryPreferencesInput

# The shared ``mcp`` instance (FastMCP). Imported by name because the
# @mcp.tool decorators need it at module-definition time and it never
# gets monkeypatched.
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool()
async def td_memory_learn(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Root path of the network subtree to analyze."),
    ],
    name: Annotated[
        str,
        Field(default="", description="Human-readable name for this technique."),
    ] = "",
    description: Annotated[
        str,
        Field(default="", description="What this technique does."),
    ] = "",
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Tags for categorization."),
    ] = None,
    max_depth: Annotated[
        int,
        Field(default=3, ge=1, le=10, description="Max child depth to walk."),
    ] = 3,
) -> dict:
    """Analyze a network subtree and extract a reusable technique recipe.

    Auto-detects complexity:
    - small (<10 nodes): full recipe with all params and expressions
    - medium (10-20): full recipe
    - large (>20): structure summary + key params only

    Returns the technique dict — pass it to td_memory_save to persist.
    """
    svc = _tr._get_services(ctx)
    client = _tr._get_client(ctx)
    technique = await analyze_network(
        client,
        path,
        max_depth=max_depth,
        name=name,
        description=description,
        tags=tags or [],
        td_build=svc.td_build,
    )
    return {"status": "ok", "technique": technique}


@mcp.tool()
async def td_memory_save(
    ctx: Context,
    technique: Annotated[
        dict,
        Field(description="Technique dict (from td_memory_learn output)."),
    ],
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
    name: Annotated[
        str,
        Field(default="", description="Override technique name."),
    ] = "",
    description: Annotated[
        str,
        Field(default="", description="Override description."),
    ] = "",
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Additional tags."),
    ] = None,
    notes: Annotated[
        str,
        Field(default="", description="Freeform notes about this technique."),
    ] = "",
) -> dict:
    """Save a technique to the project or global library.

    Use the output of td_memory_learn as the technique input,
    or construct a technique dict manually.
    """
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    # Build compatibility dict from technique metadata if present
    tech = technique
    td_build = tech.get("td_build", "") if isinstance(tech, dict) else ""
    required_op_types = tech.get("required_op_types", []) if isinstance(tech, dict) else []
    compatibility: dict = {}
    if td_build:
        compatibility["min_build"] = td_build
    if required_op_types:
        compatibility["required_ops"] = required_op_types
    # Fall back to values from the technique dict if caller didn't provide them
    resolved_name = name or (tech.get("name", "") if isinstance(tech, dict) else "")
    resolved_description = description or (tech.get("description", "") if isinstance(tech, dict) else "")
    resolved_tags = (tags or []) or (tech.get("tags", []) if isinstance(tech, dict) else [])
    technique_id = store.add(
        technique=technique,
        scope=scope,
        name=resolved_name,
        description=resolved_description,
        tags=resolved_tags,
        notes=notes,
        compatibility=compatibility or None,
    )
    return {"status": "ok", "technique_id": technique_id, "scope": scope}


@mcp.tool()
async def td_memory_recall(
    ctx: Context,
    query: Annotated[
        str,
        Field(
            default="",
            description="Text search across names, descriptions, tags.",
        ),
    ] = "",
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Filter by tags."),
    ] = None,
    scope: Annotated[
        str,
        Field(default="all", description="'project', 'global', or 'all'."),
    ] = "all",
    limit: Annotated[
        int,
        Field(default=20, ge=1, le=100, description="Max results."),
    ] = 20,
) -> dict:
    """Search the technique library by text query and/or tags.

    Returns summaries (not full recipes). Use td_memory_replay to rebuild a found technique.
    """
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    results = store.search(
        query=query,
        tags=tags if tags else None,
        scope=scope,
        limit=limit,
    )
    return {"status": "ok", "count": len(results), "techniques": results}


@mcp.tool()
async def td_memory_replay(
    ctx: Context,
    technique_id: Annotated[
        str,
        Field(description="ID of the saved technique to replay."),
    ],
    parent_path: Annotated[
        str,
        Field(
            description="Parent COMP path where the technique will be rebuilt.",
        ),
    ],
    name_prefix: Annotated[
        str,
        Field(
            default="",
            description="Optional prefix for created node names.",
        ),
    ] = "",
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
    force: Annotated[
        bool,
        Field(
            default=False,
            description="Skip build compatibility checks and replay anyway.",
        ),
    ] = False,
    recreate_root: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "v1.4.7 Bug V opt-in. If True and the recipe's '/' entry "
                "has family='COMP', the replay creates that wrapper COMP "
                "under parent_path first and builds all children inside "
                "it. Default False preserves the existing flat-replay "
                "behavior where '/' is aliased to parent_path (children "
                "land as siblings). Set to True when you want a faithful "
                "clone of a COMP-wrapped technique."
            ),
        ),
    ] = False,
) -> dict:
    """Rebuild a saved technique in a new location in the TD project.

    Creates nodes, sets parameters and expressions, wires connections.
    Only works for techniques with a full recipe (small/medium complexity).
    """
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    entry = store.get(technique_id, scope=scope)
    if not entry:
        return {
            "status": "error",
            "message": f"Technique {technique_id} not found in {scope} scope.",
        }

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
    if not force:
        required_ops: list[str] = (
            technique.get("required_op_types") or entry.get("compatibility", {}).get("required_ops") or []
        )
        if required_ops:
            client = _tr._get_client(ctx)
            try:
                families_resp = await client.request("families", {})
                available_types: set = set()
                # v1.5.1: TD's /api/families returns
                # {"families": {"TOP": [...], "CHOP": [...], ...}}.
                # Pre-v1.5.1 this loop iterated families_resp.values() which
                # gave the inner dict (not a list), so the isinstance check
                # always failed and available_types stayed empty — silently
                # disabling the prereq guard. Unwrap the "families" key first
                # but accept the legacy flat shape too in case TD ever changes.
                families_data = families_resp.get("families") if isinstance(families_resp, dict) else None
                if not isinstance(families_data, dict):
                    families_data = families_resp if isinstance(families_resp, dict) else {}
                if isinstance(families_data, dict):
                    for fam_types in families_data.values():
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

    client = _tr._get_client(ctx)
    parent = parent_path.rstrip("/") or "/"
    prefix = name_prefix.strip()

    recipe_nodes = recipe.get("nodes", {})
    if not isinstance(recipe_nodes, dict) or not recipe_nodes:
        return {"status": "error", "message": "Technique recipe has no nodes to replay."}

    created_nodes: dict[str, str] = {"/": parent}
    skipped_nodes: list[dict[str, str]] = []
    created_count = 0

    # v1.4.7 Bug V (V.C): opt-in root-COMP recreation.
    # When `recreate_root=True` AND the recipe's '/' entry is a COMP,
    # create that wrapper COMP under `parent_path` FIRST and remap
    # created_nodes['/'] to the new path. Children then get created
    # INSIDE the new root instead of directly under `parent_path`,
    # producing a faithful clone of the original COMP hierarchy.
    # Default False preserves existing flat-replay semantics.
    if recreate_root:
        root_info = recipe_nodes.get("/")
        if isinstance(root_info, dict):
            root_family = str(root_info.get("family", "")).strip().upper()
            if root_family == "COMP":
                raw_root_type = str(root_info.get("type", "")).strip()
                root_candidates: list[str] = []
                upper_root_type = raw_root_type.upper()
                _suffix_by_family = {
                    "TOP": "TOP",
                    "CHOP": "CHOP",
                    "SOP": "SOP",
                    "DAT": "DAT",
                    "COMP": "COMP",
                    "MAT": "MAT",
                    "POP": "POP",
                    "POPX": "POPX",
                }
                if any(upper_root_type.endswith(s) for s in _suffix_by_family.values()):
                    root_candidates.append(raw_root_type)
                else:
                    root_candidates.append(f"{raw_root_type}COMP")
                    root_candidates.append(raw_root_type)
                root_candidates = list(dict.fromkeys(root_candidates))
                base_name = str(root_info.get("name", "")).strip() or "wrapper"
                root_node_name = f"{prefix}_{base_name}" if prefix else base_name
                root_result: dict[str, Any] | None = None
                for candidate in root_candidates:
                    try:
                        r = await client.request(
                            "node/create",
                            {
                                "parent_path": parent,
                                "node_type": candidate,
                                "name": root_node_name,
                            },
                        )
                        if isinstance(r, dict):
                            root_result = r
                            break
                    except Exception:
                        continue
                if root_result is not None:
                    root_node_obj = root_result.get("node", {}) if isinstance(root_result, dict) else {}
                    root_actual = root_node_obj.get("path") if isinstance(root_node_obj, dict) else None
                    if not isinstance(root_actual, str) or not root_actual:
                        fb = root_result.get("path") if isinstance(root_result, dict) else None
                        root_actual = (
                            fb
                            if isinstance(fb, str) and fb
                            else f"{parent.rstrip('/')}/{root_node_name}".replace("//", "/")
                        )
                    # Remap '/' so children land INSIDE the recreated COMP.
                    created_nodes["/"] = root_actual
                    created_count += 1
                    # Apply root COMP's params if present (custom pars / settings).
                    root_params_to_set = root_info.get("params", {})
                    if isinstance(root_params_to_set, dict):
                        clean_root_params = {k: v for k, v in root_params_to_set.items() if v is not None}
                        if clean_root_params:
                            await client.request(
                                "node/params/set",
                                {"path": root_actual, "params": clean_root_params},
                            )
                else:
                    skipped_nodes.append({"path": "/", "reason": "recreate_root_create_failed"})

    # Build shallow-to-deep so nested paths can resolve their parent container.
    create_order = sorted(
        (
            rel_path
            for rel_path in recipe_nodes.keys()
            if isinstance(rel_path, str) and rel_path and rel_path != "/"
        ),
        key=lambda rel_path: rel_path.count("/"),
    )

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
                key: {"expr": value} for key, value in expressions.items() if isinstance(value, str) and value
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

    # v1.4.7 Bug V (V.C): when recreate_root actually ran (created_nodes['/']
    # was remapped from `parent` to a newly-created COMP path), surface the
    # new root path so callers can discover where the wrapper landed.
    # Otherwise keep the old behavior where '/' is redundant (just = parent).
    created_paths = {key: value for key, value in created_nodes.items() if key != "/"}
    if created_nodes.get("/") and created_nodes["/"] != parent:
        created_paths["/"] = created_nodes["/"]

    # Auto-validate after replay
    validation_result = None
    try:
        error_result = await client.request("node/errors", {"path": parent, "recurse": True, "max_depth": 10})
        errors = error_result.get("issues", []) if isinstance(error_result, dict) else []
        validation_status = "pass" if not errors else "fail"
        validation_result = {
            "status": validation_status,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "td_build": _tr._get_services(ctx).td_build,
            "errors": [str(e) for e in errors[:10]],
            "warnings": [],
        }
        # Persist validation and auto-promote candidate -> validated_local on
        # pass. Use update_validation() (not update()) — update() enforces
        # state-transition discipline by silently dropping `state` keys, so
        # routing state changes through update_validation() is the canonical
        # path. It also handles the demotion case (fail → drop back one rung).
        store.update_validation(technique_id, validation_result, scope=scope)
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
    store.record_replay(technique_id, scope=scope)

    return response


@mcp.tool()
async def td_memory_favorite(
    ctx: Context,
    technique_id: Annotated[
        str,
        Field(description="ID of the technique."),
    ],
    favorite: Annotated[
        bool,
        Field(default=True, description="Set favorite status."),
    ] = True,
    rating: Annotated[
        int,
        Field(default=-1, ge=-1, le=5, description="Rating 0-5, or -1 to skip."),
    ] = -1,
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
) -> dict:
    """Mark a technique as favorite and/or rate it (0-5)."""
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    ok = store.set_favorite(technique_id, favorite, scope=scope)
    if not ok:
        return {"status": "error", "message": f"Technique {technique_id} not found."}
    if rating >= 0:
        store.set_rating(technique_id, rating, scope=scope)
    return {
        "status": "ok",
        "technique_id": technique_id,
        "favorite": favorite,
        "rating": rating,
    }


@mcp.tool()
async def td_memory_promote(
    ctx: Context,
    technique_id: Annotated[
        str,
        Field(description="Project technique ID to promote."),
    ],
) -> dict:
    """Copy a project technique to the global library so it's available across all projects."""
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    new_id = store.promote(technique_id)
    if not new_id:
        return {
            "status": "error",
            "message": f"Technique {technique_id} not found in project scope.",
        }
    return {
        "status": "ok",
        "global_technique_id": new_id,
        "promoted_from": technique_id,
    }


@mcp.tool()
async def td_memory_export(
    ctx: Context,
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
) -> dict:
    """Export the technique library as a portable JSON object for sharing or backup."""
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    return {"status": "ok", "library": store.export_library(scope=scope)}


@mcp.tool()
async def td_memory_import(
    ctx: Context,
    data: Annotated[
        dict[str, Any],
        Field(
            description="Exported library data (from td_memory_export).",
        ),
    ],
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
    overwrite: Annotated[
        bool,
        Field(
            default=False,
            description="Overwrite existing techniques with same ID.",
        ),
    ] = False,
) -> dict:
    """Import techniques from an exported library (from td_memory_export)."""
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    result = store.import_library(data, scope=scope, overwrite=overwrite)
    return {"status": "ok", **result}


@mcp.tool()
async def td_memory_preferences(
    ctx: Context,
    action: Annotated[
        str,
        Field(description="One of: 'get', 'set', 'list', 'delete'."),
    ],
    key: Annotated[
        str,
        Field(
            default="",
            description="Preference key (required for get/set/delete).",
        ),
    ] = "",
    value: Annotated[
        Any,
        Field(default=None, description="Value to set (required for 'set')."),
    ] = None,
    scope: Annotated[
        str,
        Field(default="project", description="'project' or 'global'."),
    ] = "project",
) -> dict:
    """Get, set, list, or delete user preferences.

    Preferences store things like: preferred color palettes, default resolutions,
    favorite operator types, naming conventions, etc.
    """
    # Re-instantiate so the MemoryPreferencesInput custom @field_validator on
    # ``action`` (allowed-set: get/set/list/delete) still runs.
    MemoryPreferencesInput(action=action, key=key, value=value, scope=scope)

    await _tr._ensure_project_scope(ctx)
    pref = _tr._get_preference_store(ctx)
    action_normalized = action.lower()

    if action_normalized == "get":
        if not key:
            return {"status": "error", "message": "Key is required for 'get'."}
        got_value = pref.get(key, scope=scope)
        return {"status": "ok", "key": key, "value": got_value}

    elif action_normalized == "set":
        if not key:
            return {"status": "error", "message": "Key is required for 'set'."}
        pref.set(key, value, scope=scope)
        return {"status": "ok", "key": key, "value": value}

    elif action_normalized == "list":
        all_prefs = pref.list_all(scope=scope)
        return {"status": "ok", "preferences": all_prefs, "count": len(all_prefs)}

    elif action_normalized == "delete":
        if not key:
            return {"status": "error", "message": "Key is required for 'delete'."}
        deleted = pref.delete(key, scope=scope)
        return {"status": "ok", "deleted": deleted, "key": key}

    else:
        return {
            "status": "error",
            "message": f"Unknown action '{action_normalized}'. Use get/set/list/delete.",
        }


@mcp.tool()
async def td_memory_list(
    ctx: Context,
    scope: Annotated[
        str,
        Field(default="all", description="'project', 'global', or 'all'."),
    ] = "all",
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Filter by tags."),
    ] = None,
    favorites_only: Annotated[
        bool,
        Field(default=False, description="Only return favorites."),
    ] = False,
    limit: Annotated[
        int,
        Field(default=50, ge=1, le=200, description="Max results."),
    ] = 50,
) -> dict:
    """List saved techniques with optional filtering by scope, tags, and favorites."""
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_technique_store(ctx)
    results = store.list_techniques(
        scope=scope,
        tags=tags if tags else None,
        favorites_only=favorites_only,
        limit=limit,
    )
    return {"status": "ok", "count": len(results), "techniques": results}
