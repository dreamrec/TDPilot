"""Lifespan service container shared across tool handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from td_mcp.audit import AuditLogger
from td_mcp.events import EventManager
from td_mcp.jobs import JobManager, TaskAdapter
from td_mcp.knowledge.card_index import CardIndex
from td_mcp.macros import MacroEngine
from td_mcp.memory import SnapshotManager, TechniqueStore
from td_mcp.memory.preference_store import PreferenceStore
from td_mcp.safety import SafetyManager
from td_mcp.td_client import TDClient
from td_mcp.telemetry import TelemetryCollector
from td_mcp.vision import TopStreamer, VisualMonitor


@dataclass
class ServiceContainer:
    """Holds runtime services initialized in FastMCP lifespan."""

    td_client: TDClient
    macro_engine: Optional[MacroEngine] = None
    event_manager: Optional[EventManager] = None
    visual_monitor: Optional[VisualMonitor] = None
    top_streamer: Optional[TopStreamer] = None
    safety_manager: Optional[SafetyManager] = None
    snapshot_manager: Optional[SnapshotManager] = None
    job_manager: Optional[JobManager] = None
    task_adapter: Optional[TaskAdapter] = None
    technique_store: Optional[TechniqueStore] = None
    preference_store: Optional[PreferenceStore] = None
    telemetry: Optional[TelemetryCollector] = None
    audit: Optional[AuditLogger] = None
    card_index: Optional[CardIndex] = None
    td_build: str = ""
