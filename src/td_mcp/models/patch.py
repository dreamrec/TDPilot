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
