"""Lifespan service container shared across tool handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from td_mcp.audit import AuditLogger
from td_mcp.telemetry import TelemetryCollector


@dataclass
class ServiceContainer:
    """Holds runtime services initialized in FastMCP lifespan."""

    td_client: object
    macro_engine: Optional[object] = None
    event_manager: Optional[object] = None
    visual_monitor: Optional[object] = None
    top_streamer: Optional[object] = None
    safety_manager: Optional[object] = None
    snapshot_manager: Optional[object] = None
    job_manager: Optional[object] = None
    task_adapter: Optional[object] = None
    technique_store: Optional[object] = None
    preference_store: Optional[object] = None
    telemetry: Optional[TelemetryCollector] = None
    audit: Optional[AuditLogger] = None
    card_index: Optional[object] = None
    td_build: str = ""
