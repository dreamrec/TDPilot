"""User macro template loader for local JSON template packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from td_mcp.macros.models import (
    ConnectionSpec,
    ExpressionSpec,
    MacroTemplate,
    NodeRefParam,
    NodeSpec,
    ParamSpec,
    ParamTarget,
)


def default_template_dir() -> Path:
    return Path("~/.tdpilot/templates").expanduser()


def load_user_templates(directory: str | Path | None = None) -> tuple[dict[str, MacroTemplate], list[str]]:
    """Load user-defined macro templates from JSON files.

    Expected JSON forms:
    - single template object
    - {"templates": [ ... ]}
    """
    template_dir = Path(directory).expanduser() if directory else default_template_dir()
    if not template_dir.exists() or not template_dir.is_dir():
        return {}, []

    templates: dict[str, MacroTemplate] = {}
    warnings: list[str] = []

    for file_path in sorted(template_dir.glob("*.json")):
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"{file_path.name}: failed to parse JSON ({exc})")
            continue

        entries: list[dict[str, Any]]
        if isinstance(raw, dict) and isinstance(raw.get("templates"), list):
            entries = [entry for entry in raw["templates"] if isinstance(entry, dict)]
        elif isinstance(raw, dict):
            entries = [raw]
        else:
            warnings.append(f"{file_path.name}: expected object or {{'templates': [...]}}")
            continue

        for index, entry in enumerate(entries):
            try:
                template = _parse_template(entry)
            except Exception as exc:
                warnings.append(f"{file_path.name}[{index}]: {exc}")
                continue
            templates[template.name] = template

    return templates, warnings


def _parse_template(data: dict[str, Any]) -> MacroTemplate:
    name = _as_str(data.get("name"), field="name")
    description = _as_str(data.get("description", ""), field="description")

    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("'nodes' must be a non-empty list")
    nodes = [_parse_node(item) for item in raw_nodes]

    raw_connections = data.get("connections")
    if not isinstance(raw_connections, list):
        raise ValueError("'connections' must be a list")
    connections = [_parse_connection(item) for item in raw_connections]

    raw_expressions = data.get("expressions", [])
    if not isinstance(raw_expressions, list):
        raise ValueError("'expressions' must be a list when provided")
    expressions = [_parse_expression(item) for item in raw_expressions]

    raw_schema = data.get("param_schema", {})
    if not isinstance(raw_schema, dict):
        raise ValueError("'param_schema' must be an object when provided")
    param_schema = {key: _parse_param_spec(key, value) for key, value in raw_schema.items()}

    raw_targets = data.get("param_targets", {})
    if not isinstance(raw_targets, dict):
        raise ValueError("'param_targets' must be an object when provided")
    param_targets: dict[str, list[ParamTarget]] = {}
    for key, target_list in raw_targets.items():
        if not isinstance(target_list, list):
            raise ValueError(f"param_targets.{key} must be a list")
        param_targets[key] = [_parse_param_target(item) for item in target_list]

    raw_node_refs = data.get("node_references", [])
    if not isinstance(raw_node_refs, list):
        raise ValueError("'node_references' must be a list when provided")
    node_references = [_parse_node_ref(item) for item in raw_node_refs]

    entry_node = data.get("entry_node")
    if entry_node is not None and not isinstance(entry_node, str):
        raise ValueError("'entry_node' must be a string when provided")

    exit_node = data.get("exit_node")
    if exit_node is not None and not isinstance(exit_node, str):
        raise ValueError("'exit_node' must be a string when provided")

    return MacroTemplate(
        name=name,
        description=description,
        nodes=nodes,
        connections=connections,
        expressions=expressions,
        node_references=node_references,
        param_schema=param_schema,
        param_targets=param_targets,
        entry_node=entry_node,
        exit_node=exit_node,
    )


def _parse_node(data: Any) -> NodeSpec:
    if not isinstance(data, dict):
        raise ValueError("node item must be an object")

    node_type = _as_str(data.get("node_type"), field="node_type")
    name = _as_str(data.get("name"), field="name")
    dx = int(data.get("dx", 0))
    dy = int(data.get("dy", 0))
    params = data.get("params", {})
    if not isinstance(params, dict):
        raise ValueError("node.params must be an object")

    return NodeSpec(
        node_type=node_type,
        name=name,
        dx=dx,
        dy=dy,
        params=dict(params),
    )


def _parse_connection(data: Any) -> ConnectionSpec:
    if not isinstance(data, dict):
        raise ValueError("connection item must be an object")

    return ConnectionSpec(
        source=_as_str(data.get("source"), field="source"),
        target=_as_str(data.get("target"), field="target"),
        source_index=int(data.get("source_index", 0)),
        target_index=int(data.get("target_index", 0)),
    )


def _parse_expression(data: Any) -> ExpressionSpec:
    if not isinstance(data, dict):
        raise ValueError("expression item must be an object")

    return ExpressionSpec(
        node=_as_str(data.get("node"), field="node"),
        param=_as_str(data.get("param"), field="param"),
        expr=_as_str(data.get("expr"), field="expr"),
    )


def _parse_param_spec(key: str, data: Any) -> ParamSpec:
    if not isinstance(data, dict):
        raise ValueError(f"param_schema.{key} must be an object")

    if "default" not in data:
        raise ValueError(f"param_schema.{key} requires 'default'")

    return ParamSpec(
        type=str(data.get("type", "any")),
        default=data.get("default"),
        min_value=_optional_float(data.get("min")),
        max_value=_optional_float(data.get("max")),
        description=str(data.get("description", "")),
    )


def _parse_param_target(data: Any) -> ParamTarget:
    if not isinstance(data, dict):
        raise ValueError("param target item must be an object")

    mode = str(data.get("mode", "value"))
    if mode not in {"value", "expr"}:
        raise ValueError("param target mode must be 'value' or 'expr'")

    template = data.get("template")
    if template is not None and not isinstance(template, str):
        raise ValueError("param target template must be a string")

    return ParamTarget(
        node=_as_str(data.get("node"), field="node"),
        param=_as_str(data.get("param"), field="param"),
        mode=mode,
        template=template,
    )


def _parse_node_ref(data: Any) -> NodeRefParam:
    if not isinstance(data, dict):
        raise ValueError("node_references item must be an object")

    return NodeRefParam(
        node=_as_str(data.get("node"), field="node"),
        param=_as_str(data.get("param"), field="param"),
        target_node=_as_str(data.get("target_node"), field="target_node"),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field}' must be a non-empty string")
    return value
