"""Budgeted, plan-local inspection orchestration for brain builds.

The planner does not execute MCP tools itself.  It produces a deterministic
set of independent read probes and provides an executor with a cache whose
lifetime is deliberately limited to one inspection plan.  This keeps repeated
reads out of a single planning pass without turning the passive global read
journal into a stale-state cache.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from td_mcp.models.build import BuildMode

InspectionTool = Literal[
    "td_get_focus",
    "td_get_state_vector",
    "td_get_nodes",
    "td_get_node_detail",
    "td_get_connections",
    "td_get_params",
    "td_get_errors",
    "td_get_info",
]

_PROBE_BUDGETS: dict[BuildMode, int] = {
    "fast": 4,
    "production": 7,
    "show_safe": 10,
}


class InspectionProbe(BaseModel):
    """One bounded, read-only inspection call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    tool: InspectionTool
    arguments: dict[str, Any] = Field(default_factory=dict)
    purpose: str = Field(min_length=1, max_length=240)
    independent: bool = True
    critical: bool = False

    @field_validator("arguments")
    @classmethod
    def _arguments_are_json_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("inspection arguments must be JSON serializable") from exc
        return value


class InspectionPlan(BaseModel):
    """Deterministic probe set bounded by the selected execution mode."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1)
    mode: BuildMode
    target_root: str = Field(min_length=1)
    output_path: str | None = None
    maximum_probes: int = Field(ge=1, le=10)
    probes: list[InspectionProbe] = Field(default_factory=list)
    omitted_probe_ids: list[str] = Field(default_factory=list)


class InspectionResult(BaseModel):
    """Normalized evidence returned by one inspection pass."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    values: dict[str, Any] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    cache_hits: list[str] = Field(default_factory=list)
    calls_made: int = Field(default=0, ge=0)


ProbeCaller = Callable[[str, dict[str, Any]], Any | Awaitable[Any]]


class PlanLocalReadCache:
    """Normalized read cache that is never shared between inspection plans."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    @staticmethod
    def key(tool: str, arguments: Mapping[str, Any]) -> str:
        normalized = json.dumps(
            {"arguments": dict(arguments), "tool": tool},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, tool: str, arguments: Mapping[str, Any]) -> tuple[bool, Any]:
        key = self.key(tool, arguments)
        if key not in self._values:
            return False, None
        return True, self._values[key]

    def put(self, tool: str, arguments: Mapping[str, Any], value: Any) -> None:
        self._values[self.key(tool, arguments)] = value


class InspectionPlanner:
    """Create targeted read plans with 4/7/10 fast/production/show-safe caps."""

    def plan(
        self,
        *,
        mode: BuildMode,
        target_root: str,
        output_path: str | None = None,
        selected_paths: Iterable[str] = (),
        relevant_param_paths: Iterable[str] = (),
        inspect_focus: bool = True,
        modification: bool = False,
        include_runtime_info: bool = False,
    ) -> InspectionPlan:
        budget = _PROBE_BUDGETS[mode]
        candidates: list[InspectionProbe] = []

        def add(
            probe_id: str,
            tool: InspectionTool,
            arguments: dict[str, Any],
            purpose: str,
            *,
            critical: bool = False,
        ) -> None:
            candidates.append(
                InspectionProbe(
                    id=probe_id,
                    tool=tool,
                    arguments=arguments,
                    purpose=purpose,
                    critical=critical,
                )
            )

        if inspect_focus:
            add("focus", "td_get_focus", {}, "Resolve active network and selection")
        add(
            "state",
            "td_get_state_vector",
            {"path": target_root, "force": False},
            "Read compact project and target state",
            critical=True,
        )
        add(
            "children",
            "td_get_nodes",
            {"path": target_root, "include_params": False, "limit": 100},
            "Inspect direct target children",
            critical=True,
        )
        add(
            "errors",
            "td_get_errors",
            {"path": target_root, "include_warnings": True, "limit": 100},
            "Establish the pre-build error baseline",
            critical=True,
        )

        normalized_selected = _stable_paths(selected_paths, excluding={target_root})
        for index, path in enumerate(normalized_selected):
            add(
                f"selected_{index}",
                "td_get_node_detail",
                {"path": path},
                "Inspect a selected or explicitly relevant node",
            )

        if output_path:
            add(
                "output_detail",
                "td_get_node_detail",
                {"path": output_path},
                "Inspect stable output metadata",
                critical=modification,
            )
            add(
                "output_connections",
                "td_get_connections",
                {"path": output_path},
                "Preserve the active output route",
                critical=modification,
            )

        for index, path in enumerate(_stable_paths(relevant_param_paths)):
            add(
                f"params_{index}",
                "td_get_params",
                {"path": path, "include_meta": True},
                "Read only parameters relevant to the requested change",
            )

        if include_runtime_info:
            add("runtime", "td_get_info", {}, "Confirm TouchDesigner build and runtime context")

        candidates = _dedupe_probes(candidates)
        selected, omitted = _select_with_budget(candidates, budget)
        fingerprint_payload = {
            "mode": mode,
            "output_path": output_path,
            "probes": [probe.model_dump(mode="json") for probe in selected],
            "target_root": target_root,
        }
        plan_id = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return InspectionPlan(
            plan_id=f"inspect-{plan_id}",
            mode=mode,
            target_root=target_root,
            output_path=output_path,
            maximum_probes=budget,
            probes=selected,
            omitted_probe_ids=[probe.id for probe in omitted],
        )

    async def execute(self, plan: InspectionPlan, caller: ProbeCaller) -> InspectionResult:
        """Execute a plan using only a cache scoped to this call."""
        cache = PlanLocalReadCache()
        values: dict[str, Any] = {}
        errors: dict[str, str] = {}
        cache_hits: list[str] = []
        calls_made = 0
        for probe in plan.probes:
            hit, value = cache.get(probe.tool, probe.arguments)
            if hit:
                values[probe.id] = value
                cache_hits.append(probe.id)
                continue
            try:
                value = caller(probe.tool, dict(probe.arguments))
                if inspect.isawaitable(value):
                    value = await value
                value = _normalize_value(value)
                cache.put(probe.tool, probe.arguments, value)
                values[probe.id] = value
                calls_made += 1
            except Exception as exc:  # noqa: BLE001 - read probes are evidence, not mutation gates
                errors[probe.id] = f"{type(exc).__name__}: {exc}"
                calls_made += 1
        return InspectionResult(
            plan_id=plan.plan_id,
            values=values,
            errors=errors,
            cache_hits=cache_hits,
            calls_made=calls_made,
        )


def _stable_paths(paths: Iterable[str], *, excluding: set[str] | None = None) -> list[str]:
    blocked = excluding or set()
    return sorted({path.strip() for path in paths if path and path.strip() not in blocked})


def _dedupe_probes(probes: Iterable[InspectionProbe]) -> list[InspectionProbe]:
    seen: set[str] = set()
    result: list[InspectionProbe] = []
    for probe in probes:
        key = PlanLocalReadCache.key(probe.tool, probe.arguments)
        if key in seen:
            continue
        seen.add(key)
        result.append(probe)
    return result


def _select_with_budget(
    probes: list[InspectionProbe],
    budget: int,
) -> tuple[list[InspectionProbe], list[InspectionProbe]]:
    if len(probes) <= budget:
        return probes, []
    # Critical probes are stable gates. Remaining slots preserve deterministic
    # candidate order, which itself is ordered from broadest/cheapest evidence
    # to narrower reads.
    critical = [probe for probe in probes if probe.critical]
    selected = critical[:budget]
    selected_ids = {id(probe) for probe in selected}
    for probe in probes:
        if len(selected) >= budget:
            break
        if id(probe) not in selected_ids:
            selected.append(probe)
            selected_ids.add(id(probe))
    selected_keys = {PlanLocalReadCache.key(item.tool, item.arguments) for item in selected}
    omitted = [
        probe for probe in probes if PlanLocalReadCache.key(probe.tool, probe.arguments) not in selected_keys
    ]
    return selected, omitted


def _normalize_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_value(item) for key, item in sorted(value.items(), key=lambda x: str(x[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "InspectionPlan",
    "InspectionPlanner",
    "InspectionProbe",
    "InspectionResult",
    "PlanLocalReadCache",
]
