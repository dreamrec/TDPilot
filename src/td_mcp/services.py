"""Lifespan service container shared across tool handlers."""

from __future__ import annotations

from dataclasses import dataclass

from td_mcp.audit import AuditLogger
from td_mcp.events import EventManager
from td_mcp.jobs import JobManager, TaskAdapter
from td_mcp.knowledge.card_index import CardIndex

try:
    from td_mcp.knowledge.docsbrain import DocsBrain
except ImportError:
    DocsBrain = None  # type: ignore[assignment,misc]
from td_mcp.macros import MacroEngine
from td_mcp.memory import KnowledgeStore, SnapshotManager, TechniqueStore
from td_mcp.memory.preference_store import PreferenceStore
from td_mcp.safety import SafetyManager
from td_mcp.td_client import TDClient
from td_mcp.telemetry import TelemetryCollector
from td_mcp.vision import TopStreamer, VisualMonitor


@dataclass
class ServiceContainer:
    """Holds runtime services initialized in FastMCP lifespan."""

    td_client: TDClient
    macro_engine: MacroEngine | None = None
    event_manager: EventManager | None = None
    visual_monitor: VisualMonitor | None = None
    top_streamer: TopStreamer | None = None
    safety_manager: SafetyManager | None = None
    snapshot_manager: SnapshotManager | None = None
    job_manager: JobManager | None = None
    task_adapter: TaskAdapter | None = None
    technique_store: TechniqueStore | None = None
    knowledge_store: KnowledgeStore | None = None
    preference_store: PreferenceStore | None = None
    telemetry: TelemetryCollector | None = None
    audit: AuditLogger | None = None
    card_index: CardIndex | None = None
    popx_brain: DocsBrain | None = None
    td_build: str = ""
