import pytest

from td_mcp.events.event_manager import EventManager


class FakeMCPServer:
    def __init__(self):
        self.updated = []

    async def notify_resource_updated(self, uri):
        self.updated.append(uri)


@pytest.mark.asyncio
async def test_process_event_updates_state_and_notifies():
    mcp = FakeMCPServer()
    manager = EventManager(mcp_server=mcp, port=19982, max_history=10)

    event = {
        "type": "chop_change",
        "timestamp": 1.23,
        "frame": 42,
        "data": {"path": "/project1/audio1", "channel": "chan1", "value": 0.5},
    }
    await manager.process_event(event)

    uri = "td://chop/path/%2Fproject1%2Faudio1/channel/chan1"
    assert manager.get_state(uri) is not None
    assert mcp.updated == [uri]
    assert len(manager.get_recent_events(limit=10)) == 1


def test_subscription_registry_roundtrip():
    mcp = FakeMCPServer()
    manager = EventManager(mcp_server=mcp, port=19982, max_history=10)

    manager.register_subscription("/project1/audio1", "chop_change", {"event_types": ["chop_change"]})
    assert manager.get_subscription("/project1/audio1", "chop_change") == {"event_types": ["chop_change"]}
    assert manager.unregister_subscription("/project1/audio1", "chop_change") is True
    assert manager.unregister_subscription("/project1/audio1", "chop_change") is False


@pytest.mark.asyncio
async def test_process_event_maps_cook_complete_and_node_error_resources():
    mcp = FakeMCPServer()
    manager = EventManager(mcp_server=mcp, port=19982, max_history=10)

    await manager.process_event(
        {
            "type": "cook_complete",
            "data": {"path": "/project1/noise1", "frame": 100},
        }
    )
    await manager.process_event(
        {
            "type": "node_error",
            "data": {"path": "/project1/noise1", "errors": "boom"},
        }
    )

    cook_uri = "td://cook/path/%2Fproject1%2Fnoise1"
    error_uri = "td://error/path/%2Fproject1%2Fnoise1"

    assert manager.get_state(cook_uri) is not None
    assert manager.get_state(error_uri) is not None
    assert cook_uri in mcp.updated
    assert error_uri in mcp.updated
