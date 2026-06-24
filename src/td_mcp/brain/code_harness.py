"""Static checks for generated Python and GLSL code blocks."""

from __future__ import annotations

import ast
import inspect
import math
import re
from typing import Any

from pydantic import ValidationError

from td_mcp.models.brain import GeneratedCodeBlock, ValidationIssue
from td_mcp.models.patch import PatchPlan

_TOPOLOGY_CAPACITY_PARAMS = (
    "maxlines",
    "maxlinestrips",
    "maxlsverts",
    "maxpointprims",
    "maxpoints",
    "maxquads",
    "maxtriangles",
)

_REQUIRED_GENERATED_CODE_LANGUAGES = ("glsl", "python")

_SUPPORTED_GENERATED_CODE_STATIC_CHECKS = (
    "python_syntax",
    "script_chop_cook_signature",
    "script_top_uses_copy_numpy_array",
    "script_dat_cook_callback",
    "script_sop_cook_callback",
    "dat_execute_table_change_callback",
    "chop_execute_value_change_callback",
    "parameter_execute_value_change_callback",
    "panel_execute_value_change_callback",
    "pargroup_execute_value_change_callback",
    "op_execute_state_change_callback",
    "glsl_no_version_line",
    "glsl_top_declares_pixel_output",
    "glsl_top_uses_td_output_swizzle",
    "glsl_mat_vertex_shader",
    "glsl_mat_pixel_shader",
    "glsl_pop_bounds_guard",
)

_SUPPORTED_GENERATED_CODE_RUNTIME_CHECKS = (
    "callback_guard_present",
    "compile_state",
    "diagnostic_output_present",
    "finite_pop_bounds",
    "topology_capacity",
)

_GENERATED_CODE_HARNESS_SOURCES = {
    "language:glsl": ["https://docs.derivative.ca/Write_a_GLSL_TOP"],
    "language:python": ["https://docs.derivative.ca/Python"],
    "python_syntax": ["https://docs.derivative.ca/Python"],
    "script_chop_cook_signature": ["https://docs.derivative.ca/Script_CHOP"],
    "script_top_uses_copy_numpy_array": ["https://docs.derivative.ca/Script_TOP"],
    "script_dat_cook_callback": ["https://docs.derivative.ca/Script_DAT"],
    "script_sop_cook_callback": ["https://docs.derivative.ca/Script_SOP"],
    "dat_execute_table_change_callback": ["https://docs.derivative.ca/DAT_Execute_DAT"],
    "chop_execute_value_change_callback": ["https://docs.derivative.ca/CHOP_Execute_DAT"],
    "parameter_execute_value_change_callback": ["https://docs.derivative.ca/Parameter_Execute_DAT"],
    "panel_execute_value_change_callback": ["https://docs.derivative.ca/Panel_Execute_DAT"],
    "pargroup_execute_value_change_callback": ["https://docs.derivative.ca/ParGroup_Execute_DAT"],
    "op_execute_state_change_callback": ["https://docs.derivative.ca/OP_Execute_DAT"],
    "glsl_no_version_line": ["https://docs.derivative.ca/Write_a_GLSL_TOP"],
    "glsl_top_declares_pixel_output": ["https://docs.derivative.ca/GLSL_TOP"],
    "glsl_top_uses_td_output_swizzle": ["https://docs.derivative.ca/Write_a_GLSL_TOP"],
    "glsl_mat_vertex_shader": ["https://docs.derivative.ca/GLSL_MAT"],
    "glsl_mat_pixel_shader": ["https://docs.derivative.ca/GLSL_MAT"],
    "glsl_pop_bounds_guard": ["https://docs.derivative.ca/Write_a_GLSL_POP"],
    "callback_guard_present": ["https://docs.derivative.ca/DAT_Execute_DAT"],
    "compile_state": ["https://docs.derivative.ca/GLSL_TOP"],
    "diagnostic_output_present": ["https://docs.derivative.ca/DAT_Execute_DAT"],
    "finite_pop_bounds": ["https://docs.derivative.ca/POP"],
    "topology_capacity": ["https://docs.derivative.ca/GLSL_Advanced_POP"],
}


def _validator_source(*funcs: Any) -> str:
    """Concatenate the source of the given validator functions.

    Used to derive what the harness *actually* checks independently of the
    declared-required constants — so the coverage report can detect a required
    check that was declared but never wired into a validator body.
    """
    parts: list[str] = []
    for fn in funcs:
        try:
            parts.append(inspect.getsource(fn))
        except (OSError, TypeError):  # pragma: no cover - source is present in-repo
            continue
    return "\n".join(parts)


def _discovered_static_check_coverage() -> list[str]:
    # Source of the static validators ONLY (never the _SUPPORTED_* tuple or the
    # _SOURCES dict, which list every id) — a check is "covered" only if its id
    # is dispatched on inside a validator body.
    source = _validator_source(
        validate_generated_code_blocks,
        _validate_python_block,
        _validate_glsl_block,
        _validate_plan_attachments,
    )
    # A check is wired if its id is dispatched on (``"<id>" in checks``) or if it
    # is an always-on validator emitting the ``"<id>_error"`` issue code
    # (e.g. python_syntax -> python_syntax_error via ast.parse).
    return sorted(
        c for c in _SUPPORTED_GENERATED_CODE_STATIC_CHECKS if f'"{c}"' in source or f'"{c}_error"' in source
    )


def _discovered_runtime_check_coverage() -> list[str]:
    source = _validator_source(validate_generated_code_runtime_contracts)
    return sorted(c for c in _SUPPORTED_GENERATED_CODE_RUNTIME_CHECKS if f'"{c}"' in source)


def _discovered_language_coverage() -> list[str]:
    # A language is covered only if validate_generated_code_blocks routes it to a
    # validator (block.language == "<lang>").
    source = _validator_source(validate_generated_code_blocks)
    return sorted(c for c in _REQUIRED_GENERATED_CODE_LANGUAGES if f'== "{c}"' in source)


def generated_code_harness_coverage_report() -> dict[str, Any]:
    """Report the generated-code harness surface.

    ``covered_*`` is DISCOVERED from the validator function bodies (not copied
    from the declared-required constants), so the report fails if a required
    language/check is declared but never wired into a validator — i.e. it is a
    real wiring check, not a tautology.
    """
    required_languages = sorted(_REQUIRED_GENERATED_CODE_LANGUAGES)
    covered_languages = _discovered_language_coverage()
    required_static_checks = sorted(_SUPPORTED_GENERATED_CODE_STATIC_CHECKS)
    covered_static_checks = _discovered_static_check_coverage()
    required_runtime_checks = sorted(_SUPPORTED_GENERATED_CODE_RUNTIME_CHECKS)
    covered_runtime_checks = _discovered_runtime_check_coverage()
    missing_languages = sorted(set(required_languages) - set(covered_languages))
    missing_static_checks = sorted(set(required_static_checks) - set(covered_static_checks))
    missing_runtime_checks = sorted(set(required_runtime_checks) - set(covered_runtime_checks))
    invalid_sources = _invalid_harness_source_records(
        required_languages=required_languages,
        required_static_checks=required_static_checks,
        required_runtime_checks=required_runtime_checks,
    )
    return {
        "schema_version": 1,
        "ok": not missing_languages
        and not missing_static_checks
        and not missing_runtime_checks
        and not invalid_sources,
        "required_languages": required_languages,
        "covered_languages": covered_languages,
        "missing_languages": missing_languages,
        "missing_language_count": len(missing_languages),
        "required_static_checks": required_static_checks,
        "covered_static_checks": covered_static_checks,
        "missing_static_checks": missing_static_checks,
        "missing_static_check_count": len(missing_static_checks),
        "required_runtime_checks": required_runtime_checks,
        "covered_runtime_checks": covered_runtime_checks,
        "missing_runtime_checks": missing_runtime_checks,
        "missing_runtime_check_count": len(missing_runtime_checks),
        "sources_by_check": dict(sorted(_GENERATED_CODE_HARNESS_SOURCES.items())),
        "invalid_sources": invalid_sources,
        "invalid_source_count": len(invalid_sources),
    }


def extract_generated_code_blocks(plan: PatchPlan) -> list[GeneratedCodeBlock]:
    """Extract generated-code metadata from PatchPlan set-param operations."""
    blocks: list[GeneratedCodeBlock] = []
    for operation in plan.operations:
        if operation.kind not in {"set_params", "set_dat_content"}:
            continue
        metadata = operation.args.get("generated_code")
        if not isinstance(metadata, dict):
            continue
        payload: dict[str, Any] = dict(metadata)
        if "code" not in payload:
            text = _operation_text_payload(operation)
            if isinstance(text, str):
                payload["code"] = text
        if "source_refs" not in payload and operation.target:
            payload["source_refs"] = [operation.target]
        blocks.append(GeneratedCodeBlock(**payload))
    return blocks


def validate_patch_plan_generated_code(plan: PatchPlan) -> list[ValidationIssue]:
    """Validate generated code payloads and their plan attachments."""
    try:
        blocks = extract_generated_code_blocks(plan)
    except ValidationError as exc:
        return [
            _issue(
                code="invalid_generated_code_metadata",
                message=f"Generated code metadata is invalid: {exc.errors()[0].get('msg', exc)}",
            )
        ]
    issues = validate_generated_code_blocks(blocks)
    issues.extend(_validate_plan_attachments(plan, blocks))
    return _dedupe_issues(issues)


def validate_generated_code_blocks(blocks: list[GeneratedCodeBlock]) -> list[ValidationIssue]:
    """Run static checks on explicit generated code blocks."""
    issues: list[ValidationIssue] = []
    for block in blocks:
        if block.language == "python":
            issues.extend(_validate_python_block(block))
        elif block.language == "glsl":
            issues.extend(_validate_glsl_block(block))
    return _dedupe_issues(issues)


def patch_plan_generated_code_runtime_contracts(plan: PatchPlan) -> list[dict[str, Any]]:
    """Return runtime validation contracts declared by generated code in a patch plan."""
    return generated_code_runtime_contracts(extract_generated_code_blocks(plan))


def generated_code_runtime_contracts(blocks: list[GeneratedCodeBlock]) -> list[dict[str, Any]]:
    """Return source-free runtime contracts for generated Python/GLSL blocks."""
    contracts: list[dict[str, Any]] = []
    for block in blocks:
        for check_id in block.runtime_checks:
            contracts.append(
                {
                    "block_id": block.block_id,
                    "check_id": check_id,
                    "language": block.language,
                    "target_op": block.target_op,
                    "target_param": block.target_param,
                    "source_refs": list(block.source_refs),
                    "expected_outputs": list(block.expected_outputs),
                    "risk_flags": list(block.risk_flags),
                    "official_sources": list(block.official_sources),
                }
            )
    return contracts


async def validate_generated_code_runtime_contracts(
    td_client,
    contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate generated-code runtime contracts against live TD readbacks."""
    evidence: list[dict[str, Any]] = []
    issues: list[ValidationIssue] = []
    content_cache: dict[str, str] = {}
    errors_cache: dict[str, list[dict[str, Any]]] = {}
    pop_bounds_cache: dict[str, dict[str, Any]] = {}
    topology_capacity_cache: dict[str, dict[str, Any]] = {}

    for contract in contracts:
        check_id = str(contract.get("check_id") or "")
        target_op = str(contract.get("target_op") or "")
        if check_id == "compile_state":
            readback_error: str | None = None
            try:
                error_issues = await _contract_errors(td_client, target_op, errors_cache)
            except Exception as exc:
                readback_error = str(exc) or type(exc).__name__
                error_issues = [{"message": readback_error}]
            status = "runtime_pass" if not error_issues else "runtime_fail"
            evidence.append(
                _runtime_evidence(
                    contract, status=status, endpoint="node/errors", issue_count=len(error_issues)
                )
            )
            if error_issues:
                if readback_error is not None:
                    issues.append(
                        _issue(
                            code="generated_code_runtime_compile_state_readback_error",
                            message=(
                                f"{contract.get('block_id')} compile_state readback for "
                                f"{target_op} failed: {readback_error}."
                            ),
                            path=target_op,
                        )
                    )
                    continue
                issues.append(
                    _issue(
                        code="generated_code_runtime_compile_state_error",
                        message=(
                            f"{contract.get('block_id')} compile_state readback reported "
                            f"{len(error_issues)} issue(s): {_first_issue_message(error_issues)}"
                        ),
                        path=target_op,
                    )
                )
            continue

        if check_id in {"callback_guard_present", "diagnostic_output_present"}:
            try:
                content = await _contract_content(td_client, target_op, content_cache)
            except Exception as exc:
                readback_error = str(exc) or type(exc).__name__
                evidence.append(
                    _runtime_evidence(
                        contract,
                        status="runtime_fail",
                        endpoint="node/content",
                        issue_count=1,
                    )
                )
                issues.append(
                    _issue(
                        code="generated_code_runtime_callback_content_readback_error",
                        message=(
                            f"{contract.get('block_id')} callback content readback for "
                            f"{target_op} failed: {readback_error}."
                        ),
                        path=target_op,
                    )
                )
                continue
            if check_id == "callback_guard_present":
                ok = _has_dat_execute_callback_guard(content)
                issue_code = "generated_code_runtime_callback_guard_missing"
                issue_message = (
                    f"{contract.get('block_id')} live callback text is missing tdpilot_callback_guard."
                )
            else:
                ok = _has_callback_diagnostic_output(content, list(contract.get("expected_outputs") or []))
                issue_code = "generated_code_runtime_diagnostic_output_missing"
                issue_message = (
                    f"{contract.get('block_id')} live callback text does not reference expected diagnostics."
                )
            evidence.append(
                _runtime_evidence(
                    contract,
                    status="runtime_pass" if ok else "runtime_fail",
                    endpoint="node/content",
                    issue_count=0 if ok else 1,
                )
            )
            if not ok:
                issues.append(_issue(code=issue_code, message=issue_message, path=target_op))
            continue

        if check_id == "finite_pop_bounds":
            bounds_path = _pop_bounds_contract_path(contract)
            readback_error: str | None = None
            try:
                bounds_payload = await _contract_pop_bounds(td_client, bounds_path, pop_bounds_cache)
                ok = _has_finite_pop_bounds(bounds_payload)
            except Exception as exc:
                ok = False
                readback_error = str(exc) or type(exc).__name__
            evidence.append(
                _runtime_evidence(
                    contract,
                    status="runtime_pass" if ok else "runtime_fail",
                    endpoint="pop/bounds",
                    issue_count=0 if ok else 1,
                )
            )
            if not ok:
                if readback_error is not None:
                    issues.append(
                        _issue(
                            code="generated_code_runtime_finite_pop_bounds_readback_error",
                            message=(
                                f"{contract.get('block_id')} finite_pop_bounds readback for "
                                f"{bounds_path} failed: {readback_error}."
                            ),
                            path=bounds_path,
                        )
                    )
                    continue
                issues.append(
                    _issue(
                        code="generated_code_runtime_finite_pop_bounds_error",
                        message=(
                            f"{contract.get('block_id')} finite_pop_bounds readback for "
                            f"{bounds_path} did not report finite POP bounds."
                        ),
                        path=bounds_path,
                    )
                )
            continue

        if check_id == "topology_capacity":
            readback_error: str | None = None
            try:
                capacity_payload = await _contract_topology_capacity(
                    td_client,
                    target_op,
                    topology_capacity_cache,
                )
                ok = _has_topology_capacity(capacity_payload)
            except Exception as exc:
                ok = False
                readback_error = str(exc) or type(exc).__name__
            evidence.append(
                _runtime_evidence(
                    contract,
                    status="runtime_pass" if ok else "runtime_fail",
                    endpoint="node/params",
                    issue_count=0 if ok else 1,
                )
            )
            if not ok:
                if readback_error is not None:
                    issues.append(
                        _issue(
                            code="generated_code_runtime_topology_capacity_readback_error",
                            message=(
                                f"{contract.get('block_id')} topology_capacity readback for "
                                f"{target_op} failed: {readback_error}."
                            ),
                            path=target_op,
                        )
                    )
                    continue
                issues.append(
                    _issue(
                        code="generated_code_runtime_topology_capacity_error",
                        message=(
                            f"{contract.get('block_id')} topology_capacity readback for "
                            f"{target_op} did not report finite non-negative capacity values."
                        ),
                        path=target_op,
                    )
                )
            continue

        evidence.append(_runtime_evidence(contract, status="runtime_fail", endpoint=None, issue_count=1))
        issues.append(
            _issue(
                code="generated_code_runtime_check_unsupported",
                message=(
                    f"{contract.get('block_id')} declares unsupported generated-code runtime check "
                    f"{check_id!r}."
                ),
                path=target_op,
            )
        )

    return {
        "schema_version": 1,
        "ok": not issues,
        "contract_count": len(contracts),
        "checked_contract_count": sum(1 for item in evidence if item["status"] != "runtime_unchecked"),
        "evidence": evidence,
        "issues": _dedupe_issues(issues),
    }


def _validate_python_block(block: GeneratedCodeBlock) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        ast.parse(block.code)
    except SyntaxError as exc:
        return [
            _issue(
                code="python_syntax_error",
                message=f"{block.block_id} has Python syntax error at line {exc.lineno}: {exc.msg}.",
                path=block.target_op,
            )
        ]

    checks = set(block.static_checks)
    runtime_checks = set(block.runtime_checks)
    if "diagnostic_output_present" in runtime_checks and not _has_callback_diagnostic_output(
        block.code,
        block.expected_outputs,
    ):
        issues.append(
            _issue(
                code="missing_callback_diagnostic_output",
                message=(
                    f"{block.block_id} declares a diagnostic output runtime check "
                    "but does not reference any expected diagnostic output."
                ),
                path=block.target_op,
            )
        )
    if "script_chop_cook_signature" in checks and not _has_python_function(block.code, "cook", "scriptOp"):
        issues.append(
            _issue(
                code="missing_script_chop_cook_callback",
                message=f"{block.block_id} must define cook(scriptOp) for Script CHOP callbacks.",
                path=block.target_op,
            )
        )
    if "script_chop_cook_signature" in checks and block.target_param != "callbacks":
        issues.append(
            _issue(
                code="generated_python_target_not_callbacks_parameter",
                message=(
                    f"{block.block_id} must target the Script CHOP callbacks parameter, "
                    "not the storage DAT text parameter."
                ),
                path=block.target_op,
            )
        )
    if "script_top_uses_copy_numpy_array" in checks and "copyNumpyArray" not in block.code:
        issues.append(
            _issue(
                code="missing_script_top_copy_numpy_array",
                message=f"{block.block_id} must write Script TOP image output with copyNumpyArray().",
                path=block.target_op,
            )
        )
    if "script_top_uses_copy_numpy_array" in checks and block.target_param != "callbacks":
        issues.append(
            _issue(
                code="generated_python_target_not_callbacks_parameter",
                message=(
                    f"{block.block_id} must target the Script TOP callbacks parameter, "
                    "not the storage DAT text parameter."
                ),
                path=block.target_op,
            )
        )
    if "script_dat_cook_callback" in checks and not _has_python_function_named(block.code, "cook"):
        issues.append(
            _issue(
                code="missing_script_dat_cook_callback",
                message=f"{block.block_id} must define cook() for Script DAT callbacks.",
                path=block.target_op,
            )
        )
    if "script_dat_cook_callback" in checks and block.target_param != "callbacks":
        issues.append(
            _issue(
                code="generated_python_target_not_callbacks_parameter",
                message=(
                    f"{block.block_id} must target the Script DAT callbacks parameter, "
                    "not the storage DAT text parameter."
                ),
                path=block.target_op,
            )
        )
    if "script_sop_cook_callback" in checks and not _has_python_function_named(block.code, "cook"):
        issues.append(
            _issue(
                code="missing_script_sop_cook_callback",
                message=f"{block.block_id} must define cook() for Script SOP callbacks.",
                path=block.target_op,
            )
        )
    if "script_sop_cook_callback" in checks and block.target_param != "callbacks":
        issues.append(
            _issue(
                code="generated_python_target_not_callbacks_parameter",
                message=(
                    f"{block.block_id} must target the Script SOP callbacks parameter, "
                    "not the storage DAT text parameter."
                ),
                path=block.target_op,
            )
        )
    if "dat_execute_table_change_callback" in checks:
        if re.search(r"\bdef\s+on(?:Cell|Row|Col|Column|Size)Change\s*\(", block.code):
            issues.append(
                _issue(
                    code="deprecated_dat_execute_callback",
                    message=f"{block.block_id} uses legacy DAT Execute row/column/cell/size callbacks.",
                    path=block.target_op,
                )
            )
        if not _has_python_function(block.code, "onTableChange", "dat"):
            issues.append(
                _issue(
                    code="missing_dat_execute_on_table_change",
                    message=f"{block.block_id} must define onTableChange(dat, prevDAT, info).",
                    path=block.target_op,
                )
            )
        if "callback_guard_present" in block.runtime_checks and not _has_dat_execute_callback_guard(
            block.code
        ):
            issues.append(
                _issue(
                    code="missing_dat_execute_callback_guard",
                    message=(
                        f"{block.block_id} must include a tdpilot_callback_guard sentinel "
                        "with try/finally reset."
                    ),
                    path=block.target_op,
                )
            )
        if _has_direct_watched_dat_write(block.code) and not _has_dat_execute_callback_guard(block.code):
            issues.append(
                _issue(
                    code="unguarded_dat_execute_watched_dat_write",
                    message=(
                        f"{block.block_id} writes to the watched DAT inside onTableChange() "
                        "without a tdpilot_callback_guard sentinel."
                    ),
                    path=block.target_op,
                )
            )
    if "chop_execute_value_change_callback" in checks and not _has_python_function_args(
        block.code,
        "onValueChange",
        ["channel", "sampleIndex", "val", "prev"],
    ):
        issues.append(
            _issue(
                code="invalid_chop_execute_callback_signature",
                message=(f"{block.block_id} must define onValueChange(channel, sampleIndex, val, prev)."),
                path=block.target_op,
            )
        )
    if "chop_execute_value_change_callback" in checks and block.target_param != "text":
        issues.append(
            _issue(
                code="generated_chop_execute_target_not_text_parameter",
                message=f"{block.block_id} must target the CHOP Execute DAT text content.",
                path=block.target_op,
            )
        )
    if "parameter_execute_value_change_callback" in checks and not _has_python_function_args(
        block.code,
        "onValueChange",
        ["par", "val", "prev"],
    ):
        issues.append(
            _issue(
                code="invalid_parameter_execute_callback_signature",
                message=f"{block.block_id} must define onValueChange(par, val, prev).",
                path=block.target_op,
            )
        )
    if (
        "parameter_execute_value_change_callback" in checks
        and "callback_guard_present" in block.runtime_checks
        and not _has_dat_execute_callback_guard(block.code)
    ):
        issues.append(
            _issue(
                code="missing_parameter_execute_callback_guard",
                message=(
                    f"{block.block_id} must include a tdpilot_callback_guard sentinel with try/finally reset."
                ),
                path=block.target_op,
            )
        )
    if (
        "parameter_execute_value_change_callback" in checks
        and _has_direct_watched_parameter_write(block.code)
        and not _has_dat_execute_callback_guard(block.code)
    ):
        issues.append(
            _issue(
                code="unguarded_parameter_execute_watched_parameter_write",
                message=(
                    f"{block.block_id} writes to the watched parameter inside a Parameter Execute callback "
                    "without a tdpilot_callback_guard sentinel."
                ),
                path=block.target_op,
            )
        )
    if "parameter_execute_value_change_callback" in checks and block.target_param != "text":
        issues.append(
            _issue(
                code="generated_parameter_execute_target_not_text_parameter",
                message=f"{block.block_id} must target the Parameter Execute DAT text content.",
                path=block.target_op,
            )
        )
    if "panel_execute_value_change_callback" in checks and not _has_python_function_args(
        block.code,
        "onValueChange",
        ["panelValue"],
    ):
        issues.append(
            _issue(
                code="invalid_panel_execute_callback_signature",
                message=f"{block.block_id} must define onValueChange(panelValue).",
                path=block.target_op,
            )
        )
    if (
        "panel_execute_value_change_callback" in checks
        and "callback_guard_present" in block.runtime_checks
        and not _has_dat_execute_callback_guard(block.code)
    ):
        issues.append(
            _issue(
                code="missing_panel_execute_callback_guard",
                message=(
                    f"{block.block_id} must include a tdpilot_callback_guard sentinel with try/finally reset."
                ),
                path=block.target_op,
            )
        )
    if "panel_execute_value_change_callback" in checks and block.target_param != "text":
        issues.append(
            _issue(
                code="generated_panel_execute_target_not_text_parameter",
                message=f"{block.block_id} must target the Panel Execute DAT text content.",
                path=block.target_op,
            )
        )
    if "pargroup_execute_value_change_callback" in checks and not _has_python_function_args(
        block.code,
        "onValueChange",
        ["curr", "prev"],
    ):
        issues.append(
            _issue(
                code="invalid_pargroup_execute_callback_signature",
                message=f"{block.block_id} must define onValueChange(curr, prev).",
                path=block.target_op,
            )
        )
    if (
        "pargroup_execute_value_change_callback" in checks
        and "callback_guard_present" in block.runtime_checks
        and not _has_dat_execute_callback_guard(block.code)
    ):
        issues.append(
            _issue(
                code="missing_pargroup_execute_callback_guard",
                message=(
                    f"{block.block_id} must include a tdpilot_callback_guard sentinel with try/finally reset."
                ),
                path=block.target_op,
            )
        )
    if (
        "pargroup_execute_value_change_callback" in checks
        and _has_direct_watched_pargroup_write(block.code)
        and not _has_dat_execute_callback_guard(block.code)
    ):
        issues.append(
            _issue(
                code="unguarded_pargroup_execute_watched_pargroup_write",
                message=(
                    f"{block.block_id} writes to the watched ParGroup inside a ParGroup Execute callback "
                    "without a tdpilot_callback_guard sentinel."
                ),
                path=block.target_op,
            )
        )
    if "pargroup_execute_value_change_callback" in checks and block.target_param != "text":
        issues.append(
            _issue(
                code="generated_pargroup_execute_target_not_text_parameter",
                message=f"{block.block_id} must target the ParGroup Execute DAT text content.",
                path=block.target_op,
            )
        )
    if "op_execute_state_change_callback" in checks and not _has_any_python_function_named(
        block.code,
        _OP_EXECUTE_CALLBACKS,
    ):
        issues.append(
            _issue(
                code="missing_op_execute_state_change_callback",
                message=f"{block.block_id} must define at least one documented OP Execute callback.",
                path=block.target_op,
            )
        )
    if "op_execute_state_change_callback" in checks and block.target_param != "text":
        issues.append(
            _issue(
                code="generated_op_execute_target_not_text_parameter",
                message=f"{block.block_id} must target the OP Execute DAT text content.",
                path=block.target_op,
            )
        )
    return issues


def _validate_glsl_block(block: GeneratedCodeBlock) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    checks = set(block.static_checks)
    if "glsl_no_version_line" in checks and re.search(r"^\s*#version\b", block.code, re.MULTILINE):
        issues.append(
            _issue(
                code="glsl_version_line_forbidden",
                message=f"{block.block_id} must not include a #version line; TouchDesigner inserts it.",
                path=block.target_op,
            )
        )
    if "glsl_top_uses_td_output_swizzle" in checks and "TDOutputSwizzle" not in block.code:
        issues.append(
            _issue(
                code="missing_td_output_swizzle",
                message=f"{block.block_id} must pass pixel shader output through TDOutputSwizzle().",
                path=block.target_op,
            )
        )
    if "glsl_top_declares_pixel_output" in checks and not re.search(
        r"\blayout\s*\(\s*location\s*=\s*0\s*\)\s*out\s+vec4\s+\w+\s*;",
        block.code,
    ):
        issues.append(
            _issue(
                code="missing_glsl_top_pixel_output_declaration",
                message=f"{block.block_id} must declare a GLSL TOP pixel output at layout(location = 0).",
                path=block.target_op,
            )
        )
    if "glsl_top_uses_td_output_swizzle" in checks and block.target_param != "pixeldat":
        issues.append(
            _issue(
                code="generated_glsl_target_not_shader_parameter",
                message=f"{block.block_id} must target the GLSL TOP pixeldat parameter, not the storage DAT.",
                path=block.target_op,
            )
        )
    if "glsl_mat_vertex_shader" in checks and block.target_param != "vdat":
        issues.append(
            _issue(
                code="generated_glsl_target_not_shader_parameter",
                message=f"{block.block_id} must target the GLSL MAT vdat parameter, not the storage DAT.",
                path=block.target_op,
            )
        )
    if "glsl_mat_vertex_shader" in checks and not (
        "TDWorldToProj" in block.code and "TDDeform" in block.code and "TDPos" in block.code
    ):
        issues.append(
            _issue(
                code="missing_glsl_mat_vertex_transform",
                message=(
                    f"{block.block_id} must transform material vertices with "
                    "TDWorldToProj(TDDeform(TDPos()))."
                ),
                path=block.target_op,
            )
        )
    if "glsl_mat_pixel_shader" in checks and block.target_param != "pdat":
        issues.append(
            _issue(
                code="generated_glsl_target_not_shader_parameter",
                message=f"{block.block_id} must target the GLSL MAT pdat parameter, not the storage DAT.",
                path=block.target_op,
            )
        )
    if "glsl_mat_pixel_shader" in checks and "TDOutputSwizzle" not in block.code:
        issues.append(
            _issue(
                code="missing_glsl_mat_output_swizzle",
                message=f"{block.block_id} must pass material color output through TDOutputSwizzle().",
                path=block.target_op,
            )
        )
    if "glsl_pop_bounds_guard" in checks and not (
        re.search(r"\bTDIndex\s*\(\s*\)", block.code) and re.search(r"\bTDNumElements\s*\(\s*\)", block.code)
    ):
        issues.append(
            _issue(
                code="missing_glsl_pop_bounds_guard",
                message=f"{block.block_id} must guard GLSL POP writes with TDIndex() and TDNumElements().",
                path=block.target_op,
            )
        )
    if "glsl_pop_bounds_guard" in checks and block.target_param != "computedat":
        issues.append(
            _issue(
                code="generated_glsl_target_not_shader_parameter",
                message=f"{block.block_id} must target the GLSL POP computedat parameter, not the storage DAT.",
                path=block.target_op,
            )
        )
    return issues


def _validate_plan_attachments(plan: PatchPlan, blocks: list[GeneratedCodeBlock]) -> list[ValidationIssue]:
    params_by_target = _params_by_target(plan)
    issues: list[ValidationIssue] = []
    for block in blocks:
        if not block.target_param:
            continue
        target_params = params_by_target.get(block.target_op, {})
        value = target_params.get(block.target_param)
        if block.target_param == "text" and block.target_op in block.source_refs and isinstance(value, str):
            continue
        if _value_references_any_source(value, block.source_refs):
            continue
        issues.append(
            _issue(
                code="generated_code_not_attached",
                message=(
                    f"{block.block_id} source DAT is not attached to {block.target_op} "
                    f"parameter {block.target_param}."
                ),
                path=block.target_op,
            )
        )
    return issues


def _params_by_target(plan: PatchPlan) -> dict[str, dict[str, Any]]:
    params: dict[str, dict[str, Any]] = {}
    for operation in plan.operations:
        if not operation.target:
            continue
        if operation.kind == "set_dat_content":
            payload = {"text": operation.args["text"]} if isinstance(operation.args.get("text"), str) else {}
        elif operation.kind == "set_params":
            payload = operation.args.get("params")
        else:
            continue
        if isinstance(payload, dict):
            params.setdefault(str(operation.target), {}).update(payload)
    return params


def _operation_text_payload(operation) -> str | None:
    if operation.kind == "set_dat_content" and isinstance(operation.args.get("text"), str):
        return operation.args["text"]
    params = operation.args.get("params")
    if isinstance(params, dict) and isinstance(params.get("text"), str):
        return params["text"]
    return None


async def _contract_errors(
    td_client,
    path: str,
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    if path in cache:
        return cache[path]
    payload = await td_client.request("node/errors", {"path": path, "recurse": False, "max_depth": 1})
    issues = _error_issue_list(payload)
    cache[path] = issues
    return issues


async def _contract_content(td_client, path: str, cache: dict[str, str]) -> str:
    if path in cache:
        return cache[path]
    payload = await td_client.request("node/content", {"path": path})
    text = _content_text(payload)
    cache[path] = text
    return text


async def _contract_pop_bounds(td_client, path: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if path in cache:
        return cache[path]
    payload = await td_client.request("pop/bounds", {"path": path})
    data = payload if isinstance(payload, dict) else {}
    cache[path] = data
    return data


async def _contract_topology_capacity(
    td_client, path: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if path in cache:
        return cache[path]
    payload = await td_client.request(
        "node/params",
        {"path": path, "names": list(_TOPOLOGY_CAPACITY_PARAMS)},
    )
    data = payload if isinstance(payload, dict) else {}
    cache[path] = data
    return data


def _runtime_evidence(
    contract: dict[str, Any],
    *,
    status: str,
    endpoint: str | None,
    issue_count: int,
) -> dict[str, Any]:
    return {
        "block_id": str(contract.get("block_id") or ""),
        "check_id": str(contract.get("check_id") or ""),
        "language": str(contract.get("language") or ""),
        "target_op": str(contract.get("target_op") or ""),
        "target_param": contract.get("target_param"),
        "expected_outputs": [str(item) for item in contract.get("expected_outputs", [])],
        "risk_flags": [str(item) for item in contract.get("risk_flags", [])],
        "official_sources": [str(item) for item in contract.get("official_sources", [])],
        "endpoint": endpoint,
        "status": status,
        "issue_count": issue_count,
    }


def _error_issue_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("issues", "errors", "warnings"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item if isinstance(item, dict) else {"message": str(item)} for item in value]
        if payload.get("ok") is False:
            return [{"message": str(payload.get("error") or payload.get("message") or "unknown TD error")}]
    if isinstance(payload, list):
        return [item if isinstance(item, dict) else {"message": str(item)} for item in payload]
    return []


def _first_issue_message(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "none"
    first = issues[0]
    return str(first.get("message") or first.get("error") or first.get("text") or first)


def _content_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "content", "data"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        rows = payload.get("rows")
        if isinstance(rows, list):
            return "\n".join(
                "\t".join(str(cell) for cell in row) if isinstance(row, list | tuple) else str(row)
                for row in rows
            )
    return ""


def _pop_bounds_contract_path(contract: dict[str, Any]) -> str:
    expected_outputs = [str(item) for item in contract.get("expected_outputs", []) if str(item)]
    for path in expected_outputs:
        lowered = path.lower()
        if lowered.endswith("pop") or "out_pop" in lowered or lowered.endswith("null_pop"):
            return path
    return str(contract.get("target_op") or "")


def _has_finite_pop_bounds(payload: dict[str, Any]) -> bool:
    bounds = payload.get("bounds") if isinstance(payload, dict) else None
    values: list[float] = []
    if isinstance(bounds, dict):
        for key in ("min", "max", "center", "size"):
            values.extend(_numeric_values(bounds.get(key)))
    else:
        values.extend(_numeric_values(bounds))
    if not values:
        for key in ("min", "max", "center", "size"):
            values.extend(_numeric_values(payload.get(key)))
    return bool(values) and all(math.isfinite(value) for value in values)


def _has_topology_capacity(payload: dict[str, Any]) -> bool:
    parameters = payload.get("parameters") if isinstance(payload, dict) else None
    values: list[float] = []
    if isinstance(parameters, dict):
        for name in _TOPOLOGY_CAPACITY_PARAMS:
            info = parameters.get(name)
            if isinstance(info, dict) and "value" in info:
                values.extend(_numeric_values(info.get("value")))
            else:
                values.extend(_numeric_values(info))
    else:
        values.extend(_numeric_values(payload))
    return bool(values) and all(math.isfinite(value) and value >= 0 for value in values)


def _numeric_values(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        values: list[float] = []
        for item in value.values():
            values.extend(_numeric_values(item))
        return values
    if isinstance(value, list | tuple):
        values: list[float] = []
        for item in value:
            values.extend(_numeric_values(item))
        return values
    return []


def _value_references_any_source(value: Any, source_refs: list[str]) -> bool:
    if isinstance(value, str):
        return any(source_ref and source_ref in value.split() for source_ref in source_refs)
    if isinstance(value, list | tuple | set):
        return any(_value_references_any_source(item, source_refs) for item in value)
    return False


def _has_python_function(code: str, name: str, first_arg: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != name:
            continue
        if not node.args.args:
            return False
        return node.args.args[0].arg == first_arg
    return False


def _has_python_function_named(code: str, name: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in ast.walk(tree))


def _has_any_python_function_named(code: str, names: set[str]) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name in names for node in ast.walk(tree))


def _has_python_function_args(code: str, name: str, args: list[str]) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return [arg.arg for arg in node.args.args] == args
    return False


def _has_dat_execute_callback_guard(code: str) -> bool:
    lowered = code.lower()
    return "tdpilot_callback_guard" in lowered and "try:" in code and "finally:" in code


def _has_callback_diagnostic_output(code: str, expected_outputs: list[str]) -> bool:
    candidates = {output.strip() for output in expected_outputs if output.strip()}
    candidates.update(output.rsplit("/", 1)[-1] for output in list(candidates) if "/" in output)
    if not candidates:
        return False
    if any(candidate in code for candidate in candidates):
        return True
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in candidates
        for node in ast.walk(tree)
    )


_WATCHED_DAT_MUTATORS = {
    "appendCol",
    "appendRow",
    "clear",
    "deleteCol",
    "deleteRow",
    "insertCol",
    "insertRow",
    "replaceCol",
    "replaceRow",
    "setSize",
}


_OP_EXECUTE_CALLBACKS = {
    "onPreCook",
    "onPostCook",
    "onDestroy",
    "onFlagChange",
    "onWireChange",
    "onNameChange",
    "onPathChange",
    "onUIChange",
    "onNumChildrenChange",
    "onChildRename",
    "onCurrentChildChange",
    "onExtensionChange",
}


def _has_direct_watched_dat_write(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "onTableChange" or not node.args.args:
            continue
        watched_arg = node.args.args[0].arg
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == watched_arg
                and child.func.attr in _WATCHED_DAT_MUTATORS
            ):
                return True
            if isinstance(child, ast.Assign | ast.AugAssign | ast.AnnAssign):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(_is_watched_dat_subscript(target, watched_arg) for target in targets):
                    return True
    return False


_PARAMETER_EXECUTE_CALLBACKS = {
    "onEnableChange",
    "onExportChange",
    "onExpressionChange",
    "onModeChange",
    "onPulse",
    "onValueChange",
}

_WATCHED_PARAMETER_MUTATOR_ATTRS = {
    "bindExpr",
    "enable",
    "expr",
    "exportOP",
    "mode",
    "val",
}

_PARGROUP_EXECUTE_CALLBACKS = {
    "onEnableChange",
    "onExportChange",
    "onExpressionChange",
    "onModeChange",
    "onPulse",
    "onValueChange",
}

_WATCHED_PARGROUP_MUTATOR_ATTRS = {
    "bindExpr",
    "bindRange",
    "clampMax",
    "clampMin",
    "default",
    "defaultBindExpr",
    "defaultExpr",
    "defaultMode",
    "enable",
    "enableExpr",
    "expr",
    "help",
    "label",
    "max",
    "menuIndex",
    "menuLabels",
    "menuNames",
    "menuSource",
    "min",
    "mode",
    "name",
    "normMax",
    "normMin",
    "normVal",
    "order",
    "page",
    "password",
    "readOnly",
    "size",
    "startSection",
    "val",
}

_WATCHED_PARGROUP_MUTATOR_METHODS = {
    "copy",
    "destroy",
    "reset",
}


def _has_direct_watched_parameter_write(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.FunctionDef)
            or node.name not in _PARAMETER_EXECUTE_CALLBACKS
            or not node.args.args
        ):
            continue
        watched_arg = node.args.args[0].arg
        for child in ast.walk(node):
            if isinstance(child, ast.Assign | ast.AugAssign | ast.AnnAssign):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(_is_watched_parameter_attr(target, watched_arg) for target in targets):
                    return True
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == watched_arg
                and child.func.attr == "pulse"
            ):
                return True
    return False


def _has_direct_watched_pargroup_write(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.FunctionDef)
            or node.name not in _PARGROUP_EXECUTE_CALLBACKS
            or not node.args.args
        ):
            continue
        watched_arg = node.args.args[0].arg
        for child in ast.walk(node):
            if isinstance(child, ast.Assign | ast.AugAssign | ast.AnnAssign):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(_is_watched_pargroup_attr(target, watched_arg) for target in targets):
                    return True
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == watched_arg
                and child.func.attr in _WATCHED_PARGROUP_MUTATOR_METHODS
            ):
                return True
    return False


def _is_watched_parameter_attr(target: ast.AST, watched_arg: str) -> bool:
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == watched_arg
        and target.attr in _WATCHED_PARAMETER_MUTATOR_ATTRS
    )


def _is_watched_pargroup_attr(target: ast.AST, watched_arg: str) -> bool:
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == watched_arg
        and target.attr in _WATCHED_PARGROUP_MUTATOR_ATTRS
    )


def _is_watched_dat_subscript(target: ast.AST, watched_arg: str) -> bool:
    return (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and target.value.id == watched_arg
    )


def _invalid_harness_source_records(
    *,
    required_languages: list[str],
    required_static_checks: list[str],
    required_runtime_checks: list[str],
) -> list[dict[str, str]]:
    required_source_ids = {
        *(f"language:{language}" for language in required_languages),
        *required_static_checks,
        *required_runtime_checks,
    }
    invalid: list[dict[str, str]] = []
    for check_id in sorted(required_source_ids):
        sources = _GENERATED_CODE_HARNESS_SOURCES.get(check_id)
        if not sources:
            invalid.append({"check_id": check_id, "source": "", "reason": "missing_official_source"})
            continue
        for source in sources:
            if not source.startswith("https://docs.derivative.ca/"):
                invalid.append({"check_id": check_id, "source": source, "reason": "non_derivative_source"})
    return invalid


def _issue(*, code: str, message: str, path: str | None = None) -> ValidationIssue:
    return ValidationIssue(severity="error", code=code, message=message, path=path, source="tdpilot-brain")


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple[str, str, str | None, str]] = set()
    deduped: list[ValidationIssue] = []
    for issue in issues:
        key = (issue.severity, issue.code, issue.path, issue.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


__all__ = [
    "extract_generated_code_blocks",
    "generated_code_harness_coverage_report",
    "generated_code_runtime_contracts",
    "patch_plan_generated_code_runtime_contracts",
    "validate_generated_code_runtime_contracts",
    "validate_generated_code_blocks",
    "validate_patch_plan_generated_code",
]
