"""Network analyzer — extracts technique recipes from live TouchDesigner projects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from td_mcp.td_client import TDClient

# Complexity thresholds
SMALL_MAX = 10
MEDIUM_MAX = 20

_PAGE_SIZE = 200

# File extensions that indicate external assets referenced in param values
_ASSET_EXTENSIONS = (
    ".toe",
    ".tox",
    ".txt",
    ".csv",
    ".json",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".tga",
    ".exr",
    ".hdr",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".wav",
    ".mp3",
    ".aiff",
    ".ogg",
    ".flac",
    ".obj",
    ".fbx",
    ".glb",
    ".gltf",
    ".abc",
    ".glsl",
    ".vert",
    ".frag",
)


async def analyze_network(
    client: TDClient,
    path: str,
    *,
    max_depth: int = 3,
    max_nodes: int = 200,
    name: str = "",
    description: str = "",
    tags: list[str] | None = None,
    td_build: str = "",
) -> dict[str, Any]:
    """Analyze a TD network subtree and return a technique recipe dict.

    Auto-detects complexity:
      - small (<10 nodes): full recipe with all params/expressions
      - medium (10-20 nodes): full recipe
      - large (>20 nodes): key params + structure summary, recipe=null

    Paths in the recipe are converted to relative for portability.
    """
    nodes, connections = await _collect_subtree(client, path, max_depth=max_depth, max_nodes=max_nodes)

    node_count = len(nodes)
    if node_count <= SMALL_MAX:
        complexity = "small"
    elif node_count <= MEDIUM_MAX:
        complexity = "medium"
    else:
        complexity = "large"

    # Build recipe (full for small/medium, summary-only for large)
    if complexity in ("small", "medium"):
        recipe = _build_full_recipe(nodes, connections, path)
    else:
        recipe = None

    # Build structure summary (always included)
    families: dict[str, int] = {}
    op_types: dict[str, int] = {}
    for node in nodes.values():
        fam = node.get("family", "unknown")
        families[fam] = families.get(fam, 0) + 1
        op_type = node.get("type", "unknown")
        op_types[op_type] = op_types.get(op_type, 0) + 1

    # Key params for large networks
    key_params: list[dict[str, Any]] | None = None
    if complexity == "large":
        key_params = _extract_key_params(nodes, path)

    return {
        "source_path": path,
        "node_count": node_count,
        "connection_count": len(connections),
        "complexity": complexity,
        "families": families,
        "op_types": op_types,
        "required_op_types": sorted(op_types.keys()),
        "recipe": recipe,
        "key_params": key_params,
        "name": name,
        "description": description,
        "tags": sorted(set(tags or [])),
        "td_build": td_build,
    }


async def _collect_subtree(
    client: TDClient,
    root_path: str,
    *,
    max_depth: int = 3,
    max_nodes: int = 200,
) -> tuple:
    """Walk a TD network subtree and collect nodes + connections.

    Returns (nodes_dict, connections_list).

    v1.4.7 Bug S (S.E) auto-detect walk mode from the ROOT node's type:

    - COMP root -> classic tree walk: descend through `isCOMP` children
      via the `nodes` endpoint. Captures the full hierarchy under the
      wrapper, bounded by `max_depth` and `max_nodes`.
    - Non-COMP root (TOP/CHOP/SOP/etc.) -> bidirectional wire-graph walk:
      follow `inputs` upstream AND `outputs` downstream via the wire
      connections TD exposes on `node/detail`. Bounded by `max_depth`
      hops and `max_nodes` total. Lets users save a connected chain of
      ops as a technique without pre-wrapping in a COMP.

    The mode is decided once on the FIRST node (the root) and fixed for
    the whole walk. That keeps COMP tree walks from accidentally leaking
    out via wire connections, and keeps wire walks from fanning out
    through deeply-nested COMPs they happen to touch.
    """
    nodes: dict[str, dict[str, Any]] = {}
    connections: list[dict[str, Any]] = []
    visited: set[str] = set()

    queue: list[tuple] = [(root_path, 0)]
    # None until the root is processed; then True (tree mode) or False (wire mode).
    root_is_comp: bool | None = None

    while queue and len(visited) < max_nodes:
        current, depth = queue.pop(0)
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
            "nodeX": detail.get("nodeX"),
            "nodeY": detail.get("nodeY"),
            "color": detail.get("color"),
            "comment": detail.get("comment"),
        }

        # Lock walk mode on the first successfully-fetched node (the root).
        if root_is_comp is None:
            root_is_comp = bool(detail.get("isCOMP"))

        # Collect connections from input list (used by both walk modes).
        for conn in detail.get("inputs", []):
            if not isinstance(conn, dict):
                continue
            source = conn.get("from")
            if isinstance(source, str) and source:
                connections.append(
                    {
                        "from": source,
                        "to": node_path,
                        "from_index": int(conn.get("from_index", 0) or 0),
                        "to_index": int(conn.get("to_index", 0) or 0),
                    }
                )

        if root_is_comp:
            # Tree mode: walk children through nested COMPs.
            if detail.get("isCOMP") and depth < max_depth:
                child_offset = 0
                while len(visited) < max_nodes:
                    children = await client.request(
                        "nodes",
                        {
                            "path": node_path,
                            "limit": _PAGE_SIZE,
                            "offset": child_offset,
                            "include_params": False,
                        },
                    )
                    child_list = children.get("nodes", [])
                    if not child_list:
                        break
                    for child in child_list:
                        child_path = child.get("path", "")
                        if child_path and child_path not in visited:
                            queue.append((child_path, depth + 1))
                    if len(child_list) < _PAGE_SIZE:
                        break
                    child_offset += _PAGE_SIZE
        else:
            # Wire mode: queue upstream (`inputs`) and downstream
            # (`outputs`) neighbors. `max_depth` counts wire hops from
            # the root; same cap semantics as tree mode.
            if depth < max_depth:
                for conn in detail.get("inputs", []):
                    if not isinstance(conn, dict):
                        continue
                    src = conn.get("from")
                    if isinstance(src, str) and src and src not in visited:
                        queue.append((src, depth + 1))
                for conn in detail.get("outputs", []):
                    if not isinstance(conn, dict):
                        continue
                    # Outputs may use `to`, `path`, or `target` depending on
                    # the TD-side response shape — defensively accept all.
                    dst = conn.get("to") or conn.get("path") or conn.get("target")
                    if isinstance(dst, str) and dst and dst not in visited:
                        queue.append((dst, depth + 1))

    return nodes, connections


def _build_full_recipe(
    nodes: dict[str, dict[str, Any]],
    connections: list[dict[str, Any]],
    root_path: str,
) -> dict[str, Any]:
    """Build a portable recipe dict with relative paths.

    v1.4.7 Bug S follow-up: wire-walked recipes (from non-COMP roots)
    capture nodes that live outside the root's hierarchy — typically
    siblings under a shared parent. Before the follow-up, those siblings
    kept their absolute paths in the recipe (e.g. ``/stage/mid``),
    which made replay to a new parent fail with ``missing_parent``
    because the recipe assumed the absolute TD layout would be preserved.

    Fix: for each captured node, derive a rel_path that's portable:

    - Root itself                        -> ``"/"``
    - Descendants of root (tree walk)    -> ``"/relative/subpath"``
    - Non-descendants (wire-walked)      -> ``"/<leaf_name>"``, with a
      numeric suffix on leaf-name collisions so distinct abs_paths never
      share a rel_path.

    The resulting recipe is a flat namespace under ``/``, which replay
    handles natively: every non-root rel_path's parent lookup resolves
    to ``created_nodes["/"]`` (the replay's effective parent), so each
    wire-walked sibling lands under ``parent_path`` correctly.

    A single ``_rel()`` closure caches the abs->rel mapping so connection
    endpoints use the exact same rel_paths as the node keys; that keeps
    replay's ``{from,to} in nodes`` filter in agreement with the
    rel_path it needs to look up.
    """
    prefix = root_path.rstrip("/")
    path_to_rel: dict[str, str] = {}
    used_rels: set[str] = set()

    # Walk mode is derivable from the root's family:
    #   COMP root  -> tree walk: recipe has `/` for the wrapper, `/path`
    #                 for descendants. Replay aliases `/` to parent_path
    #                 (children fill the wrapper; wrapper itself is
    #                 implicit unless recreate_root=True — see V.C).
    #   Non-COMP   -> wire walk: EVERY captured node is a peer of the
    #                 others. Recipe has NO `/` entry — all nodes get
    #                 leaf-name rel_paths (`/head`, `/mid`, ...) and
    #                 replay creates them as siblings under parent_path.
    #                 This is what makes wire-walked recipes portable.
    root_node = nodes.get(root_path)
    root_is_comp = isinstance(root_node, dict) and root_node.get("family") == "COMP"

    def _rel(p: str) -> str:
        # Cache first so every call for the same abs_path returns the
        # same rel_path — crucial for keeping connection endpoints in
        # sync with the node keys in the recipe.
        if p in path_to_rel:
            return path_to_rel[p]

        if root_is_comp:
            if p == prefix:
                rel = "/"
            elif p.startswith(prefix + "/"):
                rel = p[len(prefix) :]
            else:
                # Shouldn't normally happen in tree mode, but handle
                # defensively with the same leaf-name strategy.
                name = p.rsplit("/", 1)[-1] or "unnamed"
                candidate = "/" + name
                counter = 1
                while candidate in used_rels:
                    counter += 1
                    candidate = f"/{name}_{counter}"
                rel = candidate
        else:
            # Wire walk: leaf-name rel_path for every node — including
            # the root. No `/` entry in the recipe's node map; all
            # nodes are peers on replay.
            name = p.rsplit("/", 1)[-1] or "unnamed"
            candidate = "/" + name
            counter = 1
            while candidate in used_rels:
                counter += 1
                candidate = f"/{name}_{counter}"
            rel = candidate

        used_rels.add(rel)
        path_to_rel[p] = rel
        return rel

    recipe_nodes: dict[str, dict[str, Any]] = {}
    external_assets: list[str] = []
    layout: dict[str, dict[str, Any]] = {}

    for abs_path, node in nodes.items():
        rel_path = _rel(abs_path)
        # Extract expressions from params and scan for external assets
        params_clean: dict[str, Any] = {}
        expressions: dict[str, str] = {}
        raw_params = node.get("params", {})
        for pname, pval in raw_params.items():
            if isinstance(pval, dict):
                value = pval.get("value")
                params_clean[pname] = value
                expr = pval.get("expression") or pval.get("expr")
                if expr:
                    expressions[pname] = expr
                # Scan value for file paths
                if isinstance(value, str) and any(value.lower().endswith(ext) for ext in _ASSET_EXTENSIONS):
                    if value not in external_assets:
                        external_assets.append(value)
            else:
                params_clean[pname] = pval
                # Scan plain string values for file paths
                if isinstance(pval, str) and any(pval.lower().endswith(ext) for ext in _ASSET_EXTENSIONS):
                    if pval not in external_assets:
                        external_assets.append(pval)

        recipe_nodes[rel_path] = {
            "name": node.get("name"),
            "type": node.get("type"),
            "family": node.get("family"),
            "params": params_clean,
        }
        if expressions:
            recipe_nodes[rel_path]["expressions"] = expressions

        # Build layout entry
        layout_entry: dict[str, Any] = {}
        node_x = node.get("nodeX")
        node_y = node.get("nodeY")
        if node_x is not None:
            layout_entry["x"] = node_x
        if node_y is not None:
            layout_entry["y"] = node_y
        color = node.get("color")
        if color is not None:
            layout_entry["color"] = color
        comment = node.get("comment")
        if comment is not None:
            layout_entry["comment"] = comment
        if layout_entry:
            layout[rel_path] = layout_entry

    # Only include connections where both endpoints are within the subtree
    recipe_connections = [
        {
            "from": _rel(c["from"]),
            "to": _rel(c["to"]),
            "from_index": c.get("from_index", 0),
            "to_index": c.get("to_index", 0),
        }
        for c in connections
        if c["from"] in nodes and c["to"] in nodes
    ]

    return {
        "nodes": recipe_nodes,
        "connections": recipe_connections,
        "external_assets": external_assets,
        "layout": layout,
    }


def _extract_key_params(
    nodes: dict[str, dict[str, Any]],
    root_path: str,
) -> list[dict[str, Any]]:
    """For large networks, extract only params with non-default/interesting values."""
    prefix = root_path.rstrip("/")
    key_params: list[dict[str, Any]] = []

    # Param names that are usually interesting
    interesting_names = {
        "file",
        "top",
        "chop",
        "sop",
        "dat",
        "mat",
        "resolutionw",
        "resolutionh",
        "seed",
        "rate",
        "speed",
        "freq",
        "amp",
        "phase",
        "feedback",
        "noise",
        "displace",
        "tx",
        "ty",
        "tz",
        "rx",
        "ry",
        "rz",
        "sx",
        "sy",
        "sz",
        "r",
        "g",
        "b",
        "a",
        "opacity",
    }

    for abs_path, node in nodes.items():
        rel_path = abs_path
        if abs_path.startswith(prefix + "/"):
            rel_path = abs_path[len(prefix) :]

        raw_params = node.get("params", {})
        for pname, pval in raw_params.items():
            pname_lower = pname.lower()
            if isinstance(pval, dict):
                value = pval.get("value")
                expr = pval.get("expression") or pval.get("expr")
                # Include if has expression or is an interesting param
                if expr or pname_lower in interesting_names:
                    entry: dict[str, Any] = {
                        "path": rel_path,
                        "param": pname,
                        "value": value,
                    }
                    if expr:
                        entry["expression"] = expr
                    key_params.append(entry)
            else:
                # Plain scalar param — include if interesting
                if pname_lower in interesting_names:
                    key_params.append(
                        {
                            "path": rel_path,
                            "param": pname,
                            "value": pval,
                        }
                    )

    return key_params[:200]  # Cap at 200 key params
