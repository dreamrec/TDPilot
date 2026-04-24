"""Dual-mode bridge between MCP Tasks protocol and JobManager."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from td_mcp.capabilities import CapabilitySet
from td_mcp.jobs.manager import JobManager


class TaskAdapter:
    """Bridges JobManager with MCP Tasks protocol when client supports it.

    When ``capabilities.supports_tasks`` is False, the adapter acts as a
    thin pass-through that simply delegates to ``JobManager``.

    When tasks are supported, ``wrap_job`` enriches the job snapshot with
    an ``mcp_task`` metadata block, and ``on_progress`` / ``on_complete``
    also fire ``notify_fn`` so the MCP layer can surface real-time updates.
    """

    def __init__(
        self,
        job_manager: JobManager,
        capabilities: CapabilitySet,
        notify_fn: Callable[[str, float, str], None] | None = None,
    ) -> None:
        self._manager = job_manager
        self._capabilities = capabilities
        self._notify = notify_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tasks_supported(self) -> bool:
        """Return True when the connected MCP client supports Tasks."""
        return self._capabilities.supports_tasks

    def wrap_job(self, job_id: str) -> dict[str, Any] | None:
        """Return job snapshot, optionally enriched with mcp_task metadata.

        Returns ``None`` when the job_id is not tracked by the manager.
        """
        job = self._manager.get_job(job_id)
        if job is None:
            return None

        result = dict(job)

        if self.tasks_supported:
            result["mcp_task"] = {
                "task_id": job_id,
                "status": job.get("status", "pending"),
                "progress": job.get("progress", 0.0),
            }

        return result

    def on_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Update job progress and optionally fire the notify callback."""
        self._manager.update_job(job_id, progress=progress)
        if self._notify is not None:
            self._notify(job_id, progress, message)

    def on_complete(self, job_id: str, result: Any = None) -> None:
        """Mark a job as completed and optionally fire the notify callback."""
        self._manager.update_job(
            job_id,
            status="completed",
            progress=1.0,
            result=result,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        if self._notify is not None:
            self._notify(job_id, 1.0, "completed")
