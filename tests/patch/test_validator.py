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
            "cooking_info": {"total_cook_ms": 12.3, "stuck": []},
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
            "cooking_info": {"total_cook_ms": 5.0, "stuck": []},
        }
    )
    report = await validate_target(client, ValidationPlan(target_root="/p"))
    assert report.ok is False
    assert len(report.errors) == 1


@pytest.mark.asyncio
async def test_validate_with_capture_frames():
    client = FakeTDClient(
        scripted={
            "node/errors": {"issues": []},
            "cooking_info": {"total_cook_ms": 1.0, "stuck": []},
            "frame/capture": lambda params: {"b64": "Zm9v", "path": params["path"]},
        }
    )
    plan = ValidationPlan(target_root="/p", capture_frames=["/p/out1", "/p/out2"])
    report = await validate_target(client, plan)
    assert set(report.frames.keys()) == {"/p/out1", "/p/out2"}
    # Verify the client was asked for frames
    frame_calls = [c for c in client.calls if c[0] == "frame/capture"]
    assert len(frame_calls) == 2
