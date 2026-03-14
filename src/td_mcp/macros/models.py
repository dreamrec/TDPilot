"""Dataclasses for macro template definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ParamSpec:
    """Validation metadata for a user-overridable macro parameter."""

    type: str
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
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
    params: Dict[str, Any] = field(default_factory=dict)


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
    template: Optional[str] = None  # for expr mode, supports "{value}" interpolation


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
    nodes: List[NodeSpec]
    connections: List[ConnectionSpec]
    expressions: List[ExpressionSpec] = field(default_factory=list)
    node_references: List[NodeRefParam] = field(default_factory=list)
    param_schema: Dict[str, ParamSpec] = field(default_factory=dict)
    param_targets: Dict[str, List[ParamTarget]] = field(default_factory=dict)
    entry_node: Optional[str] = None
    exit_node: Optional[str] = None

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "node_count": len(self.nodes),
            "connection_count": len(self.connections),
            "entry_node": self.entry_node,
            "exit_node": self.exit_node,
            "params": {k: v.to_dict() for k, v in self.param_schema.items()},
        }

