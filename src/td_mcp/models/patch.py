"""Typed Pydantic models for the Patch Session MVP (Phase 3).

See docs/superpowers/specs/2026-04-24-v1.5.0-phase-3-patch-session-design.md
§4 for the authoritative model definitions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PatchOperation",
    "ValidationPlan",
    "PatchPlan",
    "PatchPreview",
    "ValidationReport",
    "PatchResult",
    "PatchVariant",
]


class PatchOperation(BaseModel):
    """One atomic TD edit. See spec §4.1."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["create_node", "set_params", "connect", "layout", "annotate", "macro"]
    target: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)


class ValidationPlan(BaseModel):
    """What a patch wants validated post-apply. See spec §4.2."""

    model_config = ConfigDict(extra="forbid")

    target_root: str
    capture_frames: list[str] = Field(default_factory=list)


class PatchPlan(BaseModel):
    """The stateless, pass-by-value patch blueprint. See spec §4.3."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str | None = None
    target_root: str
    source: Literal["intent_heuristic", "recipe", "operations", "variant"]
    source_recipe_id: str | None = None
    operations: list[PatchOperation] = Field(default_factory=list)
    required_ops: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    undo_label: str
    validation_plan: ValidationPlan
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatchPreview(BaseModel):
    """Return shape of td_patch_preview. See spec §4.4."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    summary: str
    risk_flags: list[str] = Field(default_factory=list)
    live_risk_flags: list[str] = Field(default_factory=list)
    required_ops: list[str] = Field(default_factory=list)
    op_count: int


class ValidationReport(BaseModel):
    """Return shape of td_patch_validate. See spec §4.5."""

    model_config = ConfigDict(extra="forbid")

    target_root: str
    errors: list[dict[str, Any]] = Field(default_factory=list)
    cook_stats: dict[str, Any] = Field(default_factory=dict)
    frames: dict[str, str] = Field(default_factory=dict)
    ok: bool
    summary: str


class PatchResult(BaseModel):
    """Outcome of td_patch_apply. See spec §4.6."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    status: Literal["clean", "warnings", "broken"]
    applied_ops: list[int] = Field(default_factory=list)
    failed_op: int | None = None
    failed_reason: str | None = None
    created_paths: list[str] = Field(default_factory=list)
    changed_params: list[dict[str, Any]] = Field(default_factory=list)
    connections_made: list[tuple[str, str]] = Field(default_factory=list)
    validation: ValidationReport | None = None
    risk_flags: list[str] = Field(default_factory=list)
    before_snapshot_id: str | None = None
    after_snapshot_id: str | None = None
    undo_label: str
    rollback_hint: str | None = None


class PatchVariant(PatchPlan):
    """A variant of a PatchPlan derived via a variation strategy. See spec §4.7."""

    source: Literal["variant"] = "variant"
    base_plan_id: str
    strategy: Literal["param_jitter", "operator_substitute", "topology_perturb"]
    seed: int
