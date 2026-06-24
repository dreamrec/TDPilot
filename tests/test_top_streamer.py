import asyncio

import pytest

from td_mcp.events.uri import top_frame_uri
from td_mcp.vision.streamer import TopStreamer


class FakeEventManager:
    def __init__(self):
        self.updates = []

    async def set_state(self, resource_uri, payload, notify=True):
        self.updates.append((resource_uri, payload, notify))


class FakeTDClient:
    def __init__(self, mode="constant"):
        self.mode = mode
        self.count = 0
        self.calls = []

    async def request(self, endpoint, body):
        assert endpoint == "screenshot"
        self.calls.append((endpoint, body))
        self.count += 1
        if self.mode == "changing":
            data = f"frame-{self.count}"
        else:
            data = "frame-constant"
        payload = {
            "success": True,
            "path": body["path"],
            "format": "jpeg",
            "size_bytes": 0 if body.get("include_data") is False else len(data),
        }
        if body.get("include_data") is not False:
            payload["data_base64"] = data
        else:
            payload["data_omitted"] = True
        return payload


@pytest.mark.asyncio
async def test_top_streamer_metadata_mode_does_not_request_image_data():
    event_manager = FakeEventManager()
    client = FakeTDClient(mode="constant")
    streamer = TopStreamer(td_client=client, event_manager=event_manager, max_fps=30.0)

    await streamer.start_stream(path="/project1/out1", fps=20.0, quality=0.2, include_image=False)
    await asyncio.sleep(0.12)
    await streamer.stop_stream("/project1/out1")

    assert event_manager.updates
    assert client.calls
    assert all(
        call == ("screenshot", {"path": "/project1/out1", "quality": 0.2, "include_data": False})
        for call in client.calls
    )
    first_image = event_manager.updates[0][1].get("image", {})
    assert first_image.get("image_omitted") is True
    assert "data_base64" not in first_image


@pytest.mark.asyncio
async def test_top_streamer_dedupes_unchanged_frames():
    event_manager = FakeEventManager()
    client = FakeTDClient(mode="constant")
    streamer = TopStreamer(td_client=client, event_manager=event_manager, max_fps=30.0)

    await streamer.start_stream(
        path="/project1/out1", fps=20.0, quality=0.2, include_image=True, emit_unchanged=False
    )
    await asyncio.sleep(0.16)
    await streamer.stop_stream("/project1/out1")

    assert event_manager.updates
    assert event_manager.updates[0][0] == top_frame_uri("/project1/out1")
    first_image = event_manager.updates[0][1].get("image", {})
    assert first_image.get("data_base64") == "frame-constant"
    assert client.calls
    assert all(
        call == ("screenshot", {"path": "/project1/out1", "quality": 0.2, "include_data": True})
        for call in client.calls
    )
    # unchanged frames should be suppressed in dedupe mode
    assert len(event_manager.updates) == 1
    stats = streamer.stats()
    assert stats["dropped_unchanged"] >= 1


@pytest.mark.asyncio
async def test_top_streamer_can_emit_unchanged_frames():
    event_manager = FakeEventManager()
    streamer = TopStreamer(td_client=FakeTDClient(mode="constant"), event_manager=event_manager, max_fps=30.0)

    await streamer.start_stream(path="/project1/out1", fps=20.0, quality=0.2, emit_unchanged=True)
    await asyncio.sleep(0.16)
    await streamer.stop_stream("/project1/out1")

    assert len(event_manager.updates) >= 2


@pytest.mark.asyncio
async def test_top_streamer_emits_when_frame_changes():
    event_manager = FakeEventManager()
    streamer = TopStreamer(td_client=FakeTDClient(mode="changing"), event_manager=event_manager, max_fps=30.0)

    await streamer.start_stream(path="/project1/out1", fps=20.0, quality=0.2, emit_unchanged=False)
    await asyncio.sleep(0.16)
    await streamer.stop_stream("/project1/out1")

    assert len(event_manager.updates) >= 2


@pytest.mark.asyncio
async def test_top_streamer_can_include_image_payloads():
    event_manager = FakeEventManager()
    streamer = TopStreamer(td_client=FakeTDClient(mode="changing"), event_manager=event_manager, max_fps=30.0)

    await streamer.start_stream(
        path="/project1/out1",
        fps=20.0,
        quality=0.2,
        include_image=True,
        emit_unchanged=False,
    )
    await asyncio.sleep(0.16)
    await streamer.stop_stream("/project1/out1")

    assert event_manager.updates
    first_image = event_manager.updates[0][1].get("image", {})
    assert "data_base64" in first_image
