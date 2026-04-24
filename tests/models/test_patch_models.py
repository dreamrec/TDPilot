"""Tests for src/td_mcp/models/patch.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.models.patch import PatchOperation


class TestPatchOperation:
    def test_valid_create_node(self):
        op = PatchOperation(kind="create_node", target="/project1", args={"op_type": "noise", "name": "noise1"})
        assert op.kind == "create_node"
        assert op.target == "/project1"
        assert op.depends_on == []

    def test_each_of_six_kinds_parseable(self):
        for kind in ("create_node", "set_params", "connect", "layout", "annotate", "macro"):
            op = PatchOperation(kind=kind, args={})
            assert op.kind == kind

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValidationError):
            PatchOperation(kind="delete", args={})  # delete deferred to v1.5.1

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            PatchOperation(kind="create_node", args={}, unknown_field=True)

    def test_depends_on_defaults_empty(self):
        op = PatchOperation(kind="create_node", args={})
        assert op.depends_on == []
        op2 = PatchOperation(kind="connect", args={}, depends_on=[0, 1])
        assert op2.depends_on == [0, 1]


from td_mcp.models.patch import ValidationPlan


class TestValidationPlan:
    def test_minimal(self):
        vp = ValidationPlan(target_root="/project1")
        assert vp.target_root == "/project1"
        assert vp.capture_frames == []

    def test_with_frames(self):
        vp = ValidationPlan(target_root="/p", capture_frames=["/p/out1", "/p/out2"])
        assert vp.capture_frames == ["/p/out1", "/p/out2"]
