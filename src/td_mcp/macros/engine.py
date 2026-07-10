"""Macro engine for compound TouchDesigner network creation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from td_mcp.macros.loader import load_user_templates
from td_mcp.macros.models import ExpressionSpec, MacroTemplate, NodeSpec
from td_mcp.macros.templates import build_default_templates

DIRECT_PARAM_PREFLIGHT_CONTRACT = "shared_direct_param_preflight_v1"


class MacroEngine:
    """Builds reusable multi-node patterns using existing TD endpoints."""

    direct_param_preflight_contract = DIRECT_PARAM_PREFLIGHT_CONTRACT

    def __init__(
        self,
        td_client,
        user_template_dir: str | None = None,
        param_preflight: Callable[..., Any] | None = None,
    ):
        self._td_client = td_client
        self._param_preflight = param_preflight
        self._templates: dict[str, MacroTemplate] = build_default_templates()
        self._template_sources: dict[str, str] = {name: "built_in" for name in self._templates.keys()}
        self._load_warnings: list[str] = []

        user_templates, warnings = load_user_templates(user_template_dir)
        self._load_warnings.extend(warnings)
        if user_templates:
            self._templates.update(user_templates)
            for name in user_templates.keys():
                self._template_sources[name] = "user"

    def list_macros(self) -> dict[str, Any]:
        macros = []
        for name, template in self._templates.items():
            summary = template.summary()
            summary["source"] = self._template_sources.get(name, "built_in")
            macros.append(summary)

        return {
            "count": len(self._templates),
            "macros": macros,
            "load_warnings": list(self._load_warnings),
        }

    def get_macro_params(self, macro_type: str) -> dict[str, Any]:
        template = self._templates.get(macro_type)
        if not template:
            raise ValueError(f"Unknown macro_type: {macro_type}")

        return {
            "macro_type": macro_type,
            "description": template.description,
            "source": self._template_sources.get(macro_type, "built_in"),
            "params": {name: spec.to_dict() for name, spec in template.param_schema.items()},
            "capability": template.capability,
            "required_inputs": list(template.required_inputs),
            "outputs": list(template.outputs),
            "completion_status": template.completion_status,
            "limitations": list(template.limitations),
            "deprecation_warning": template.deprecation_warning,
        }

    async def create_macro(
        self,
        *,
        parent_path: str,
        macro_type: str,
        name_prefix: str | None = None,
        node_x: int = 0,
        node_y: int = 0,
        overrides: dict[str, Any] | None = None,
        param_semantics_policy: str = "warn",
    ) -> dict[str, Any]:
        template = self._templates.get(macro_type)
        if not template:
            raise ValueError(f"Unknown macro_type: {macro_type}")

        override_values = overrides or {}
        unknown_keys = [key for key in override_values if key not in template.param_schema]
        if unknown_keys:
            raise ValueError(f"Unknown macro params for '{macro_type}': {', '.join(sorted(unknown_keys))}")

        resolved_values = {key: spec.default for key, spec in template.param_schema.items()}
        resolved_values.update(override_values)
        self._validate_param_ranges(template, resolved_values)

        nodes, extra_expressions = self._apply_param_targets(template, resolved_values)
        if param_semantics_policy == "block":
            pre_create_preflight = self.preflight_macro(
                parent_path=parent_path,
                macro_type=macro_type,
                name_prefix=name_prefix,
                overrides=overrides,
                param_semantics_policy=param_semantics_policy,
            )
            if pre_create_preflight["blocked"]:
                return {
                    "success": False,
                    "blocked": True,
                    "param_semantics_status": "blocked",
                    "macro_type": macro_type,
                    "parent_path": parent_path,
                    "created_nodes": [],
                    "connections": [],
                    "entry_node": None,
                    "exit_node": None,
                    "resolved_params": resolved_values,
                    "warnings": pre_create_preflight["warnings"],
                    "param_semantics_warnings": pre_create_preflight["param_semantics_warnings"],
                }

        created_nodes: list[dict[str, Any]] = []
        logical_to_path: dict[str, str] = {}
        warnings: list[str] = []
        if template.deprecation_warning:
            warnings.append(template.deprecation_warning)

        for node in nodes:
            final_name = f"{name_prefix}_{node.name}" if name_prefix else node.name
            create_body = {
                "parent_path": parent_path,
                "node_type": node.node_type,
                "name": final_name,
                "nodeX": node_x + node.dx,
                "nodeY": node_y + node.dy,
            }
            create_result = await self._td_client.request("node/create", create_body)
            created = create_result.get("node", {})
            path = created.get("path") or f"{parent_path.rstrip('/')}/{final_name}"
            logical_to_path[node.name] = path
            created_nodes.append(
                {
                    "logical_name": node.name,
                    "name": created.get("name", final_name),
                    "path": path,
                    "type": created.get("type", node.node_type),
                }
            )

            if node.params:
                try:
                    adjusted, preflight_warnings = self._preflight_params(
                        path=path,
                        op_type=node.node_type,
                        params=node.params,
                        param_semantics_policy=param_semantics_policy,
                    )
                    warnings.extend(preflight_warnings)
                    await self._td_client.request(
                        "node/params/set",
                        {"path": path, "params": adjusted},
                    )
                except Exception as exc:  # pragma: no cover - dependent on TD runtime
                    warnings.append(f"set_params failed on {path}: {exc}")

        connection_results = []
        for connection in template.connections:
            source_path = logical_to_path.get(connection.source)
            target_path = logical_to_path.get(connection.target)
            if not source_path or not target_path:
                warnings.append(f"Skipped connection {connection.source}->{connection.target}: missing node.")
                continue
            try:
                await self._td_client.request(
                    "node/connect",
                    {
                        "source_path": source_path,
                        "target_path": target_path,
                        "source_index": connection.source_index,
                        "target_index": connection.target_index,
                    },
                )
                connection_results.append(
                    {
                        "source": source_path,
                        "target": target_path,
                        "source_index": connection.source_index,
                        "target_index": connection.target_index,
                    }
                )
            except Exception as exc:  # pragma: no cover - dependent on TD runtime
                warnings.append(f"connect failed {connection.source}->{connection.target}: {exc}")

        for ref in template.node_references:
            node_path = logical_to_path.get(ref.node)
            target_path = logical_to_path.get(ref.target_node)
            if not node_path or not target_path:
                warnings.append(f"Skipped node ref {ref.node}.{ref.param}->{ref.target_node}: missing node.")
                continue
            target_name = target_path.rsplit("/", 1)[-1]
            try:
                adjusted, preflight_warnings = self._preflight_params(
                    path=node_path,
                    op_type=_op_type_for_logical_node(nodes, ref.node),
                    params={ref.param: target_name},
                    param_semantics_policy=param_semantics_policy,
                )
                warnings.extend(preflight_warnings)
                await self._td_client.request(
                    "node/params/set",
                    {"path": node_path, "params": adjusted},
                )
            except Exception as exc:  # pragma: no cover - dependent on TD runtime
                warnings.append(f"node ref failed {ref.node}.{ref.param}: {exc}")

        all_expressions = [*template.expressions, *extra_expressions]
        for expr in all_expressions:
            path = logical_to_path.get(expr.node)
            if not path:
                warnings.append(f"Skipped expression {expr.node}.{expr.param}: node missing.")
                continue
            try:
                adjusted, preflight_warnings = self._preflight_params(
                    path=path,
                    op_type=_op_type_for_logical_node(nodes, expr.node),
                    params={expr.param: {"expr": expr.expr}},
                    param_semantics_policy=param_semantics_policy,
                )
                warnings.extend(preflight_warnings)
                await self._td_client.request(
                    "node/params/set",
                    {"path": path, "params": adjusted},
                )
            except Exception as exc:  # pragma: no cover - dependent on TD runtime
                warnings.append(f"expression failed {path}.{expr.param}: {exc}")

        return {
            "success": True,
            "macro_type": macro_type,
            "parent_path": parent_path,
            "created_nodes": created_nodes,
            "connections": connection_results,
            "entry_node": logical_to_path.get(template.entry_node) if template.entry_node else None,
            "exit_node": logical_to_path.get(template.exit_node) if template.exit_node else None,
            "resolved_params": resolved_values,
            "capability": template.capability,
            "required_inputs": list(template.required_inputs),
            "outputs": list(template.outputs),
            "completion_status": template.completion_status,
            "limitations": list(template.limitations),
            "deprecation_warning": template.deprecation_warning,
            "warnings": warnings,
        }

    def preflight_macro(
        self,
        *,
        parent_path: str,
        macro_type: str,
        name_prefix: str | None = None,
        overrides: dict[str, Any] | None = None,
        param_semantics_policy: str = "warn",
    ) -> dict[str, Any]:
        """Check template-driven parameter writes without creating nodes."""
        template = self._templates.get(macro_type)
        if not template:
            raise ValueError(f"Unknown macro_type: {macro_type}")

        override_values = overrides or {}
        unknown_keys = [key for key in override_values if key not in template.param_schema]
        if unknown_keys:
            raise ValueError(f"Unknown macro params for '{macro_type}': {', '.join(sorted(unknown_keys))}")

        resolved_values = {key: spec.default for key, spec in template.param_schema.items()}
        resolved_values.update(override_values)
        self._validate_param_ranges(template, resolved_values)

        nodes, extra_expressions = self._apply_param_targets(template, resolved_values)
        preflight = self._preflight_template_param_writes(
            parent_path=parent_path,
            name_prefix=name_prefix,
            nodes=nodes,
            node_references=template.node_references,
            expressions=[*template.expressions, *extra_expressions],
            param_semantics_policy=param_semantics_policy,
        )
        return {
            "success": not bool(preflight["blocked"]),
            "blocked": bool(preflight["blocked"]),
            "macro_type": macro_type,
            "parent_path": parent_path,
            "resolved_params": resolved_values,
            "warnings": preflight["warnings"],
            "param_semantics_warnings": preflight["param_semantics_warnings"],
        }

    def _preflight_params(
        self,
        *,
        path: str,
        op_type: str | None,
        params: dict[str, Any],
        param_semantics_policy: str,
    ) -> tuple[dict[str, Any], list[str]]:
        if self._param_preflight is None:
            return dict(params), []
        result = self._param_preflight(
            path=path,
            op_type=op_type,
            params=dict(params),
            param_semantics_policy=param_semantics_policy,
        )
        warnings = [str(item) for item in getattr(result, "safety_warnings", [])]
        warnings.extend(
            _format_param_semantics_warnings(
                path,
                getattr(result, "param_semantics_warnings", []),
            )
        )
        if getattr(result, "blocked", False):
            raise ValueError(f"param semantics blocked macro params for {path}")
        adjusted = getattr(result, "adjusted_params", None)
        return dict(adjusted) if isinstance(adjusted, dict) else dict(params), warnings

    def _preflight_template_param_writes(
        self,
        *,
        parent_path: str,
        name_prefix: str | None,
        nodes: list[NodeSpec],
        node_references: list[Any],
        expressions: list[ExpressionSpec],
        param_semantics_policy: str,
    ) -> dict[str, Any]:
        """Preflight all template-driven param writes before creating nodes."""
        if self._param_preflight is None:
            return {"blocked": False, "warnings": [], "param_semantics_warnings": []}

        logical_to_path = {
            node.name: _predicted_node_path(parent_path, name_prefix, node.name) for node in nodes
        }
        logical_to_name = {node.name: _prefixed_node_name(name_prefix, node.name) for node in nodes}
        warnings: list[str] = []
        param_semantics_warnings: list[str] = []
        blocked = False

        def run(path: str, op_type: str | None, params: dict[str, Any]) -> None:
            nonlocal blocked
            result = self._param_preflight(
                path=path,
                op_type=op_type,
                params=dict(params),
                param_semantics_policy=param_semantics_policy,
            )
            warnings.extend(str(item) for item in getattr(result, "safety_warnings", []) or [])
            formatted = _format_param_semantics_warnings(
                path,
                getattr(result, "param_semantics_warnings", []),
            )
            warnings.extend(formatted)
            param_semantics_warnings.extend(formatted)
            blocked = blocked or bool(getattr(result, "blocked", False))

        for node in nodes:
            if node.params:
                run(logical_to_path[node.name], node.node_type, node.params)

        for ref in node_references:
            node_path = logical_to_path.get(ref.node)
            target_name = logical_to_name.get(ref.target_node)
            if not node_path or target_name is None:
                continue
            run(
                node_path,
                _op_type_for_logical_node(nodes, ref.node),
                {ref.param: target_name},
            )

        for expr in expressions:
            path = logical_to_path.get(expr.node)
            if not path:
                continue
            run(
                path,
                _op_type_for_logical_node(nodes, expr.node),
                {expr.param: {"expr": expr.expr}},
            )

        return {
            "blocked": blocked,
            "warnings": warnings,
            "param_semantics_warnings": param_semantics_warnings,
        }

    def _validate_param_ranges(
        self,
        template: MacroTemplate,
        values: dict[str, Any],
    ) -> None:
        for key, value in values.items():
            spec = template.param_schema[key]
            if spec.min_value is not None and value < spec.min_value:
                raise ValueError(f"{key}={value} below minimum {spec.min_value}")
            if spec.max_value is not None and value > spec.max_value:
                raise ValueError(f"{key}={value} above maximum {spec.max_value}")

    def _apply_param_targets(
        self,
        template: MacroTemplate,
        values: dict[str, Any],
    ) -> tuple[list[NodeSpec], list[ExpressionSpec]]:
        nodes = [
            NodeSpec(
                node_type=node.node_type,
                name=node.name,
                dx=node.dx,
                dy=node.dy,
                params=dict(node.params),
            )
            for node in template.nodes
        ]
        node_lookup = {node.name: node for node in nodes}
        extra_exprs: list[ExpressionSpec] = []

        for key, targets in template.param_targets.items():
            if key not in values:
                continue
            value = values[key]
            for target in targets:
                node = node_lookup.get(target.node)
                if not node:
                    continue
                if target.mode == "expr":
                    if not target.template:
                        continue
                    extra_exprs.append(
                        replace(
                            ExpressionSpec(node=target.node, param=target.param, expr=""),
                            expr=target.template.replace("{value}", str(value)),
                        )
                    )
                else:
                    node.params[target.param] = value

        return nodes, extra_exprs


def _op_type_for_logical_node(nodes: list[NodeSpec], logical_name: str) -> str | None:
    for node in nodes:
        if node.name == logical_name:
            return node.node_type
    return None


def _prefixed_node_name(name_prefix: str | None, logical_name: str) -> str:
    return f"{name_prefix}_{logical_name}" if name_prefix else logical_name


def _predicted_node_path(parent_path: str, name_prefix: str | None, logical_name: str) -> str:
    return f"{parent_path.rstrip('/')}/{_prefixed_node_name(name_prefix, logical_name)}"


def _format_param_semantics_warnings(path: str, warnings: Any) -> list[str]:
    if not isinstance(warnings, list):
        return []
    formatted: list[str] = []
    for item in warnings:
        if isinstance(item, str):
            code = item.strip()
            message = ""
        elif isinstance(item, dict):
            code = str(item.get("code", "") or "").strip()
            message = str(item.get("message", "") or "").strip()
        else:
            code = str(getattr(item, "code", "") or "").strip()
            message = str(getattr(item, "message", "") or "").strip()
        if code and message:
            formatted.append(f"param_semantics:{path}:{code}:{message}")
        elif code:
            formatted.append(f"param_semantics:{path}:{code}")
    return formatted
