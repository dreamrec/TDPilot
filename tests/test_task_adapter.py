"""Tests for TaskAdapter bridge and JobManager callback hooks."""

from __future__ import annotations

import asyncio

from td_mcp.capabilities import CapabilitySet
from td_mcp.jobs.manager import JobManager
from td_mcp.jobs.task_adapter import TaskAdapter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _caps(supports_tasks: bool = False) -> CapabilitySet:
    return CapabilitySet(supports_tasks=supports_tasks)


def _make_adapter(supports_tasks: bool = False, notify_fn=None) -> tuple[JobManager, TaskAdapter]:
    manager = JobManager()
    caps = _caps(supports_tasks=supports_tasks)
    adapter = TaskAdapter(manager, caps, notify_fn=notify_fn)
    return manager, adapter


# ---------------------------------------------------------------------------
# Task 1 — TaskAdapter.wrap_job
# ---------------------------------------------------------------------------


def test_adapter_no_tasks_support():
    """wrap_job returns plain job dict without mcp_task when tasks not supported."""
    manager, adapter = _make_adapter(supports_tasks=False)
    job = manager.create_job(description="test job")
    result = adapter.wrap_job(job["job_id"])
    assert result is not None
    assert result["job_id"] == job["job_id"]
    assert "mcp_task" not in result


def test_adapter_with_tasks_support():
    """wrap_job adds mcp_task metadata when supports_tasks=True."""
    manager, adapter = _make_adapter(supports_tasks=True)
    job = manager.create_job(description="test job")
    result = adapter.wrap_job(job["job_id"])
    assert result is not None
    assert result["job_id"] == job["job_id"]
    assert "mcp_task" in result
    assert result["mcp_task"]["task_id"] == job["job_id"]


def test_adapter_tasks_supported_property():
    """tasks_supported property reflects capability flag."""
    _, adapter_no = _make_adapter(supports_tasks=False)
    _, adapter_yes = _make_adapter(supports_tasks=True)
    assert adapter_no.tasks_supported is False
    assert adapter_yes.tasks_supported is True


# ---------------------------------------------------------------------------
# Task 1 — TaskAdapter.on_progress / on_complete
# ---------------------------------------------------------------------------


def test_on_progress_callback():
    """on_progress updates job progress via JobManager."""
    manager, adapter = _make_adapter(supports_tasks=False)
    job = manager.create_job(description="progress test")
    job_id = job["job_id"]
    adapter.on_progress(job_id, 0.5, "halfway")
    snapshot = manager.get_job(job_id)
    assert snapshot is not None
    assert snapshot["progress"] == 0.5


def test_on_complete_callback():
    """on_complete marks job as completed with result."""
    manager, adapter = _make_adapter(supports_tasks=False)
    job = manager.create_job(description="complete test")
    job_id = job["job_id"]
    adapter.on_complete(job_id, {"output": "done"})
    snapshot = manager.get_job(job_id)
    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["result"] == {"output": "done"}


def test_on_progress_fires_notify():
    """on_progress calls notify_fn when provided."""
    calls = []

    def notify(job_id, progress, message):
        calls.append({"job_id": job_id, "progress": progress, "message": message})

    manager, adapter = _make_adapter(supports_tasks=True, notify_fn=notify)
    job = manager.create_job(description="notify test")
    job_id = job["job_id"]
    adapter.on_progress(job_id, 0.75, "almost done")
    assert len(calls) == 1
    assert calls[0]["progress"] == 0.75
    assert calls[0]["message"] == "almost done"


def test_on_complete_fires_notify():
    """on_complete calls notify_fn when provided."""
    calls = []

    def notify(job_id, progress, message):
        calls.append({"job_id": job_id, "progress": progress, "message": message})

    manager, adapter = _make_adapter(supports_tasks=True, notify_fn=notify)
    job = manager.create_job(description="notify complete test")
    job_id = job["job_id"]
    adapter.on_complete(job_id, {"result": 42})
    assert len(calls) == 1
    assert calls[0]["progress"] == 1.0


# ---------------------------------------------------------------------------
# Task 2 — JobManager callback hooks
# ---------------------------------------------------------------------------


def test_job_manager_progress_hook():
    """JobManager fires on_progress_hook when progress field is updated."""
    manager = JobManager()
    progress_calls = []

    def progress_hook(job_id: str, progress: float) -> None:
        progress_calls.append((job_id, progress))

    manager.on_progress_hook = progress_hook
    job = manager.create_job(description="hook test")
    job_id = job["job_id"]
    manager.update_job(job_id, progress=0.3)
    assert len(progress_calls) == 1
    assert progress_calls[0] == (job_id, 0.3)


def test_job_manager_complete_hook():
    """JobManager fires on_complete_hook when status becomes completed."""
    manager = JobManager()
    complete_calls = []

    def complete_hook(job_id: str) -> None:
        complete_calls.append(job_id)

    manager.on_complete_hook = complete_hook
    job = manager.create_job(description="complete hook test")
    job_id = job["job_id"]
    manager.update_job(job_id, status="completed", progress=1.0)
    assert len(complete_calls) == 1
    assert complete_calls[0] == job_id


def test_job_manager_complete_hook_not_fired_for_other_statuses():
    """on_complete_hook is NOT fired when status is not 'completed'."""
    manager = JobManager()
    complete_calls = []

    manager.on_complete_hook = lambda job_id: complete_calls.append(job_id)
    job = manager.create_job(description="partial hook test")
    job_id = job["job_id"]
    manager.update_job(job_id, status="running")
    manager.update_job(job_id, status="failed")
    assert len(complete_calls) == 0


def test_job_manager_hooks_default_none():
    """JobManager initializes with hook attributes set to None."""
    manager = JobManager()
    assert manager.on_progress_hook is None
    assert manager.on_complete_hook is None


def test_job_manager_complete_hook_fires_via_start_async():
    """on_complete_hook fires when start_async job completes."""

    async def _run():
        manager = JobManager()
        complete_calls = []

        manager.on_complete_hook = lambda job_id: complete_calls.append(job_id)

        async def runner(job_id):
            return {"done": True}

        job = manager.start_async("async hook test", runner)
        await asyncio.sleep(0.05)

        assert len(complete_calls) == 1
        assert complete_calls[0] == job["job_id"]

    asyncio.run(_run())
