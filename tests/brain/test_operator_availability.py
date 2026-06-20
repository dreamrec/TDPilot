from __future__ import annotations

import pytest

from td_mcp.brain.operator_availability import (
    build_availability_targets,
    sample_operator_availability,
)


def test_build_availability_targets_includes_deprecated_gaps_and_replacements() -> None:
    atlas_report = {
        "docsbrain_operator_coverage": {
            "deprecated_missing_operator_cards": [
                {
                    "op_type": "svgTOP",
                    "family": "TOP",
                    "gap_status": "deprecated_nonfunctional",
                    "replacement_op_types": ["webrenderTOP"],
                },
                {
                    "op_type": "glslcreatePOP",
                    "family": "POP",
                    "gap_status": "deprecated_pending_removal",
                    "replacement_op_types": ["glsladvancedPOP", "topologyPOP"],
                },
            ]
        }
    }

    targets = build_availability_targets(atlas_report)

    assert targets == [
        {
            "op_type": "glslcreatePOP",
            "family": "POP",
            "role": "deprecated_gap",
            "gap_status": "deprecated_pending_removal",
            "replacement_for": None,
        },
        {
            "op_type": "glsladvancedPOP",
            "family": None,
            "role": "replacement",
            "gap_status": None,
            "replacement_for": "glslcreatePOP",
        },
        {
            "op_type": "topologyPOP",
            "family": None,
            "role": "replacement",
            "gap_status": None,
            "replacement_for": "glslcreatePOP",
        },
        {
            "op_type": "svgTOP",
            "family": "TOP",
            "role": "deprecated_gap",
            "gap_status": "deprecated_nonfunctional",
            "replacement_for": None,
        },
        {
            "op_type": "webrenderTOP",
            "family": None,
            "role": "replacement",
            "gap_status": None,
            "replacement_for": "svgTOP",
        },
    ]


class _AvailabilityFakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def health_check(self) -> dict:
        self.calls.append(("health", {}))
        return {"status": "ok", "api_version": "2.0.0"}

    async def request(self, endpoint: str, body: dict | None = None) -> dict:
        payload = body or {}
        self.calls.append((endpoint, payload))
        if endpoint == "node/create" and payload.get("name") == "tdpilot_availability_probe":
            return {"node": {"path": "/project1/tdpilot_availability_probe"}}
        if endpoint == "node/create" and payload.get("node_type") == "goodTOP":
            return {"node": {"path": "/project1/tdpilot_availability_probe/good"}}
        if endpoint == "node/create" and payload.get("node_type") == "badTOP":
            raise RuntimeError("Cannot create operator")
        if endpoint == "node/delete":
            return {"success": True}
        raise AssertionError(f"Unexpected call: {endpoint} {payload}")

    async def close(self) -> None:
        self.calls.append(("close", {}))


@pytest.mark.asyncio
async def test_sample_operator_availability_records_results_and_cleans_scratch() -> None:
    client = _AvailabilityFakeClient()
    targets = [
        {
            "op_type": "goodTOP",
            "family": "TOP",
            "role": "replacement",
            "gap_status": None,
            "replacement_for": "oldTOP",
        },
        {
            "op_type": "badTOP",
            "family": "TOP",
            "role": "deprecated_gap",
            "gap_status": "deprecated_nonfunctional",
            "replacement_for": None,
        },
    ]

    report = await sample_operator_availability(client, targets, parent_path="/project1")

    assert report["ok"] is True
    assert report["target_count"] == 2
    assert report["available_count"] == 1
    assert report["unavailable_count"] == 1
    assert report["cleanup_ok"] is True
    assert report["results"] == [
        {
            "op_type": "goodTOP",
            "family": "TOP",
            "role": "replacement",
            "gap_status": None,
            "replacement_for": "oldTOP",
            "available": True,
            "created_path": "/project1/tdpilot_availability_probe/good",
            "error": "",
        },
        {
            "op_type": "badTOP",
            "family": "TOP",
            "role": "deprecated_gap",
            "gap_status": "deprecated_nonfunctional",
            "replacement_for": None,
            "available": False,
            "created_path": "",
            "error": "Cannot create operator",
        },
    ]
    assert client.calls[-2] == ("node/delete", {"path": "/project1/tdpilot_availability_probe"})
    assert client.calls[-1] == ("close", {})
