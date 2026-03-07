import pytest

from td_mcp.events import EventManager


class DummyMCP:
    def __init__(self):
        self.updated = []

    async def notify_resource_updated(self, uri):
        self.updated.append(uri)


@pytest.mark.asyncio
async def test_event_history_maxlen_and_filtering():
    mcp = DummyMCP()
    manager = EventManager(mcp_server=mcp, max_history=3)

    for idx in range(5):
        await manager.process_event(
            {
                "type": "timeline" if idx % 2 == 0 else "chop_change",
                "data": {"path": "/project1/audio1", "channel": "chan1"},
            }
        )

    all_events = manager.get_recent_events(limit=10)
    timeline_events = manager.get_recent_events(event_type="timeline", limit=10)

    assert len(all_events) == 3
    assert all(event.get("type") in {"timeline", "chop_change"} for event in all_events)
    assert all(event.get("type") == "timeline" for event in timeline_events)


@pytest.mark.asyncio
async def test_process_raw_message_ignores_invalid_json():
    manager = EventManager(mcp_server=DummyMCP(), max_history=5)

    await manager.process_raw_message("not-json")

    assert manager.get_recent_events(limit=10) == []


@pytest.mark.asyncio
async def test_set_state_records_resource_update_event():
    mcp = DummyMCP()
    manager = EventManager(mcp_server=mcp, max_history=10)

    await manager.set_state("td://timeline/state", {"playing": True}, notify=True)

    assert mcp.updated == ["td://timeline/state"]
    recent = manager.get_recent_events(limit=1)
    assert recent[0]["type"] == "resource_update"
    assert recent[0]["resource_uri"] == "td://timeline/state"
