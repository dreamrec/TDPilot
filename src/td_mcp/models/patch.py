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
