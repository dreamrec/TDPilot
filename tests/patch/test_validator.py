"""Tests for src/td_mcp/patch/validator.py."""

from __future__ import annotations

import pytest

from patch.conftest import FakeTDClient
from td_mcp.models.patch import ValidationPlan
from td_mcp.patch.validator import validate_target


@pytest.mark.asyncio
async def test_validate_clean():
    client = FakeTDClient(
        scripted={
            "node/errors": {"issues": []},
            "cooking": {"total_cook_ms": 12.3, "stuck": []},
        }
    )
    plan = ValidationPlan(target_root="/project1", capture_frames=[])
    report = await validate_target(client, plan)
    assert report.ok is True
    assert report.errors == []
    assert report.target_root == "/project1"
    assert report.frames == {}  # no capture_frames -> no calls


@pytest.mark.asyncio
async def test_validate_with_errors():
    client = FakeTDClient(
        scripted={
            "node/errors": {"issues": [{"node": "/p/n1", "message": "bad"}]},
            "cooking": {"total_cook_ms": 5.0, "stuck": []},
        }
    )
    report = await validate_target(client, ValidationPlan(target_root="/p"))
    assert report.ok is False
    assert len(report.errors) == 1


@pytest.mark.asyncio
async def test_validate_fails_closed_when_cooking_probe_errors():
    """A failed cooking probe means we can't tell if nodes are stuck — the
    report must NOT claim ok (fail closed), even with no errors."""
    client = FakeTDClient(
        scripted={
            "node/errors": {"issues": []},
            "cooking": RuntimeError("cooking probe unavailable"),
        }
    )
    report = await validate_target(client, ValidationPlan(target_root="/p"))
    assert report.ok is False
    assert report.cook_stats.get("probe_error")


@pytest.mark.asyncio
async def test_validate_with_capture_frames():
    """v1.5.1: validator now uses TD's /api/screenshot endpoint
    (returns ``data_base64``), not the fictional /api/frame/capture
    that pre-v1.5.1 silently 404'd against."""
    client = FakeTDClient(
        scripted={
            "node/errors": {"issues": []},
            "cooking": {"total_cook_ms": 1.0, "stuck": []},
            "screenshot": lambda params: {
                "success": True,
                "path": params["path"],
                "data_base64": "Zm9v",
            },
        }
    )
    plan = ValidationPlan(target_root="/p", capture_frames=["/p/out1", "/p/out2"])
    report = await validate_target(client, plan)
    assert set(report.frames.keys()) == {"/p/out1", "/p/out2"}
    assert report.frames["/p/out1"] == "Zm9v"
    # Verify the client hit the canonical screenshot endpoint, not the
    # nonexistent frame/capture path.
    screenshot_calls = [c for c in client.calls if c[0] == "screenshot"]
    assert len(screenshot_calls) == 2
    legacy_calls = [c for c in client.calls if c[0] == "frame/capture"]
    assert legacy_calls == []


@pytest.mark.asyncio
async def test_validate_fails_when_requested_capture_frame_is_missing():
    client = FakeTDClient(
        scripted={
            "node/errors": {"issues": []},
            "cooking": {"total_cook_ms": 1.0, "stuck": []},
            "screenshot": lambda params: {"error": f"Node not found: {params['path']}"},
        }
    )
    plan = ValidationPlan(target_root="/p", capture_frames=["/p/out_missing"])

    report = await validate_target(client, plan)

    assert report.ok is False
    assert report.frames["/p/out_missing"].startswith("ERROR:")
    assert any("capture frame failed" in item["message"] for item in report.errors)
