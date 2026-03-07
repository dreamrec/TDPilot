"""Network analyzer — extracts technique recipes from live TouchDesigner projects."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Complexity thresholds
SMALL_MAX = 10
MEDIUM_MAX = 20


async def analyze_network(
    client: "TDClient",  # noqa: F821
    path: str,
    *,
    max_depth: int = 3,
    max_nodes: int = 200,
    name: str = "",
    description: str = "",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
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
    families: Dict[str, int] = {}
    op_types: Dict[str, int] = {}
    for node in nodes.values():
        fam = node.get("family", "unknown")
        families[fam] = families.get(fam, 0) + 1
        op_type = node.get("type", "unknown")
        op_types[op_type] = op_types.get(op_type, 0) + 1

    # Key params for large networks
    key_params: Optional[List[Dict[str, Any]]] = None
    if complexity == "large":
        key_params = _extract_key_params(nodes, path)

    return {
        "source_path": path,
        "node_count": node_count,
        "connection_count": len(connections),
        "complexity": complexity,
        "families": families,
        "op_types": op_types,
        "recipe": recipe,
        "key_params": key_params,
        "name": name,
        "description": description,
        "tags": sorted(set(tags or [])),
    }


async def _collect_subtree(
    client: "TDClient",
    root_path: str,
    *,
    max_depth: int = 3,
    max_nodes: int = 200,
) -> tuple:
    """Walk a TD network subtree and collect nodes + connections.

    Returns (nodes_dict, connections_list).
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    connections: List[Dict[str, Any]] = []
    visited: set[str] = set()

    queue: list[tuple] = [(root_path, 0)]

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
        }

        # Collect connections from input list
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

        # Walk children if COMP and within depth
        if detail.get("isCOMP") and depth < max_depth:
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
                child_list = children.get("nodes", [])
                if not child_list:
                    break
                for child in child_list:
                    child_path = child.get("path", "")
                    if child_path and child_path not in visited:
                        queue.append((child_path, depth + 1))
                if len(child_list) < 200:
                    break
                child_offset += 200

    return nodes, connections


def _build_full_recipe(
    nodes: Dict[str, Dict[str, Any]],
    connections: List[Dict[str, Any]],
    root_path: str,
) -> Dict[str, Any]:
    """Build a portable recipe dict with relative paths."""
    prefix = root_path.rstrip("/")

    def _rel(p: str) -> str:
        if p.startswith(prefix + "/"):
            return p[len(prefix) :]
        if p == prefix:
            return "/"
        return p

    recipe_nodes: Dict[str, Dict[str, Any]] = {}
    for abs_path, node in nodes.items():
        rel_path = _rel(abs_path)
        # Extract expressions from params
        params_clean: Dict[str, Any] = {}
        expressions: Dict[str, str] = {}
        raw_params = node.get("params", {})
        for pname, pval in raw_params.items():
            if isinstance(pval, dict):
                params_clean[pname] = pval.get("value")
                expr = pval.get("expression") or pval.get("expr")
                if expr:
                    expressions[pname] = expr
            else:
                params_clean[pname] = pval

        recipe_nodes[rel_path] = {
            "name": node.get("name"),
            "type": node.get("type"),
            "family": node.get("family"),
            "params": params_clean,
        }
        if expressions:
            recipe_nodes[rel_path]["expressions"] = expressions

    recipe_connections = [
        {
            "from": _rel(c["from"]),
            "to": _rel(c["to"]),
            "from_index": c.get("from_index", 0),
            "to_index": c.get("to_index", 0),
        }
        for c in connections
    ]

    return {
        "nodes": recipe_nodes,
        "connections": recipe_connections,
    }


def _extract_key_params(
    nodes: Dict[str, Dict[str, Any]],
    root_path: str,
) -> List[Dict[str, Any]]:
    """For large networks, extract only params with non-default/interesting values."""
    prefix = root_path.rstrip("/")
    key_params: List[Dict[str, Any]] = []

    # Param names that are usually interesting
    interesting_names = {
        "file", "top", "chop", "sop", "dat", "mat",
        "resolutionw", "resolutionh",
        "seed", "rate", "speed", "freq", "amp", "phase",
        "feedback", "noise", "displace",
        "tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz",
        "r", "g", "b", "a", "opacity",
    }

    for abs_path, node in nodes.items():
        rel_path = abs_path
        if abs_path.startswith(prefix + "/"):
            rel_path = abs_path[len(prefix):]

        raw_params = node.get("params", {})
        for pname, pval in raw_params.items():
            pname_lower = pname.lower()
            if isinstance(pval, dict):
                value = pval.get("value")
                expr = pval.get("expression") or pval.get("expr")
                # Include if has expression or is an interesting param
                if expr or pname_lower in interesting_names:
                    entry: Dict[str, Any] = {
                        "path": rel_path,
                        "param": pname,
                        "value": value,
                    }
                    if expr:
                        entry["expression"] = expr
                    key_params.append(entry)

    return key_params[:200]  # Cap at 200 key params
