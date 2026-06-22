from __future__ import annotations

import json
from pathlib import Path

import pytest

from td_mcp.brain import operator_availability
from td_mcp.brain.operator_availability import (
    build_availability_targets,
    build_operator_availability_matrix,
    load_operator_substitution_rules,
    operator_availability_coverage_report,
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
        return {
            "status": "ok",
            "api_version": "2.0.0",
            "td_build": "2025.32820",
            "platform": "macOS",
            "installed_addons": ["POPX"],
        }

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


class _AvailabilityInfoFallbackClient(_AvailabilityFakeClient):
    async def health_check(self) -> dict:
        self.calls.append(("health", {}))
        return {
            "status": "ok",
            "api_version": "2.0.0",
        }

    async def request(self, endpoint: str, body: dict | None = None) -> dict:
        payload = body or {}
        if endpoint == "info":
            self.calls.append((endpoint, payload))
            return {
                "build": "2025.32820",
                "osName": "macOS",
            }
        return await super().request(endpoint, body)


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
    assert report["availability_matrix"]["td_build"] == "2025.32820"
    assert report["availability_matrix"]["platform"] == "macOS"
    assert report["availability_matrix"]["installed_addons"] == ["POPX"]
    assert report["availability_matrix"]["operators"] == {
        "badTOP": {"family": "TOP", "available": False},
        "goodTOP": {"family": "TOP", "available": True},
    }
    assert report["availability_matrix"]["unavailable_reasons"] == {
        "badTOP": "Cannot create operator",
    }
    assert client.calls[-2] == ("node/delete", {"path": "/project1/tdpilot_availability_probe"})
    assert client.calls[-1] == ("close", {})


@pytest.mark.asyncio
async def test_sample_operator_availability_uses_info_endpoint_when_health_lacks_build() -> None:
    client = _AvailabilityInfoFallbackClient()
    targets = [
        {
            "op_type": "goodTOP",
            "family": "TOP",
            "role": "replacement",
            "gap_status": None,
            "replacement_for": "oldTOP",
        }
    ]

    report = await sample_operator_availability(client, targets, parent_path="/project1")

    assert report["availability_matrix"]["td_build"] == "2025.32820"
    assert report["availability_matrix"]["platform"] == "macOS"
    assert ("info", {}) in client.calls


def test_build_operator_availability_matrix_records_available_and_missing_ops():
    matrix = build_operator_availability_matrix(
        {"audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"},
        required_ops=["audiofileinCHOP", "audiodeviceinCHOP", "nullCHOP"],
        td_build="2025.32820",
        platform="macOS",
        installed_addons=["POPX"],
    )

    assert matrix.schema_version == 1
    assert matrix.td_build == "2025.32820"
    assert matrix.platform == "macOS"
    assert matrix.installed_addons == ["POPX"]
    assert matrix.operators["audiofileinCHOP"] == {"family": "CHOP", "available": True}
    assert matrix.operators["audiodeviceinCHOP"] == {"family": "CHOP", "available": False}
    assert matrix.family_aliases["CHOP"] == ["analyzeCHOP", "audiodeviceinCHOP", "audiofileinCHOP", "mathCHOP", "nullCHOP"]
    assert matrix.unavailable_reasons["audiodeviceinCHOP"] == "missing from live family list"


def test_availability_report_store_path_partitions_by_build_platform_and_addons(tmp_path: Path):
    matrix = build_operator_availability_matrix(
        {"audiofileinCHOP"},
        required_ops=["audiofileinCHOP", "audiodeviceinCHOP"],
        td_build="2025.32820",
        platform="macOS",
        installed_addons=["POPX", "Kinect Azure"],
    )
    report = {"schema_version": 1, "availability_matrix": matrix.model_dump()}

    assert hasattr(operator_availability, "availability_report_store_path")
    path = operator_availability.availability_report_store_path(report, root=tmp_path)

    assert path == tmp_path / "2025.32820" / "macos" / "kinect-azure_popx" / "operator_availability.json"


def test_save_and_load_operator_availability_report_round_trips_typed_matrix(tmp_path: Path):
    matrix = build_operator_availability_matrix(
        {"audiodeviceinCHOP"},
        required_ops=["audiofileinCHOP", "audiodeviceinCHOP"],
        td_build="2025.32820",
        platform="macOS",
        installed_addons=["POPX"],
    )
    report = {
        "schema_version": 1,
        "ok": True,
        "generated_at": "2026-06-22T00:00:00+00:00",
        "availability_matrix": matrix.model_dump(),
        "results": [],
    }

    assert hasattr(operator_availability, "save_operator_availability_report")
    assert hasattr(operator_availability, "load_operator_availability_report")
    path = operator_availability.save_operator_availability_report(report, root=tmp_path)
    loaded = operator_availability.load_operator_availability_report(path)

    assert path == tmp_path / "2025.32820" / "macos" / "popx" / "operator_availability.json"
    assert json.loads(path.read_text(encoding="utf-8")) == loaded
    assert loaded["availability_matrix"]["td_build"] == "2025.32820"
    assert loaded["availability_matrix"]["platform"] == "macOS"
    assert loaded["availability_matrix"]["installed_addons"] == ["POPX"]
    assert loaded["availability_matrix"]["operators"]["audiofileinCHOP"]["available"] is False


def test_load_operator_substitution_rules_returns_docs_grounded_phase_two_seed_rules():
    rules = load_operator_substitution_rules()
    by_missing = {rule.missing_op: rule for rule in rules}

    assert "audiofileinCHOP" in by_missing
    audio = by_missing["audiofileinCHOP"]
    assert audio.replacement_ops == ["audiodeviceinCHOP"]
    assert audio.replacement_pattern == "audio_device_to_analysis_chop"
    assert audio.confidence == "medium"
    assert audio.requires_user_approval is True
    assert audio.tradeoffs

    assert "glslcreatePOP" in by_missing
    assert by_missing["glslcreatePOP"].replacement_ops == ["glsladvancedPOP", "topologyPOP"]

    expected_deprecated_replacements = {
        "webDAT": ["webclientDAT"],
        "fieldCOMP": ["textCOMP"],
        "bandeqCHOP": ["audiobandeqCHOP"],
        "etherdreamCHOP": ["laserdeviceCHOP"],
        "heliosdacCHOP": ["laserdeviceCHOP"],
        "parametriceqCHOP": ["audioparaeqCHOP"],
        "scanCHOP": ["laserCHOP"],
        "fontSOP": ["textSOP"],
    }
    for missing_op, replacement_ops in expected_deprecated_replacements.items():
        rule = by_missing[missing_op]
        assert rule.replacement_ops == replacement_ops
        assert rule.replacement_pattern is None
        assert rule.confidence in {"medium", "high"}
        assert rule.requires_user_approval is False
        assert rule.tradeoffs

    realsense = by_missing["realsenseCHOP"]
    assert realsense.replacement_ops == ["realsenseTOP"]
    assert realsense.replacement_pattern is None
    assert realsense.confidence == "low"
    assert realsense.requires_user_approval is True
    assert realsense.tradeoffs

    assert all(
        source.startswith("https://docs.derivative.ca/")
        for rule in rules
        for source in rule.official_sources
    )


def test_operator_availability_coverage_report_covers_required_substitution_rules():
    report = operator_availability_coverage_report()

    assert report["ok"] is True
    assert report["rule_count"] >= 12
    assert report["required_rule_count"] >= 12
    assert report["covered_required_rule_count"] >= 12
    assert report["missing_required_rule_count"] == 0
    assert report["invalid_source_count"] == 0
    assert report["missing_tradeoff_count"] == 0
    assert {
        "audiofileinCHOP",
        "bandeqCHOP",
        "etherdreamCHOP",
        "fieldCOMP",
        "fontSOP",
        "glslcreatePOP",
        "heliosdacCHOP",
        "parametriceqCHOP",
        "realsenseCHOP",
        "scanCHOP",
        "svgTOP",
        "webDAT",
    }.issubset(set(report["covered_required_missing_ops"]))
