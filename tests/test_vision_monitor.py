import asyncio

import pytest

from td_mcp.events.uri import top_frame_uri
from td_mcp.vision import VisualMonitor


class FakeTDClient:
    def __init__(self):
        self.calls = []

    async def request(self, endpoint, body):
        assert endpoint == "screenshot"
        self.calls.append((endpoint, body))
        payload = {
            "success": True,
            "path": body["path"],
            "format": "jpeg",
            "size_bytes": 0 if body.get("include_data") is False else 4,
        }
        if body.get("include_data") is not False:
            payload["data_base64"] = "ZmFrZQ=="
        else:
            payload["data_omitted"] = True
        return {
            **payload,
        }


class FakeEventManager:
    def __init__(self):
        self.updates = []

    async def set_state(self, resource_uri, payload, notify=True):
        self.updates.append((resource_uri, payload, notify))


@pytest.mark.asyncio
async def test_visual_monitor_start_and_stop():
    event_manager = FakeEventManager()
    client = FakeTDClient()
    monitor = VisualMonitor(td_client=client, event_manager=event_manager)

    config = await monitor.start_monitor(path="/project1/out1", interval=0.05, quality=0.2)
    assert config["path"] == "/project1/out1"

    await asyncio.sleep(0.12)
    stopped = await monitor.stop_monitor("/project1/out1")

    assert stopped is True
    assert event_manager.updates
    assert event_manager.updates[-1][0] == top_frame_uri("/project1/out1")
    latest_payload = event_manager.updates[-1][1]
    image = latest_payload.get("image", {})
    assert image.get("image_omitted") is True
    assert "data_base64" not in image
    assert client.calls
    assert all(
        call == ("screenshot", {"path": "/project1/out1", "quality": 0.2, "include_data": False})
        for call in client.calls
    )


@pytest.mark.asyncio
async def test_visual_monitor_can_include_image_payload():
    event_manager = FakeEventManager()
    client = FakeTDClient()
    monitor = VisualMonitor(td_client=client, event_manager=event_manager)

    await monitor.start_monitor(path="/project1/out1", interval=0.05, quality=0.2, include_image=True)
    await asyncio.sleep(0.12)
    await monitor.stop_monitor("/project1/out1")

    assert event_manager.updates
    latest_payload = event_manager.updates[-1][1]
    image = latest_payload.get("image", {})
    assert image.get("data_base64") == "ZmFrZQ=="
    assert client.calls
    assert all(
        call == ("screenshot", {"path": "/project1/out1", "quality": 0.2, "include_data": True})
        for call in client.calls
    )
