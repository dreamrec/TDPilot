from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain import code_harness
from td_mcp.brain.code_harness import (
    extract_generated_code_blocks,
    validate_generated_code_blocks,
    validate_patch_plan_generated_code,
)
from td_mcp.brain.transaction import apply_transaction
from td_mcp.models.brain import GeneratedCodeBlock
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel


def _plan(operations: list[PatchOperation]) -> PatchPlan:
    return PatchPlan(
        intent="test generated code",
        target_root="/project1",
        source="operations",
        operations=operations,
        required_ops=[],
        risk_flags=[],
        undo_label="test generated code",
        validation_plan=ValidationPlan(target_root="/project1"),
    )


def _block(**updates) -> GeneratedCodeBlock:
    payload = {
        "block_id": "script_chop_callbacks",
        "language": "python",
        "target_op": "/project1/script",
        "target_param": "callbacks",
        "source_kind": "generated",
        "source_refs": ["/project1/script_callbacks"],
        "code": "def cook(scriptOp):\n    return",
        "static_checks": ["python_syntax", "script_chop_cook_signature"],
        "runtime_checks": ["cook_health"],
        "expected_outputs": ["/project1/script"],
        "risk_flags": ["validate-python-callback"],
        "official_sources": ["https://docs.derivative.ca/Script_CHOP"],
    }
    payload.update(updates)
    return GeneratedCodeBlock(**payload)


def test_python_generated_code_syntax_errors_are_reported():
    issues = validate_generated_code_blocks([_block(code="def cook(scriptOp):\n    return (")])

    assert any(issue.code == "python_syntax_error" for issue in issues)


def test_generated_code_harness_coverage_report_covers_supported_surface():
    assert hasattr(code_harness, "generated_code_harness_coverage_report")

    report = code_harness.generated_code_harness_coverage_report()

    assert report["ok"] is True
    assert report["missing_language_count"] == 0
    assert report["missing_static_check_count"] == 0
    assert report["missing_runtime_check_count"] == 0
    assert report["invalid_source_count"] == 0
    assert {"python", "glsl"}.issubset(set(report["covered_languages"]))
    assert {
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
    }.issubset(set(report["covered_static_checks"]))
    assert {
        "callback_guard_present",
        "compile_state",
        "diagnostic_output_present",
        "finite_pop_bounds",
        "topology_capacity",
    }.issubset(set(report["covered_runtime_checks"]))


def test_generated_code_harness_coverage_report_is_not_tautological(monkeypatch):
    """Coverage must be DISCOVERED from validator bodies, not copied from the
    required-constant. A declared-but-unwired check must surface as missing and
    fail the report — otherwise the gate proves nothing."""
    monkeypatch.setattr(
        code_harness,
        "_SUPPORTED_GENERATED_CODE_STATIC_CHECKS",
        code_harness._SUPPORTED_GENERATED_CODE_STATIC_CHECKS + ("totally_unwired_check",),
    )
    report = code_harness.generated_code_harness_coverage_report()
    assert report["ok"] is False
    assert "totally_unwired_check" in report["missing_static_checks"]
    assert "totally_unwired_check" not in report["covered_static_checks"]


def test_generated_code_runtime_contracts_are_explicit_and_source_free():
    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="pixel_shader",
                language="glsl",
                target_op="/project1/glsl",
                target_param="pixeldat",
                source_refs=["/project1/pixel_code"],
                code="layout(location = 0) out vec4 fragColor; void main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
                static_checks=["glsl_top_uses_td_output_swizzle"],
                runtime_checks=["compile_state"],
                expected_outputs=["/project1/out1"],
                risk_flags=["validate-glsl-compile-state"],
                official_sources=["https://docs.derivative.ca/GLSL_TOP"],
            ),
            _block(
                block_id="table_callback",
                language="python",
                target_op="/project1/table_exec",
                target_param="text",
                source_refs=["/project1/table_exec"],
                code="tdpilot_callback_guard = False\ndef onTableChange(dat, prevDAT, info):\n    global tdpilot_callback_guard\n    if tdpilot_callback_guard:\n        return\n    tdpilot_callback_guard = True\n    try:\n        return\n    finally:\n        tdpilot_callback_guard = False\n",
                static_checks=["python_syntax", "dat_execute_table_change_callback"],
                runtime_checks=["callback_guard_present", "diagnostic_output_present"],
                expected_outputs=["/project1/debug_callbacks"],
                risk_flags=["validate-python-callback"],
                official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
            ),
        ]
    )

    assert contracts == [
        {
            "block_id": "pixel_shader",
            "check_id": "compile_state",
            "language": "glsl",
            "target_op": "/project1/glsl",
            "target_param": "pixeldat",
            "source_refs": ["/project1/pixel_code"],
            "expected_outputs": ["/project1/out1"],
            "risk_flags": ["validate-glsl-compile-state"],
            "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
        },
        {
            "block_id": "table_callback",
            "check_id": "callback_guard_present",
            "language": "python",
            "target_op": "/project1/table_exec",
            "target_param": "text",
            "source_refs": ["/project1/table_exec"],
            "expected_outputs": ["/project1/debug_callbacks"],
            "risk_flags": ["validate-python-callback"],
            "official_sources": ["https://docs.derivative.ca/DAT_Execute_DAT"],
        },
        {
            "block_id": "table_callback",
            "check_id": "diagnostic_output_present",
            "language": "python",
            "target_op": "/project1/table_exec",
            "target_param": "text",
            "source_refs": ["/project1/table_exec"],
            "expected_outputs": ["/project1/debug_callbacks"],
            "risk_flags": ["validate-python-callback"],
            "official_sources": ["https://docs.derivative.ca/DAT_Execute_DAT"],
        },
    ]
    assert all("code" not in contract for contract in contracts)


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_reports_glsl_compile_errors_from_td_errors():
    class RuntimeClient:
        def __init__(self):
            self.calls = []

        async def request(self, endpoint, body=None):
            self.calls.append((endpoint, body or {}))
            return {"issues": [{"path": "/project1/glsl", "message": "shader compile failed"}]}

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="pixel_shader",
                language="glsl",
                target_op="/project1/glsl",
                target_param="pixeldat",
                source_refs=["/project1/pixel_code"],
                code="layout(location = 0) out vec4 fragColor; void main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
                static_checks=["glsl_top_uses_td_output_swizzle"],
                runtime_checks=["compile_state"],
                expected_outputs=["/project1/out1"],
                risk_flags=["validate-glsl-compile-state"],
                official_sources=["https://docs.derivative.ca/GLSL_TOP"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is False
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_fail"
    assert report["issues"][0].code == "generated_code_runtime_compile_state_error"


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_reports_compile_state_readback_errors():
    class RuntimeClient:
        async def request(self, endpoint, body=None):
            raise RuntimeError("node errors endpoint unavailable")

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="pixel_shader",
                language="glsl",
                target_op="/project1/glsl",
                target_param="pixeldat",
                source_refs=["/project1/pixel_code"],
                code="layout(location = 0) out vec4 fragColor; void main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
                static_checks=["glsl_top_uses_td_output_swizzle"],
                runtime_checks=["compile_state"],
                expected_outputs=["/project1/out1"],
                risk_flags=["validate-glsl-compile-state"],
                official_sources=["https://docs.derivative.ca/GLSL_TOP"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is False
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_fail"
    assert report["evidence"][0]["endpoint"] == "node/errors"
    assert report["issues"][0].code == "generated_code_runtime_compile_state_readback_error"
    assert report["issues"][0].path == "/project1/glsl"


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_reads_callback_contract_without_source_leak():
    class RuntimeClient:
        def __init__(self):
            self.calls = []

        async def request(self, endpoint, body=None):
            self.calls.append((endpoint, body or {}))
            return {
                "text": (
                    "tdpilot_callback_guard = False\n"
                    "def onTableChange(dat, prevDAT, info):\n"
                    "    global tdpilot_callback_guard\n"
                    "    if tdpilot_callback_guard:\n"
                    "        return\n"
                    "    tdpilot_callback_guard = True\n"
                    "    try:\n"
                    "        op('debug_callbacks').appendRow(['changed'])\n"
                    "    finally:\n"
                    "        tdpilot_callback_guard = False\n"
                )
            }

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="table_callback",
                language="python",
                target_op="/project1/table_exec",
                target_param="text",
                source_refs=["/project1/table_exec"],
                code="tdpilot_callback_guard = False\ndef onTableChange(dat, prevDAT, info):\n    return\n",
                static_checks=["python_syntax", "dat_execute_table_change_callback"],
                runtime_checks=["callback_guard_present", "diagnostic_output_present"],
                expected_outputs=["/project1/debug_callbacks"],
                risk_flags=["validate-python-callback"],
                official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is True
    assert report["checked_contract_count"] == 2
    assert {item["status"] for item in report["evidence"]} == {"runtime_pass"}
    assert all(
        "code" not in item and "text" not in item and "content" not in item for item in report["evidence"]
    )


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_reports_callback_content_readback_errors():
    class RuntimeClient:
        async def request(self, endpoint, body=None):
            raise RuntimeError("node content endpoint unavailable")

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="table_callback",
                language="python",
                target_op="/project1/table_exec",
                target_param="text",
                source_refs=["/project1/table_exec"],
                code="tdpilot_callback_guard = False\ndef onTableChange(dat, prevDAT, info):\n    return\n",
                static_checks=["python_syntax", "dat_execute_table_change_callback"],
                runtime_checks=["callback_guard_present"],
                expected_outputs=["/project1/debug_callbacks"],
                risk_flags=["validate-python-callback"],
                official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is False
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_fail"
    assert report["evidence"][0]["endpoint"] == "node/content"
    assert "content" not in report["evidence"][0]
    assert report["issues"][0].code == "generated_code_runtime_callback_content_readback_error"
    assert report["issues"][0].path == "/project1/table_exec"


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_reports_nonfinite_pop_bounds():
    class RuntimeClient:
        def __init__(self):
            self.calls = []

        async def request(self, endpoint, body=None):
            self.calls.append((endpoint, body or {}))
            return {
                "bounds": {
                    "min": [-1.0, float("nan"), 0.0],
                    "max": [1.0, 2.0, 3.0],
                }
            }

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="pop_compute",
                language="glsl",
                target_op="/project1/out_pop",
                target_param="computedat",
                source_refs=["/project1/pop_code"],
                code=(
                    "void main() {\n"
                    "    uint idx = TDIndex();\n"
                    "    if (idx >= TDNumElements()) { return; }\n"
                    "}\n"
                ),
                static_checks=["glsl_pop_bounds_guard"],
                runtime_checks=["finite_pop_bounds"],
                expected_outputs=["/project1/out_pop"],
                risk_flags=["validate-finite-pop-bounds"],
                official_sources=["https://docs.derivative.ca/POP"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is False
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_fail"
    assert report["evidence"][0]["endpoint"] == "pop/bounds"
    assert report["issues"][0].code == "generated_code_runtime_finite_pop_bounds_error"
    assert report["issues"][0].path == "/project1/out_pop"


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_reports_pop_bounds_readback_errors():
    class RuntimeClient:
        async def request(self, endpoint, body=None):
            raise RuntimeError("pop bounds endpoint unavailable")

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="pop_compute",
                language="glsl",
                target_op="/project1/out_pop",
                target_param="computedat",
                source_refs=["/project1/pop_code"],
                code=(
                    "void main() {\n"
                    "    uint idx = TDIndex();\n"
                    "    if (idx >= TDNumElements()) { return; }\n"
                    "}\n"
                ),
                static_checks=["glsl_pop_bounds_guard"],
                runtime_checks=["finite_pop_bounds"],
                expected_outputs=["/project1/out_pop"],
                risk_flags=["validate-finite-pop-bounds"],
                official_sources=["https://docs.derivative.ca/POP"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is False
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_fail"
    assert report["evidence"][0]["endpoint"] == "pop/bounds"
    assert report["issues"][0].code == "generated_code_runtime_finite_pop_bounds_readback_error"
    assert report["issues"][0].path == "/project1/out_pop"


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_checks_topology_capacity_params():
    class RuntimeClient:
        def __init__(self):
            self.calls = []

        async def request(self, endpoint, body=None):
            self.calls.append((endpoint, body or {}))
            return {
                "parameters": {
                    "maxpoints": {"value": 4096},
                    "maxtriangles": {"value": 8192},
                    "maxquads": {"value": 0},
                }
            }

    client = RuntimeClient()
    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="glsl_advanced_pop_topology_shader",
                language="glsl",
                target_op="/project1/glsladvanced",
                target_param="computedat",
                source_refs=["/project1/advanced_code"],
                code=(
                    "void main() {\n"
                    "    uint idx = TDIndex();\n"
                    "    if (idx >= TDNumElements()) { return; }\n"
                    "}\n"
                ),
                static_checks=["glsl_pop_bounds_guard"],
                runtime_checks=["topology_capacity"],
                expected_outputs=["/project1/out_pop"],
                risk_flags=["validate-glsl-compile-state", "validate-finite-pop-bounds"],
                official_sources=["https://docs.derivative.ca/GLSL_Advanced_POP"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(client, contracts)

    assert report["ok"] is True
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_pass"
    assert report["evidence"][0]["endpoint"] == "node/params"
    assert "parameters" not in report["evidence"][0]
    assert client.calls == [
        (
            "node/params",
            {
                "path": "/project1/glsladvanced",
                "names": [
                    "maxlines",
                    "maxlinestrips",
                    "maxlsverts",
                    "maxpointprims",
                    "maxpoints",
                    "maxquads",
                    "maxtriangles",
                ],
            },
        )
    ]


@pytest.mark.asyncio
async def test_generated_code_runtime_validation_blocks_unsupported_runtime_checks():
    class RuntimeClient:
        async def request(self, endpoint, body=None):
            return {}

    contracts = code_harness.generated_code_runtime_contracts(
        [
            _block(
                block_id="experimental_shader",
                language="glsl",
                target_op="/project1/experimental",
                target_param="computedat",
                source_refs=["/project1/experimental_code"],
                code="void main() { return; }\n",
                static_checks=["glsl_no_version_line"],
                runtime_checks=["future_runtime_probe"],
                expected_outputs=["/project1/out1"],
                risk_flags=["validate-experimental-runtime"],
                official_sources=["https://docs.derivative.ca/GLSL_TOP"],
            )
        ]
    )

    report = await code_harness.validate_generated_code_runtime_contracts(RuntimeClient(), contracts)

    assert report["ok"] is False
    assert report["checked_contract_count"] == 1
    assert report["evidence"][0]["status"] == "runtime_fail"
    assert report["evidence"][0]["endpoint"] is None
    assert report["issues"][0].code == "generated_code_runtime_check_unsupported"
    assert report["issues"][0].path == "/project1/experimental"


def test_script_chop_requires_cook_callback_signature():
    issues = validate_generated_code_blocks([_block(code="def setupParameters(scriptOp):\n    return")])

    assert any(issue.code == "missing_script_chop_cook_callback" for issue in issues)


def test_script_chop_generated_code_metadata_must_target_callbacks_param():
    block = _block(
        target_op="/project1/script_chop_callbacks",
        target_param="text",
        source_refs=["/project1/script_chop_callbacks"],
        code="def cook(scriptOp):\n    return",
        static_checks=["python_syntax", "script_chop_cook_signature"],
        official_sources=["https://docs.derivative.ca/Script_CHOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_python_target_not_callbacks_parameter" for issue in issues)


def test_script_top_requires_copy_numpy_array_output_write():
    block = _block(
        block_id="script_top_callbacks",
        target_op="/project1/script_top",
        target_param="callbacks",
        source_refs=["/project1/script_top_callbacks"],
        code="def cook(scriptOp):\n    return",
        static_checks=["python_syntax", "script_top_uses_copy_numpy_array"],
        runtime_checks=["cook_health", "top_output_present"],
        expected_outputs=["/project1/script_top"],
        official_sources=["https://docs.derivative.ca/Script_TOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_script_top_copy_numpy_array" for issue in issues)


def test_script_top_generated_code_metadata_must_target_callbacks_param():
    block = _block(
        block_id="script_top_callbacks",
        target_op="/project1/script_top_callbacks",
        target_param="text",
        source_refs=["/project1/script_top_callbacks"],
        code=(
            "import numpy as np\n\n"
            "def cook(scriptOp):\n"
            "    pixels = np.zeros((16, 16, 4), dtype=np.float32)\n"
            "    scriptOp.copyNumpyArray(pixels)\n"
        ),
        static_checks=["python_syntax", "script_top_uses_copy_numpy_array"],
        runtime_checks=["cook_health", "top_output_present"],
        expected_outputs=["/project1/script_top"],
        official_sources=["https://docs.derivative.ca/Script_TOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_python_target_not_callbacks_parameter" for issue in issues)


def test_script_dat_requires_cook_callback():
    block = _block(
        block_id="script_dat_callbacks",
        target_op="/project1/script_dat",
        target_param="callbacks",
        source_refs=["/project1/script_dat_callbacks"],
        code="def setupParameters(scriptOp):\n    return",
        static_checks=["python_syntax", "script_dat_cook_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/script_dat"],
        official_sources=["https://docs.derivative.ca/Script_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_script_dat_cook_callback" for issue in issues)


def test_script_dat_generated_code_metadata_must_target_callbacks_param():
    block = _block(
        block_id="script_dat_callbacks",
        target_op="/project1/script_dat_callbacks",
        target_param="text",
        source_refs=["/project1/script_dat_callbacks"],
        code="def cook(scriptOp):\n    return",
        static_checks=["python_syntax", "script_dat_cook_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/script_dat"],
        official_sources=["https://docs.derivative.ca/Script_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_python_target_not_callbacks_parameter" for issue in issues)


def test_script_sop_requires_cook_callback():
    block = _block(
        block_id="script_sop_callbacks",
        target_op="/project1/script_sop",
        target_param="callbacks",
        source_refs=["/project1/script_sop_callbacks"],
        code="def setupParameters(scriptOp):\n    return",
        static_checks=["python_syntax", "script_sop_cook_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/script_sop"],
        official_sources=["https://docs.derivative.ca/Script_SOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_script_sop_cook_callback" for issue in issues)


def test_script_sop_generated_code_metadata_must_target_callbacks_param():
    block = _block(
        block_id="script_sop_callbacks",
        target_op="/project1/script_sop_callbacks",
        target_param="text",
        source_refs=["/project1/script_sop_callbacks"],
        code="def cook(scriptOp):\n    return",
        static_checks=["python_syntax", "script_sop_cook_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/script_sop"],
        official_sources=["https://docs.derivative.ca/Script_SOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_python_target_not_callbacks_parameter" for issue in issues)


def test_dat_execute_prefers_modern_table_change_callback_and_flags_legacy_callbacks():
    block = _block(
        block_id="dat_execute_callbacks",
        target_op="/project1/watch_exec",
        target_param="callbacks",
        source_refs=["/project1/watch_callbacks"],
        code="def onCellChange(dat, cells, prev):\n    return",
        static_checks=["python_syntax", "dat_execute_table_change_callback"],
        official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "deprecated_dat_execute_callback" for issue in issues)
    assert any(issue.code == "missing_dat_execute_on_table_change" for issue in issues)


def test_dat_execute_callback_guard_check_rejects_unguarded_callback_source():
    block = _block(
        block_id="dat_execute_callbacks",
        target_op="/project1/watch_exec",
        target_param="callbacks",
        source_refs=["/project1/watch_callbacks"],
        code="def onTableChange(dat, prevDAT, info):\n    dat.appendRow(['unsafe'])\n    return",
        static_checks=["python_syntax", "dat_execute_table_change_callback"],
        runtime_checks=["callback_guard_present"],
        official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_dat_execute_callback_guard" for issue in issues)


def test_dat_execute_direct_watched_dat_writes_require_callback_guard():
    block = _block(
        block_id="dat_execute_callbacks",
        target_op="/project1/watch_exec",
        target_param="callbacks",
        source_refs=["/project1/watch_callbacks"],
        code="def onTableChange(dat, prevDAT, info):\n    dat.appendRow(['unsafe'])\n    return",
        static_checks=["python_syntax", "dat_execute_table_change_callback"],
        runtime_checks=["cook_health"],
        official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "unguarded_dat_execute_watched_dat_write" for issue in issues)


def test_generated_callback_diagnostic_runtime_check_requires_output_write():
    block = _block(
        block_id="dat_execute_callbacks",
        target_op="/project1/watch_exec",
        target_param="text",
        source_refs=["/project1/watch_exec"],
        code=(
            "tdpilot_callback_guard = False\n\n"
            "def onTableChange(dat, prevDAT, info):\n"
            "    global tdpilot_callback_guard\n"
            "    if tdpilot_callback_guard:\n"
            "        return\n"
            "    tdpilot_callback_guard = True\n"
            "    try:\n"
            "        return\n"
            "    finally:\n"
            "        tdpilot_callback_guard = False\n"
        ),
        static_checks=["python_syntax", "dat_execute_table_change_callback"],
        runtime_checks=["callback_guard_present", "diagnostic_output_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_callback_diagnostic_output" for issue in issues)


def test_chop_execute_value_change_callback_requires_official_signature():
    block = _block(
        block_id="chop_execute_callbacks",
        target_op="/project1/chop_exec",
        target_param="text",
        source_refs=["/project1/chop_exec"],
        code="def onValueChange(channel, val):\n    return",
        static_checks=["python_syntax", "chop_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/out_chop"],
        official_sources=[
            "https://docs.derivative.ca/CHOP_Execute_DAT",
            "https://docs.derivative.ca/ChopexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "invalid_chop_execute_callback_signature" for issue in issues)


def test_chop_execute_value_change_callback_targets_dat_text():
    block = _block(
        block_id="chop_execute_callbacks",
        target_op="/project1/chop_exec",
        target_param="callbacks",
        source_refs=["/project1/chop_exec"],
        code="def onValueChange(channel, sampleIndex, val, prev):\n    return",
        static_checks=["python_syntax", "chop_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/out_chop"],
        official_sources=[
            "https://docs.derivative.ca/CHOP_Execute_DAT",
            "https://docs.derivative.ca/ChopexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_chop_execute_target_not_text_parameter" for issue in issues)


def test_parameter_execute_value_change_callback_requires_official_signature():
    block = _block(
        block_id="parameter_execute_callbacks",
        target_op="/project1/parameter_exec",
        target_param="text",
        source_refs=["/project1/parameter_exec"],
        code="def onValueChange(par, val):\n    return",
        static_checks=["python_syntax", "parameter_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Parameter_Execute_DAT",
            "https://docs.derivative.ca/ParameterexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "invalid_parameter_execute_callback_signature" for issue in issues)


def test_parameter_execute_direct_watched_parameter_writes_require_callback_guard():
    block = _block(
        block_id="parameter_execute_callbacks",
        target_op="/project1/parameter_exec",
        target_param="text",
        source_refs=["/project1/parameter_exec"],
        code="def onValueChange(par, val, prev):\n    par.val = val\n    return",
        static_checks=["python_syntax", "parameter_execute_value_change_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Parameter_Execute_DAT",
            "https://docs.derivative.ca/ParameterexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "unguarded_parameter_execute_watched_parameter_write" for issue in issues)


def test_parameter_execute_callback_guard_check_rejects_unguarded_callback_source():
    block = _block(
        block_id="parameter_execute_callbacks",
        target_op="/project1/parameter_exec",
        target_param="text",
        source_refs=["/project1/parameter_exec"],
        code="def onValueChange(par, val, prev):\n    return",
        static_checks=["python_syntax", "parameter_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Parameter_Execute_DAT",
            "https://docs.derivative.ca/ParameterexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_parameter_execute_callback_guard" for issue in issues)


def test_parameter_execute_value_change_callback_targets_dat_text():
    block = _block(
        block_id="parameter_execute_callbacks",
        target_op="/project1/parameter_exec",
        target_param="callbacks",
        source_refs=["/project1/parameter_exec"],
        code="def onValueChange(par, val, prev):\n    return",
        static_checks=["python_syntax", "parameter_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Parameter_Execute_DAT",
            "https://docs.derivative.ca/ParameterexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_parameter_execute_target_not_text_parameter" for issue in issues)


def test_panel_execute_value_change_callback_requires_official_signature():
    block = _block(
        block_id="panel_execute_callbacks",
        target_op="/project1/panel_exec",
        target_param="text",
        source_refs=["/project1/panel_exec"],
        code="def onValueChange(panelValue, extra):\n    return",
        static_checks=["python_syntax", "panel_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Panel_Execute_DAT",
            "https://docs.derivative.ca/PanelexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "invalid_panel_execute_callback_signature" for issue in issues)


def test_panel_execute_value_change_callback_targets_dat_text():
    block = _block(
        block_id="panel_execute_callbacks",
        target_op="/project1/panel_exec",
        target_param="callbacks",
        source_refs=["/project1/panel_exec"],
        code="def onValueChange(panelValue):\n    return",
        static_checks=["python_syntax", "panel_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Panel_Execute_DAT",
            "https://docs.derivative.ca/PanelexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_panel_execute_target_not_text_parameter" for issue in issues)


def test_panel_execute_callback_guard_check_rejects_unguarded_callback_source():
    block = _block(
        block_id="panel_execute_callbacks",
        target_op="/project1/panel_exec",
        target_param="text",
        source_refs=["/project1/panel_exec"],
        code="def onValueChange(panelValue):\n    return",
        static_checks=["python_syntax", "panel_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/Panel_Execute_DAT",
            "https://docs.derivative.ca/PanelexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_panel_execute_callback_guard" for issue in issues)


def test_pargroup_execute_value_change_callback_requires_official_signature():
    block = _block(
        block_id="pargroup_execute_callbacks",
        target_op="/project1/pargroup_exec",
        target_param="text",
        source_refs=["/project1/pargroup_exec"],
        code="def onValueChange(parGroup):\n    return",
        static_checks=["python_syntax", "pargroup_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/ParGroup_Execute_DAT",
            "https://docs.derivative.ca/PargroupexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "invalid_pargroup_execute_callback_signature" for issue in issues)


def test_pargroup_execute_value_change_callback_targets_dat_text():
    block = _block(
        block_id="pargroup_execute_callbacks",
        target_op="/project1/pargroup_exec",
        target_param="callbacks",
        source_refs=["/project1/pargroup_exec"],
        code="def onValueChange(curr, prev):\n    return",
        static_checks=["python_syntax", "pargroup_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/ParGroup_Execute_DAT",
            "https://docs.derivative.ca/PargroupexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_pargroup_execute_target_not_text_parameter" for issue in issues)


def test_pargroup_execute_callback_guard_check_rejects_unguarded_callback_source():
    block = _block(
        block_id="pargroup_execute_callbacks",
        target_op="/project1/pargroup_exec",
        target_param="text",
        source_refs=["/project1/pargroup_exec"],
        code="def onValueChange(curr, prev):\n    return",
        static_checks=["python_syntax", "pargroup_execute_value_change_callback"],
        runtime_checks=["callback_guard_present"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/ParGroup_Execute_DAT",
            "https://docs.derivative.ca/PargroupexecuteDAT_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_pargroup_execute_callback_guard" for issue in issues)


def test_pargroup_execute_direct_watched_pargroup_writes_require_callback_guard():
    block = _block(
        block_id="pargroup_execute_callbacks",
        target_op="/project1/pargroup_exec",
        target_param="text",
        source_refs=["/project1/pargroup_exec"],
        code="def onValueChange(curr, prev):\n    curr.val = prev\n    return",
        static_checks=["python_syntax", "pargroup_execute_value_change_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=[
            "https://docs.derivative.ca/ParGroup_Execute_DAT",
            "https://docs.derivative.ca/ParGroup_Class",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "unguarded_pargroup_execute_watched_pargroup_write" for issue in issues)


def test_op_execute_state_change_callback_requires_documented_callback_name():
    block = _block(
        block_id="op_execute_callbacks",
        target_op="/project1/op_exec",
        target_param="text",
        source_refs=["/project1/op_exec"],
        code="def onValueChange(channel, sampleIndex, val, prev):\n    return",
        static_checks=["python_syntax", "op_execute_state_change_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=["https://docs.derivative.ca/OP_Execute_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_op_execute_state_change_callback" for issue in issues)


def test_op_execute_state_change_callback_targets_dat_text():
    block = _block(
        block_id="op_execute_callbacks",
        target_op="/project1/op_exec",
        target_param="callbacks",
        source_refs=["/project1/op_exec"],
        code="def onPostCook(op):\n    return",
        static_checks=["python_syntax", "op_execute_state_change_callback"],
        runtime_checks=["cook_health"],
        expected_outputs=["/project1/debug_callbacks"],
        official_sources=["https://docs.derivative.ca/OP_Execute_DAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_op_execute_target_not_text_parameter" for issue in issues)


def test_glsl_top_pixel_shader_rejects_version_line_and_missing_td_output_swizzle():
    block = _block(
        block_id="pixel_shader",
        language="glsl",
        target_op="/project1/glsl",
        target_param="pixeldat",
        source_refs=["/project1/pixel_code"],
        code="#version 460\nlayout(location = 0) out vec4 fragColor;\nvoid main(){ fragColor = vec4(1.0); }",
        static_checks=["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
        runtime_checks=["compile_state"],
        official_sources=["https://docs.derivative.ca/GLSL_TOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert {issue.code for issue in issues} >= {"glsl_version_line_forbidden", "missing_td_output_swizzle"}


def test_glsl_top_pixel_shader_requires_explicit_pixel_output_declaration():
    block = _block(
        block_id="pixel_shader",
        language="glsl",
        target_op="/project1/glsl",
        target_param="pixeldat",
        source_refs=["/project1/pixel_code"],
        code="void main(){ vec4 color = vec4(1.0); fragColor = TDOutputSwizzle(color); }",
        static_checks=[
            "glsl_no_version_line",
            "glsl_top_declares_pixel_output",
            "glsl_top_uses_td_output_swizzle",
        ],
        runtime_checks=["compile_state"],
        expected_outputs=["/project1/out1"],
        official_sources=["https://docs.derivative.ca/Write_a_GLSL_TOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_glsl_top_pixel_output_declaration" for issue in issues)


def test_glsl_top_generated_code_metadata_must_target_shader_parameter_not_text_dat():
    block = _block(
        block_id="pixel_shader",
        language="glsl",
        target_op="/project1/pixel_code",
        target_param="text",
        source_refs=["/project1/pixel_code"],
        code="layout(location = 0) out vec4 fragColor;\nvoid main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
        static_checks=["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
        runtime_checks=["compile_state"],
        official_sources=["https://docs.derivative.ca/GLSL_TOP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_glsl_target_not_shader_parameter" for issue in issues)


def test_glsl_mat_generated_code_metadata_must_target_material_shader_params():
    block = _block(
        block_id="material_vertex_shader",
        language="glsl",
        target_op="/project1/vertex_code",
        target_param="text",
        source_refs=["/project1/vertex_code"],
        code="void TDVertex(){}",
        static_checks=["glsl_no_version_line", "glsl_mat_vertex_shader"],
        runtime_checks=["compile_state"],
        official_sources=["https://docs.derivative.ca/GLSL_MAT"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_glsl_target_not_shader_parameter" for issue in issues)


def test_glsl_mat_vertex_shader_requires_touchdesigner_deform_transform():
    block = _block(
        block_id="material_vertex_shader",
        language="glsl",
        target_op="/project1/glsl",
        target_param="vdat",
        source_refs=["/project1/vertex_code"],
        code="void TDVertex(){ gl_Position = TDWorldToProj(vec4(P, 1.0)); }",
        static_checks=["glsl_no_version_line", "glsl_mat_vertex_shader"],
        runtime_checks=["compile_state"],
        expected_outputs=["/project1/out1"],
        official_sources=[
            "https://docs.derivative.ca/GLSL_MAT",
            "https://docs.derivative.ca/Write_a_GLSL_MAT",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_glsl_mat_vertex_transform" for issue in issues)


def test_glsl_mat_pixel_shader_requires_touchdesigner_output_swizzle():
    block = _block(
        block_id="material_pixel_shader",
        language="glsl",
        target_op="/project1/glsl",
        target_param="pdat",
        source_refs=["/project1/pixel_code"],
        code="out vec4 fragColor;\nvoid TDFragment(){ fragColor = vec4(1.0); }",
        static_checks=["glsl_no_version_line", "glsl_mat_pixel_shader"],
        runtime_checks=["compile_state"],
        expected_outputs=["/project1/out1"],
        official_sources=[
            "https://docs.derivative.ca/GLSL_MAT",
            "https://docs.derivative.ca/Write_a_GLSL_MAT",
        ],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_glsl_mat_output_swizzle" for issue in issues)


def test_glsl_pop_compute_shader_requires_bounds_guard():
    block = _block(
        block_id="pop_compute",
        language="glsl",
        target_op="/project1/pop_shader",
        target_param="computedat",
        source_refs=["/project1/pop_code"],
        code="void main(){ P = vec3(0.0); }",
        static_checks=["glsl_pop_bounds_guard"],
        runtime_checks=["compile_state", "finite_pop_bounds"],
        official_sources=["https://docs.derivative.ca/Write_a_GLSL_POP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "missing_glsl_pop_bounds_guard" for issue in issues)


def test_glsl_pop_generated_code_metadata_must_target_compute_shader_param():
    block = _block(
        block_id="pop_compute",
        language="glsl",
        target_op="/project1/pop_code",
        target_param="text",
        source_refs=["/project1/pop_code"],
        code=("void main() {\n    uint idx = TDIndex();\n    if (idx >= TDNumElements()) { return; }\n}\n"),
        static_checks=["glsl_pop_bounds_guard"],
        runtime_checks=["compile_state", "finite_pop_bounds"],
        official_sources=["https://docs.derivative.ca/Write_a_GLSL_POP"],
    )

    issues = validate_generated_code_blocks([block])

    assert any(issue.code == "generated_glsl_target_not_shader_parameter" for issue in issues)


def test_patch_plan_generated_code_extraction_and_glsl_attachment_validation():
    plan = _plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "textDAT", "name": "pixel_code"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/pixel_code",
                args={
                    "params": {
                        "text": "layout(location = 0) out vec4 fragColor;\nvoid main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }"
                    },
                    "generated_code": {
                        "block_id": "pixel_shader",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "source_kind": "generated",
                        "source_refs": ["/project1/pixel_code"],
                        "static_checks": ["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
                        "runtime_checks": ["compile_state"],
                        "expected_outputs": ["/project1/out1"],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                    },
                },
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glsl", "name": "glsl"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/glsl",
                args={"params": {"pixeldat": "/project1/pixel_code"}},
            ),
        ]
    )

    blocks = extract_generated_code_blocks(plan)
    issues = validate_patch_plan_generated_code(plan)

    assert len(blocks) == 1
    assert blocks[0].code.startswith("layout(location = 0)")
    assert issues == []


def test_patch_plan_generated_code_extraction_from_dat_content_write():
    plan = _plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "datexecuteDAT", "name": "table_change_exec"},
            ),
            PatchOperation(
                kind="set_dat_content",
                target="/project1/table_change_exec",
                args={
                    "text": (
                        "tdpilot_callback_guard = False\n\n"
                        "def onTableChange(dat, prevDAT, info):\n"
                        "    global tdpilot_callback_guard\n"
                        "    if tdpilot_callback_guard:\n"
                        "        return\n"
                        "    tdpilot_callback_guard = True\n"
                        "    try:\n"
                        "        return\n"
                        "    finally:\n"
                        "        tdpilot_callback_guard = False\n"
                    ),
                    "generated_code": {
                        "block_id": "dat_execute_table_change_callback",
                        "language": "python",
                        "target_op": "/project1/table_change_exec",
                        "target_param": "text",
                        "source_kind": "generated",
                        "source_refs": ["/project1/table_change_exec"],
                        "static_checks": ["python_syntax", "dat_execute_table_change_callback"],
                        "runtime_checks": ["callback_guard_present"],
                        "expected_outputs": ["/project1/out_dat"],
                        "risk_flags": ["validate-python-callback"],
                        "official_sources": ["https://docs.derivative.ca/DAT_Execute_DAT"],
                    },
                },
            ),
        ]
    )

    blocks = extract_generated_code_blocks(plan)
    issues = validate_patch_plan_generated_code(plan)

    assert len(blocks) == 1
    assert "def onTableChange" in blocks[0].code
    assert "tdpilot_callback_guard" in blocks[0].code
    assert issues == []


def test_patch_plan_reports_unattached_generated_glsl_dat():
    plan = _plan(
        [
            PatchOperation(
                kind="set_params",
                target="/project1/pixel_code",
                args={
                    "params": {"text": "void main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }"},
                    "generated_code": {
                        "block_id": "pixel_shader",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "source_kind": "generated",
                        "source_refs": ["/project1/pixel_code"],
                        "static_checks": ["glsl_top_uses_td_output_swizzle"],
                        "runtime_checks": ["compile_state"],
                        "expected_outputs": ["/project1/out1"],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                    },
                },
            )
        ]
    )

    issues = validate_patch_plan_generated_code(plan)

    assert any(issue.code == "generated_code_not_attached" for issue in issues)


def test_patch_plan_generated_code_metadata_requires_runtime_checks_and_expected_outputs():
    plan = _plan(
        [
            PatchOperation(
                kind="set_params",
                target="/project1/pixel_code",
                args={
                    "params": {"text": "void main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }"},
                    "generated_code": {
                        "block_id": "syntax_only_shader",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "source_kind": "generated",
                        "source_refs": ["/project1/pixel_code"],
                        "static_checks": ["glsl_top_uses_td_output_swizzle"],
                        "runtime_checks": [],
                        "expected_outputs": [],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                    },
                },
            )
        ]
    )

    issues = validate_patch_plan_generated_code(plan)

    assert any(issue.code == "invalid_generated_code_metadata" for issue in issues)
    assert "runtime check" in issues[0].message


@pytest.mark.asyncio
async def test_transaction_preflight_blocks_invalid_generated_code_before_preview():
    plan = _plan(
        [
            PatchOperation(
                kind="set_params",
                target="/project1/pixel_code",
                args={
                    "params": {"text": "#version 460\nvoid main(){ fragColor = vec4(1.0); }"},
                    "generated_code": {
                        "block_id": "pixel_shader",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "source_kind": "generated",
                        "source_refs": ["/project1/pixel_code"],
                        "static_checks": ["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
                        "runtime_checks": ["compile_state"],
                        "expected_outputs": ["/project1/out1"],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                    },
                },
            )
        ]
    )
    client = FakeTDClient(scripted={"project/lifecycle": {"snapshot_id": "unused"}})

    result = await apply_transaction(client, plan, sentinel=UndoBlockSentinel(), concept_profile="glsl")

    assert result.status == "blocked"
    assert result.validation_report is not None
    assert result.validation_report.checks == ["generated_code_static_checks"]
    assert any(issue.code == "glsl_version_line_forbidden" for issue in result.validation_report.issues)
    assert not any(call[0] == "node/params/set" for call in client.calls)
    assert not any(call[0] == "patch/preview" for call in client.calls)
