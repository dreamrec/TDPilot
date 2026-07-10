from __future__ import annotations

import pytest

from td_mcp.brain.validation_engine import to_validation_report_v2, validate_contract
from td_mcp.models.build import ValidationAssertion, ValidationContract


class FakeTDClient:
    def __init__(self, scripted: dict | None = None) -> None:
        self.scripted = scripted or {}
        self.calls: list[tuple[str, dict]] = []

    async def request(self, endpoint: str, params: dict):
        self.calls.append((endpoint, params))
        response = self.scripted.get(endpoint, {})
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            return response(params)
        return response


def _assertion(
    *,
    assertion_id: str,
    kind: str,
    target: str,
    probe: str,
    expected=True,
    comparator: str = "eq",
    required: bool = True,
) -> ValidationAssertion:
    return ValidationAssertion(
        id=assertion_id,
        kind=kind,
        target=target,
        required=required,
        comparator=comparator,
        expected=expected,
        probe=probe,
    )


def _contract(**updates) -> ValidationContract:
    values = {
        "target_root": "/project1",
        "output_path": "/project1/out1",
    }
    values.update(updates)
    return ValidationContract(**values)


@pytest.mark.asyncio
async def test_unavailable_runtime_probe_is_reported_and_cannot_pass_from_static_structure():
    contract = _contract(
        runtime_assertions=[
            _assertion(
                assertion_id="audio:active",
                kind="nonzero_signal",
                target="/project1/audio_out",
                probe="chop_data",
                expected=0.001,
                comparator="gt",
            )
        ]
    )
    client = FakeTDClient(
        scripted={
            # Even if the node exists structurally, the declared runtime probe
            # is unavailable and must not be replaced by node existence.
            "node/detail": {"path": "/project1/audio_out", "type": "nullCHOP"},
            "chop/data": RuntimeError("TouchDesigner is not running"),
        }
    )

    report = await validate_contract(client, contract)

    assert report.ok is False
    assert report.unavailable_assertion_ids == ["audio:active"]
    assert report.results[0].status == "unavailable"
    assert report.results[0].endpoint == "chop/data"
    assert report.results[0].issue_code == "runtime_probe_unavailable"
    assert all(endpoint != "node/detail" for endpoint, _params in client.calls)


@pytest.mark.asyncio
async def test_graph_existence_and_runtime_binding_readback_use_live_endpoints():
    expression = "op('/project1/audio_out')['low']"
    contract = _contract(
        graph_assertions=[
            _assertion(
                assertion_id="output:exists",
                kind="exists",
                target="/project1/out1",
                probe="node_query",
                comparator="exists",
            )
        ],
        runtime_assertions=[
            _assertion(
                assertion_id="binding:readback",
                kind="binding_readback",
                target="/project1/level1",
                probe="param_query",
                expected={"param": "opacity", "expr": expression},
            )
        ],
    )
    client = FakeTDClient(
        scripted={
            "node/detail": {"path": "/project1/out1", "type": "nullTOP"},
            "node/params": {
                "parameters": {"opacity": {"value": 0.5, "expr": expression, "mode": "expression"}}
            },
        }
    )

    report = await validate_contract(client, contract)

    assert report.ok is True
    assert [result.status for result in report.results] == ["passed", "passed"]
    assert ("node/params", {"path": "/project1/level1", "names": ["opacity"]}) in client.calls


@pytest.mark.asyncio
async def test_black_feedback_and_static_motion_emit_repair_specific_failure_codes():
    contract = _contract(
        visual_assertions=[
            _assertion(
                assertion_id="feedback:visible",
                kind="not_black",
                target="/project1/out1",
                probe="frame_metrics",
            ),
            _assertion(
                assertion_id="feedback:moves",
                kind="changing_signal",
                target="/project1/out1",
                probe="frame_metrics",
            ),
        ]
    )
    static_frame = {
        "path": "/project1/out1",
        "modes": {
            "luminance": {"mean": 0.0, "max": 0.0, "std": 0.0},
            "alpha_coverage": {"opaque_fraction": 1.0},
        },
    }
    client = FakeTDClient(scripted={"analyze_frame": static_frame})

    report = await validate_contract(client, contract)

    assert report.ok is False
    assert report.failed_assertion_ids == ["feedback:visible", "feedback:moves"]
    assert [result.issue_code for result in report.results] == [
        "black_feedback_output",
        "static_or_missing_binding",
    ]
    assert len([call for call in client.calls if call[0] == "analyze_frame"]) == 3


@pytest.mark.asyncio
async def test_frame_motion_passes_only_with_two_distinct_live_samples():
    calls = {"count": 0}

    def moving_frame(_params):
        calls["count"] += 1
        value = 0.1 * calls["count"]
        return {
            "modes": {
                "luminance": {"mean": value, "max": value + 0.2, "std": 0.05},
                "alpha_coverage": {"opaque_fraction": 1.0},
            }
        }

    contract = _contract(
        visual_assertions=[
            _assertion(
                assertion_id="feedback:moves",
                kind="changing_signal",
                target="/project1/out1",
                probe="frame_metrics",
                expected=0.01,
                comparator="gt",
            )
        ]
    )

    report = await validate_contract(FakeTDClient(scripted={"analyze_frame": moving_frame}), contract)

    assert report.ok is True
    assert report.results[0].evidence["sample_count"] == 2
    assert report.results[0].evidence["motion_delta"] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_resolution_and_cook_metrics_are_checked_against_post_apply_state():
    contract = _contract(
        graph_assertions=[
            _assertion(
                assertion_id="output:resolution",
                kind="resolution",
                target="/project1/out1",
                probe="param_query",
                expected=[1920, 1080],
            )
        ],
        performance_assertions=[
            _assertion(
                assertion_id="output:cook_budget",
                kind="cook_budget",
                target="/project1",
                probe="cook_info",
                expected=8.0,
                comparator="lte",
            )
        ],
    )
    client = FakeTDClient(
        scripted={
            "node/detail": {"path": "/project1/out1", "resolution": [1280, 720]},
            "cooking": {"total_cook_ms": 14.2, "nodes": []},
        }
    )

    report = await validate_contract(client, contract)

    assert report.ok is False
    assert report.failed_assertion_ids == ["output:resolution", "output:cook_budget"]
    assert [result.issue_code for result in report.results] == [
        "resolution_mismatch",
        "excessive_cook_cost",
    ]


@pytest.mark.asyncio
async def test_legacy_report_projection_preserves_unavailable_as_an_error():
    contract = _contract(
        visual_assertions=[
            _assertion(
                assertion_id="output:visible",
                kind="not_black",
                target="/project1/out1",
                probe="frame_metrics",
            )
        ]
    )

    contract_report = await validate_contract(FakeTDClient(), contract)
    legacy = to_validation_report_v2(contract_report)

    assert legacy.ok is False
    assert legacy.issues[0].code == "runtime_probe_unavailable"
    assert legacy.issues[0].severity == "error"
    assert legacy.cheap_metrics["assertion_results"][0]["status"] == "unavailable"
