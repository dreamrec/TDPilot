"""Task-specific validation against live post-apply TouchDesigner state.

The engine consumes the internal :class:`ValidationContract` emitted by the
build compiler.  It never treats PatchPlan structure as runtime evidence: a
runtime, visual, signal, or performance assertion must complete its declared
live probe.  Missing endpoints and malformed probe payloads are reported as
``unavailable`` rather than silently passing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from td_mcp.models.brain import ValidationIssue, ValidationReportV2
from td_mcp.models.build import ValidationAssertion, ValidationContract

AssertionStatus = Literal["passed", "failed", "unavailable"]
AssertionCategory = Literal["graph", "runtime", "visual", "performance", "preservation"]


class AssertionResult(BaseModel):
    """One assertion outcome with compact live evidence."""

    model_config = ConfigDict(extra="forbid")

    assertion_id: str
    category: AssertionCategory
    kind: str
    target: str
    required: bool
    status: AssertionStatus
    expected: Any = None
    actual: Any = None
    endpoint: str | None = None
    issue_code: str | None = None
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ContractValidationReport(BaseModel):
    """Aggregate result for a ValidationContract."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    target_root: str
    ok: bool
    results: list[AssertionResult] = Field(default_factory=list)
    failed_assertion_ids: list[str] = Field(default_factory=list)
    unavailable_assertion_ids: list[str] = Field(default_factory=list)
    summary: str


@dataclass(frozen=True)
class _ProbeOutcome:
    status: AssertionStatus
    actual: Any
    endpoint: str | None
    message: str
    evidence: dict[str, Any]


class _ReadSession:
    """Plan-local read cache; never shared across validation runs."""

    def __init__(self, td_client: Any) -> None:
        self.td_client = td_client
        self._cache: dict[str, tuple[bool, Any, str | None]] = {}

    async def request(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        fresh: bool = False,
    ) -> tuple[bool, Any, str | None]:
        key = json.dumps([endpoint, params], sort_keys=True, separators=(",", ":"), default=str)
        if not fresh and key in self._cache:
            return self._cache[key]
        try:
            payload = await self.td_client.request(endpoint, params)
        except Exception as exc:  # noqa: BLE001
            result = (False, None, str(exc))
        else:
            if not isinstance(payload, dict | list):
                result = (False, payload, "probe returned a non-object payload")
            elif isinstance(payload, dict) and payload.get("error"):
                result = (False, payload, str(payload["error"]))
            else:
                result = (True, payload, None)
        if not fresh:
            self._cache[key] = result
        return result


async def validate_contract(td_client: Any, contract: ValidationContract) -> ContractValidationReport:
    """Evaluate every contract assertion against actual post-apply state."""

    session = _ReadSession(td_client)
    results: list[AssertionResult] = []
    groups: tuple[tuple[AssertionCategory, list[ValidationAssertion]], ...] = (
        ("graph", contract.graph_assertions),
        ("runtime", contract.runtime_assertions),
        ("visual", contract.visual_assertions),
        ("performance", contract.performance_assertions),
        ("preservation", contract.preservation_assertions),
    )
    for category, assertions in groups:
        for assertion in assertions:
            outcome = await _evaluate_assertion(session, assertion)
            issue_code = None
            if outcome.status == "failed":
                issue_code = _failure_code(assertion)
            elif outcome.status == "unavailable":
                issue_code = "runtime_probe_unavailable" if category != "graph" else "graph_probe_unavailable"
            results.append(
                AssertionResult(
                    assertion_id=assertion.id,
                    category=category,
                    kind=assertion.kind,
                    target=assertion.target,
                    required=assertion.required,
                    status=outcome.status,
                    expected=assertion.expected,
                    actual=outcome.actual,
                    endpoint=outcome.endpoint,
                    issue_code=issue_code,
                    message=outcome.message,
                    evidence=outcome.evidence,
                )
            )

    required_failures = [item for item in results if item.required and item.status != "passed"]
    failed = [item.assertion_id for item in results if item.status == "failed"]
    unavailable = [item.assertion_id for item in results if item.status == "unavailable"]
    ok = not required_failures
    return ContractValidationReport(
        contract_id=contract.contract_id,
        target_root=contract.target_root,
        ok=ok,
        results=results,
        failed_assertion_ids=failed,
        unavailable_assertion_ids=unavailable,
        summary=(
            f"validation passed: {len(results)} assertion(s)"
            if ok
            else (
                f"validation failed: {len(required_failures)} required assertion(s); "
                f"{len(failed)} failed, {len(unavailable)} unavailable"
            )
        ),
    )


def to_validation_report_v2(report: ContractValidationReport) -> ValidationReportV2:
    """Project contract results into the legacy transaction report envelope."""

    issues = [
        ValidationIssue(
            severity="error" if result.required else "warning",
            code=result.issue_code or "validation_assertion_failed",
            message=result.message,
            path=result.target,
            source="tdpilot-validation-contract",
        )
        for result in report.results
        if result.status != "passed"
    ]
    severity_counts = {
        severity: sum(issue.severity == severity for issue in issues)
        for severity in ("info", "warning", "error", "critical")
    }
    return ValidationReportV2(
        profile="build_program_contract",
        target_root=report.target_root,
        ok=report.ok,
        checks=[result.assertion_id for result in report.results],
        issues=issues,
        severity_counts=severity_counts,
        cheap_metrics={
            "contract_id": report.contract_id,
            "assertion_results": [result.model_dump(mode="json") for result in report.results],
        },
        summary=report.summary,
    )


async def _evaluate_assertion(
    session: _ReadSession,
    assertion: ValidationAssertion,
) -> _ProbeOutcome:
    if assertion.kind == "no_errors" or assertion.probe == "errors":
        return await _probe_errors(session, assertion)
    if assertion.kind == "connected":
        return await _probe_connection(session, assertion)
    if assertion.kind == "operator_count":
        return await _probe_operator_count(session, assertion)
    if assertion.kind == "resolution":
        return await _probe_resolution(session, assertion)
    if assertion.probe == "node_query":
        return await _probe_node(session, assertion)
    if assertion.probe == "param_query":
        return await _probe_parameter(session, assertion)
    if assertion.probe == "cook_info":
        return await _probe_cook(session, assertion)
    if assertion.probe == "chop_data":
        return await _probe_chop(session, assertion)
    if assertion.probe == "geometry_data":
        return await _probe_geometry(session, assertion)
    if assertion.probe == "pop_inspect":
        return await _probe_pop(session, assertion)
    if assertion.probe == "frame_metrics":
        return await _probe_frame(session, assertion)
    if assertion.probe == "screenshot_critic":
        return _unavailable(
            "screenshot_critic",
            "No deterministic screenshot critic is configured for this validation runtime.",
        )
    return _unavailable(None, f"Unsupported validation probe: {assertion.probe}")


async def _probe_node(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "node/detail"
    ok, payload, error = await session.request(endpoint, {"path": assertion.target})
    if not ok:
        return _unavailable(endpoint, f"Node readback unavailable for {assertion.target}: {error}")
    exists = _node_exists(payload)
    actual: Any = exists
    if assertion.kind == "preserved" and isinstance(assertion.expected, dict):
        expected_type = assertion.expected.get("type") or assertion.expected.get("op_type")
        actual_type = _mapping_value(payload, "type", "op_type", "node_type")
        actual = {"exists": exists, "type": actual_type}
        passed = exists and (expected_type is None or actual_type == expected_type)
    else:
        passed = _compare(actual, assertion.comparator, assertion.expected)
    return _evaluated(
        passed,
        actual,
        endpoint,
        assertion,
        evidence={"path": assertion.target},
    )


async def _probe_connection(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "node/connections"
    ok, payload, error = await session.request(endpoint, {"path": assertion.target})
    if not ok:
        return _unavailable(endpoint, f"Connection readback unavailable for {assertion.target}: {error}")
    expected_path = _expected_reference(assertion.expected)
    if not expected_path:
        return _unavailable(endpoint, f"Connection assertion {assertion.id} has no expected endpoint path.")
    actual = _payload_contains_string(payload, expected_path)
    return _evaluated(
        actual,
        {"connected": actual, "expected_path": expected_path},
        endpoint,
        assertion,
        evidence={"path": assertion.target},
    )


async def _probe_errors(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "node/errors"
    ok, payload, error = await session.request(
        endpoint,
        {"path": assertion.target, "recurse": True, "max_depth": 10},
    )
    if not ok:
        return _unavailable(endpoint, f"TD error probe unavailable for {assertion.target}: {error}")
    issues = payload.get("issues") if isinstance(payload, dict) else payload
    if not isinstance(issues, list):
        return _unavailable(endpoint, "TD error probe did not return an issues list.")
    actual = len(issues)
    return _evaluated(
        actual == 0,
        actual,
        endpoint,
        assertion,
        evidence={"issue_count": actual},
    )


async def _probe_operator_count(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "nodes"
    ok, payload, error = await session.request(endpoint, {"path": assertion.target, "limit": 500})
    if not ok:
        return _unavailable(endpoint, f"Operator count unavailable for {assertion.target}: {error}")
    nodes = payload.get("nodes") if isinstance(payload, dict) else payload
    if not isinstance(nodes, list):
        return _unavailable(endpoint, "Operator count probe did not return a nodes list.")
    actual = len(nodes)
    return _evaluated(_compare(actual, assertion.comparator, assertion.expected), actual, endpoint, assertion)


async def _probe_resolution(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "node/detail"
    ok, payload, error = await session.request(endpoint, {"path": assertion.target})
    if not ok:
        return _unavailable(endpoint, f"Resolution readback unavailable for {assertion.target}: {error}")
    resolution = _resolution(payload)
    if resolution is None:
        return _unavailable(endpoint, "Node detail did not include a normalized output resolution.")
    expected = _expected_resolution(assertion.expected)
    if expected is None:
        return _unavailable(
            endpoint, f"Resolution assertion {assertion.id} has no valid expected resolution."
        )
    return _evaluated(
        resolution == expected,
        list(resolution),
        endpoint,
        assertion,
        evidence={"resolution": list(resolution)},
    )


async def _probe_parameter(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    node_path, param_name = _parameter_target(assertion)
    body: dict[str, Any] = {"path": node_path}
    if param_name:
        body["names"] = [param_name]
    endpoint = "node/params"
    ok, payload, error = await session.request(endpoint, body)
    if not ok:
        return _unavailable(endpoint, f"Parameter readback unavailable for {node_path}: {error}")
    parameters = payload.get("parameters") if isinstance(payload, dict) else None
    if not isinstance(parameters, dict):
        return _unavailable(endpoint, "Parameter probe did not return a parameters mapping.")

    if assertion.kind == "binding_readback":
        expected_expr = _expected_expression(assertion.expected)
        entries = [parameters.get(param_name)] if param_name else list(parameters.values())
        expressions = [expr for entry in entries if (expr := _parameter_expression(entry))]
        if not expressions:
            actual: Any = None
            passed = False
        elif expected_expr is None:
            actual = expressions[0]
            passed = True
        else:
            actual = expressions[0]
            passed = any(expr == expected_expr or expected_expr in expr for expr in expressions)
        return _evaluated(
            passed,
            actual,
            endpoint,
            assertion,
            evidence={"path": node_path, "parameter": param_name, "expression_present": bool(expressions)},
        )

    if param_name:
        entry = parameters.get(param_name)
        if entry is None:
            return _unavailable(endpoint, f"Parameter {param_name} was absent from readback.")
        actual = _parameter_value(entry)
    else:
        actual = {name: _parameter_value(entry) for name, entry in parameters.items()}
    return _evaluated(_compare(actual, assertion.comparator, assertion.expected), actual, endpoint, assertion)


async def _probe_cook(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "cooking"
    ok, payload, error = await session.request(
        endpoint,
        {"path": assertion.target, "recurse": True, "sort_by": "cookTime", "limit": 20},
    )
    if not ok:
        return _unavailable(endpoint, f"Cook probe unavailable for {assertion.target}: {error}")
    metric = _cook_metric(payload)
    if metric is None:
        return _unavailable(endpoint, "Cook probe did not return a normalized millisecond metric.")
    expected = _numeric_expected(assertion.expected)
    if expected is None:
        return _unavailable(endpoint, f"Cook assertion {assertion.id} has no numeric budget.")
    passed = _compare(metric, assertion.comparator, expected)
    return _evaluated(
        passed,
        metric,
        endpoint,
        assertion,
        evidence={"cook_time_ms": metric, "budget_ms": expected},
    )


async def _probe_chop(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "chop/data"
    first_ok, first, first_error = await session.request(
        endpoint,
        {"path": assertion.target},
        fresh=assertion.kind == "changing_signal",
    )
    if not first_ok:
        return _unavailable(endpoint, f"CHOP probe unavailable for {assertion.target}: {first_error}")
    first_values = _numeric_samples(first)
    if not first_values:
        return _unavailable(endpoint, "CHOP probe returned no numeric channel samples.")
    threshold = _numeric_expected(assertion.expected) or 1e-6
    if assertion.kind == "changing_signal":
        second_ok, second, second_error = await session.request(
            endpoint,
            {"path": assertion.target},
            fresh=True,
        )
        if not second_ok:
            return _unavailable(endpoint, f"Second CHOP sample unavailable: {second_error}")
        second_values = _numeric_samples(second)
        if not second_values:
            return _unavailable(endpoint, "Second CHOP probe returned no numeric samples.")
        delta = _sample_delta(first_values, second_values)
        return _evaluated(
            delta > threshold,
            delta,
            endpoint,
            assertion,
            evidence={"sample_count": min(len(first_values), len(second_values)), "delta": delta},
        )
    magnitude = max(abs(value) for value in first_values)
    return _evaluated(
        magnitude > threshold,
        magnitude,
        endpoint,
        assertion,
        evidence={"sample_count": len(first_values), "maximum_magnitude": magnitude},
    )


async def _probe_geometry(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "geometry/data"
    ok, payload, error = await session.request(
        endpoint,
        {"path": assertion.target, "include_points": True, "include_prims": False, "limit": 500},
    )
    if not ok:
        return _unavailable(endpoint, f"Geometry probe unavailable for {assertion.target}: {error}")
    count = _element_count(payload, "point_count", "num_points", "points")
    if count is None:
        return _unavailable(endpoint, "Geometry probe did not include a point count.")
    expected = _numeric_expected(assertion.expected) or 0.0
    return _evaluated(count > expected, count, endpoint, assertion, evidence={"point_count": count})


async def _probe_pop(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "pop/inspect"
    ok, payload, error = await session.request(
        endpoint,
        {
            "path": assertion.target,
            "include_bounds": True,
            "include_attributes": True,
            "point_attributes": None,
            "prim_attributes": None,
            "vert_attributes": None,
            "start": 0,
            "count": 32,
            "delayed": False,
        },
    )
    if not ok:
        return _unavailable(endpoint, f"POP probe unavailable for {assertion.target}: {error}")
    count = _element_count(payload, "point_count", "num_points", "points")
    if count is None:
        return _unavailable(endpoint, "POP probe did not include a point count.")
    expected = _numeric_expected(assertion.expected) or 0.0
    return _evaluated(count > expected, count, endpoint, assertion, evidence={"point_count": count})


async def _probe_frame(session: _ReadSession, assertion: ValidationAssertion) -> _ProbeOutcome:
    endpoint = "analyze_frame"
    request = {"path": assertion.target, "modes": ["luminance", "alpha_coverage"]}
    first_ok, first, first_error = await session.request(
        endpoint,
        request,
        fresh=assertion.kind == "changing_signal",
    )
    if not first_ok:
        return _unavailable(endpoint, f"Frame probe unavailable for {assertion.target}: {first_error}")
    stats = _luminance_stats(first)
    if stats is None:
        return _unavailable(endpoint, "Frame probe did not return normalized luminance metrics.")
    mean, maximum, deviation = stats
    threshold = _numeric_expected(assertion.expected)
    threshold = threshold if threshold is not None and not isinstance(assertion.expected, bool) else 1e-6
    if assertion.kind == "not_black":
        passed = maximum > threshold
        actual: Any = passed
        evidence = {"luminance_mean": mean, "luminance_max": maximum}
    elif assertion.kind == "nonuniform_image":
        passed = deviation > threshold
        actual = passed
        evidence = {"luminance_std": deviation}
    elif assertion.kind == "changing_signal":
        second_ok, second, second_error = await session.request(endpoint, request, fresh=True)
        if not second_ok:
            return _unavailable(endpoint, f"Second frame sample unavailable: {second_error}")
        second_stats = _luminance_stats(second)
        if second_stats is None:
            return _unavailable(endpoint, "Second frame probe returned no normalized luminance metrics.")
        delta = max(abs(left - right) for left, right in zip(stats, second_stats, strict=True))
        passed = delta > threshold
        actual = passed
        evidence = {"motion_delta": delta, "sample_count": 2}
    else:
        actual = mean
        passed = _compare(actual, assertion.comparator, assertion.expected)
        evidence = {"luminance_mean": mean, "luminance_max": maximum, "luminance_std": deviation}
    return _evaluated(passed, actual, endpoint, assertion, evidence=evidence)


def _evaluated(
    passed: bool,
    actual: Any,
    endpoint: str,
    assertion: ValidationAssertion,
    *,
    evidence: dict[str, Any] | None = None,
) -> _ProbeOutcome:
    return _ProbeOutcome(
        status="passed" if passed else "failed",
        actual=actual,
        endpoint=endpoint,
        message=(
            f"{assertion.id} passed via {endpoint}."
            if passed
            else f"{assertion.id} failed via {endpoint}: expected {assertion.expected!r}, observed {actual!r}."
        ),
        evidence=evidence or {},
    )


def _unavailable(endpoint: str | None, message: str) -> _ProbeOutcome:
    return _ProbeOutcome(
        status="unavailable",
        actual=None,
        endpoint=endpoint,
        message=message,
        evidence={},
    )


def _compare(actual: Any, comparator: str, expected: Any) -> bool:
    if comparator == "exists":
        return bool(actual) is bool(expected)
    if comparator == "eq":
        return actual == expected
    if comparator == "ne":
        return actual != expected
    if comparator == "contains":
        try:
            return expected in actual
        except TypeError:
            return False
    if comparator == "between":
        if not isinstance(expected, list | tuple) or len(expected) != 2:
            return False
        try:
            return expected[0] <= actual <= expected[1]
        except TypeError:
            return False
    if comparator in {"lt", "lte", "gt", "gte"}:
        try:
            return {
                "lt": actual < expected,
                "lte": actual <= expected,
                "gt": actual > expected,
                "gte": actual >= expected,
            }[comparator]
        except TypeError:
            return False
    return False


def _failure_code(assertion: ValidationAssertion) -> str:
    if assertion.kind == "not_black":
        return "black_feedback_output" if "feedback" in assertion.id.lower() else "visual_output_black"
    if assertion.kind in {"binding_readback", "nonzero_signal", "changing_signal"}:
        return "static_or_missing_binding"
    if assertion.kind == "connected":
        return "missing_connection_or_reference"
    if assertion.kind == "resolution":
        return "resolution_mismatch"
    if assertion.kind == "cook_budget":
        return "excessive_cook_cost"
    return f"validation_{assertion.kind}_failed"


def _node_exists(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and not payload.get("error")
        and any(
            payload.get(key) is not None for key in ("path", "name", "type", "op_type", "node_type", "family")
        )
    )


def _mapping_value(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    return next((payload[key] for key in keys if key in payload), None)


def _payload_contains_string(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, dict):
        return any(_payload_contains_string(item, expected) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_payload_contains_string(item, expected) for item in value)
    return False


def _expected_reference(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        for key in ("path", "source", "target", "reference"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _resolution(payload: Any) -> tuple[int, int] | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("resolution") or payload.get("output_resolution")
    if isinstance(raw, list | tuple) and len(raw) >= 2:
        return _positive_int_pair(raw[0], raw[1])
    width = _mapping_value(payload, "width", "resolutionw", "output_width")
    height = _mapping_value(payload, "height", "resolutionh", "output_height")
    return _positive_int_pair(width, height)


def _expected_resolution(value: Any) -> tuple[int, int] | None:
    if isinstance(value, list | tuple) and len(value) == 2:
        return _positive_int_pair(value[0], value[1])
    if isinstance(value, dict):
        return _positive_int_pair(value.get("width"), value.get("height"))
    return None


def _positive_int_pair(left: Any, right: Any) -> tuple[int, int] | None:
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    if not isinstance(left, int | float) or not isinstance(right, int | float):
        return None
    if left <= 0 or right <= 0:
        return None
    return int(left), int(right)


def _parameter_target(assertion: ValidationAssertion) -> tuple[str, str | None]:
    if isinstance(assertion.expected, dict):
        parameter = assertion.expected.get("parameter") or assertion.expected.get("param")
        if isinstance(parameter, str) and parameter:
            return assertion.target, parameter
    if "::" in assertion.target:
        path, parameter = assertion.target.rsplit("::", 1)
        return path, parameter or None
    marker = ".par."
    if marker in assertion.target:
        path, parameter = assertion.target.rsplit(marker, 1)
        return path, parameter or None
    return assertion.target, None


def _parameter_expression(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    expression = entry.get("expr") or entry.get("expression")
    return str(expression).strip() if isinstance(expression, str) and expression.strip() else None


def _expected_expression(value: Any) -> str | None:
    if not isinstance(value, dict):
        return value if isinstance(value, str) else None
    expression = value.get("expr") or value.get("expression")
    return str(expression).strip() if isinstance(expression, str) and expression.strip() else None


def _parameter_value(entry: Any) -> Any:
    if not isinstance(entry, dict):
        return entry
    for key in ("value", "val", "evaluated", "eval"):
        if key in entry:
            return entry[key]
    return entry


def _numeric_expected(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        for key in ("threshold", "maximum", "max", "value"):
            candidate = value.get(key)
            if isinstance(candidate, int | float) and not isinstance(candidate, bool):
                return float(candidate)
    return None


def _cook_metric(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    direct = _first_number(payload, "total_cook_ms", "cook_time_ms", "cookTime", "cpuCookTime")
    if direct is not None:
        return direct
    nodes = payload.get("nodes")
    if isinstance(nodes, list):
        values = [
            metric
            for node in nodes
            if isinstance(node, dict)
            if (metric := _first_number(node, "cook_time_ms", "cookTime", "cpuCookTime")) is not None
        ]
        return max(values) if values else None
    return None


def _first_number(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(float(value)):
            return float(value)
    return None


def _numeric_samples(payload: Any) -> list[float]:
    values: list[float] = []

    def visit(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int | float) and math.isfinite(float(value)):
            values.append(float(value))
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in {"path", "name", "rate", "start", "end", "sample_rate"}:
                    visit(item)
        elif isinstance(value, list | tuple):
            for item in value:
                visit(item)

    channels = payload.get("channels") if isinstance(payload, dict) else payload
    visit(channels)
    return values


def _sample_delta(first: list[float], second: list[float]) -> float:
    pair_count = min(len(first), len(second))
    if pair_count == 0:
        return 0.0
    return max(abs(first[index] - second[index]) for index in range(pair_count))


def _element_count(payload: Any, *keys: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        if isinstance(value, list):
            return len(value)
    return None


def _luminance_stats(payload: Any) -> tuple[float, float, float] | None:
    if not isinstance(payload, dict):
        return None
    modes = payload.get("modes")
    luminance = modes.get("luminance") if isinstance(modes, dict) else payload.get("luminance")
    if not isinstance(luminance, dict) or luminance.get("error"):
        return None
    values = tuple(_first_number(luminance, key) for key in ("mean", "max", "std"))
    if any(value is None for value in values):
        return None
    return values  # type: ignore[return-value]


__all__ = [
    "AssertionResult",
    "ContractValidationReport",
    "to_validation_report_v2",
    "validate_contract",
]
