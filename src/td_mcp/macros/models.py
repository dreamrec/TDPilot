"""Dataclasses for macro template definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParamSpec:
    """Validation metadata for a user-overridable macro parameter."""

    type: str
    default: Any
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "default": self.default,
            "min": self.min_value,
            "max": self.max_value,
            "description": self.description,
        }


@dataclass
class NodeSpec:
    """Node creation spec relative to macro origin coordinates."""

    node_type: str
    name: str
    dx: int = 0
    dy: int = 0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionSpec:
    """Connection wiring between logical node names."""

    source: str
    target: str
    source_index: int = 0
    target_index: int = 0


@dataclass(frozen=True)
class ExpressionSpec:
    """Expression assignment to a logical node parameter."""

    node: str
    param: str
    expr: str


@dataclass(frozen=True)
class ParamTarget:
    """Mapping from user param override to node parameter assignment."""

    node: str
    param: str
    mode: str = "value"  # value | expr
    template: str | None = None  # for expr mode, supports "{value}" interpolation


@dataclass(frozen=True)
class NodeRefParam:
    """Set a parameter on one node to reference another node's resolved name.

    Used by feedbackTOP's ``top`` parameter to close loops without physical
    wires (which cause cook-dependency warnings in TouchDesigner).
    """

    node: str
    param: str
    target_node: str


@dataclass
class MacroTemplate:
    """Complete macro template definition."""

    name: str
    description: str
    nodes: list[NodeSpec]
    connections: list[ConnectionSpec]
    expressions: list[ExpressionSpec] = field(default_factory=list)
    node_references: list[NodeRefParam] = field(default_factory=list)
    param_schema: dict[str, ParamSpec] = field(default_factory=dict)
    param_targets: dict[str, list[ParamTarget]] = field(default_factory=dict)
    entry_node: str | None = None
    exit_node: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "node_count": len(self.nodes),
            "connection_count": len(self.connections),
            "entry_node": self.entry_node,
            "exit_node": self.exit_node,
            "params": {k: v.to_dict() for k, v in self.param_schema.items()},
        }
