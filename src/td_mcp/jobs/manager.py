"""In-process async job manager for long-running tool operations."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any


class JobManager:
    """Tracks and runs async jobs with status snapshots."""

    def __init__(self, mcp_server=None):
        self._mcp = mcp_server
        self._jobs: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self.on_progress_hook: Callable | None = None
        self.on_complete_hook: Callable | None = None

    def create_job(self, description: str = "") -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "job_id": job_id,
            "status": "pending",
            "description": description,
            "progress": 0.0,
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self._jobs[job_id] = payload
        return payload

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **fields: Any) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "progress" in fields and self.on_progress_hook is not None:
            self.on_progress_hook(job_id, fields["progress"])
        if fields.get("status") == "completed" and self.on_complete_hook is not None:
            self.on_complete_hook(job_id)

    def start_async(
        self,
        description: str,
        runner: Callable[[str], Awaitable[Any]],
    ) -> dict[str, Any]:
        job = self.create_job(description=description)
        job_id = job["job_id"]
        self.update_job(job_id, status="running")

        async def task_wrapper() -> None:
            try:
                result = await runner(job_id)
                self.update_job(
                    job_id,
                    status="completed",
                    progress=1.0,
                    result=result,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            except asyncio.CancelledError:
                self.update_job(
                    job_id,
                    status="cancelled",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as exc:  # pragma: no cover - defensive runtime path
                self.update_job(
                    job_id,
                    status="failed",
                    error=str(exc),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

        task = asyncio.create_task(task_wrapper())
        self._tasks[job_id] = task
        return job

    def cancel_job(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if not task:
            return False
        task.cancel()
        return True

    def stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for job in self._jobs.values():
            status = str(job.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "count": len(self._jobs),
            "active_tasks": sum(1 for task in self._tasks.values() if not task.done()),
            "status_counts": status_counts,
        }

    async def shutdown(self) -> None:
        if not self._tasks:
            return
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
