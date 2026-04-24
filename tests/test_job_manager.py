import asyncio

import pytest

from td_mcp.jobs.manager import JobManager


@pytest.mark.asyncio
async def test_job_manager_completes_job():
    manager = JobManager()

    async def runner(job_id):
        manager.update_job(job_id, progress=0.5)
        await asyncio.sleep(0)
        return {"ok": True}

    job = manager.start_async("demo", runner)
    await asyncio.sleep(0.01)

    snapshot = manager.get_job(job["job_id"])
    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["result"] == {"ok": True}
