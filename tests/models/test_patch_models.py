"""Tests for src/td_mcp/models/patch.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.models.patch import PatchOperation


class TestPatchOperation:
    def test_valid_create_node(self):
        op = PatchOperation(
            kind="create_node", target="/project1", args={"op_type": "noise", "name": "noise1"}
        )
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


import uuid as _uuid
from datetime import datetime, timezone

from td_mcp.models.patch import PatchPlan


class TestPatchPlan:
    def _minimal(self, **overrides):
        defaults = dict(
            target_root="/project1",
            source="operations",
            operations=[],
            undo_label="test",
            validation_plan=ValidationPlan(target_root="/project1"),
        )
        defaults.update(overrides)
        return PatchPlan(**defaults)

    def test_auto_generated_id_is_uuid(self):
        plan = self._minimal()
        _uuid.UUID(plan.id)  # raises if not a valid UUID

    def test_created_at_is_utc(self):
        plan = self._minimal()
        assert plan.created_at.tzinfo == timezone.utc

    def test_source_literal_rejects_invalid(self):
        with pytest.raises(ValidationError):
            self._minimal(source="arbitrary_string")

    def test_source_accepts_four_values(self):
        for s in ("intent_heuristic", "recipe", "operations", "variant"):
            self._minimal(source=s)

    def test_empty_operations_list_valid(self):
        plan = self._minimal(operations=[])
        assert plan.operations == []

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            self._minimal(unknown_field=True)


from td_mcp.models.patch import PatchPreview, PatchResult, PatchVariant, ValidationReport


class TestPatchPreview:
    def test_minimal(self):
        p = PatchPreview(plan_id="abc", summary="Will create 3 nodes", op_count=3)
        assert p.risk_flags == []
        assert p.live_risk_flags == []
        assert p.required_ops == []

    def test_with_flags(self):
        p = PatchPreview(
            plan_id="abc",
            summary="...",
            op_count=3,
            risk_flags=["mass-change"],
            live_risk_flags=["target-missing:/x"],
            required_ops=["noise", "unknown:zzz"],
        )
        assert "unknown:zzz" in p.required_ops


class TestValidationReport:
    def test_clean(self):
        r = ValidationReport(target_root="/p", ok=True, summary="clean")
        assert r.errors == [] and r.frames == {}

    def test_with_errors(self):
        r = ValidationReport(
            target_root="/p",
            ok=False,
            summary="errors present",
            errors=[{"node": "/p/n1", "message": "bad"}],
        )
        assert r.ok is False


class TestPatchResult:
    def test_clean_minimal(self):
        r = PatchResult(plan_id="abc", status="clean", undo_label="test")
        assert r.applied_ops == [] and r.risk_flags == []
        assert r.before_snapshot_id is None

    def test_broken(self):
        r = PatchResult(
            plan_id="abc",
            status="broken",
            undo_label="test",
            applied_ops=[0, 1],
            failed_op=2,
            failed_reason="boom",
            rollback_hint="undo 2 ops",
        )
        assert r.status == "broken"
        assert r.rollback_hint == "undo 2 ops"


class TestPatchVariant:
    def _minimal_variant(self):
        return PatchVariant(
            target_root="/p",
            operations=[],
            undo_label="v1",
            validation_plan=ValidationPlan(target_root="/p"),
            base_plan_id="parent-uuid",
            strategy="param_jitter",
            seed=42,
        )

    def test_source_is_variant(self):
        v = self._minimal_variant()
        assert v.source == "variant"

    def test_source_cannot_override(self):
        # Pydantic should reject attempts to set source to anything else.
        with pytest.raises(ValidationError):
            PatchVariant(
                target_root="/p",
                source="operations",  # narrowed Literal rejects
                operations=[],
                undo_label="v1",
                validation_plan=ValidationPlan(target_root="/p"),
                base_plan_id="parent",
                strategy="param_jitter",
                seed=0,
            )

    def test_inherits_patchplan_fields(self):
        v = self._minimal_variant()
        _uuid.UUID(v.id)  # has id from PatchPlan
        assert v.created_at.tzinfo == timezone.utc
