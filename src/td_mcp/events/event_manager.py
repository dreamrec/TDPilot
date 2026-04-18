"""WebSocket event bridge from TouchDesigner to MCP resources."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from typing import Any

import websockets

from td_mcp.events.uri import chop_uri, cook_uri, error_uri, par_uri


class EventManager:
    """Receives pushed events from TD and exposes state for MCP resources."""

    def __init__(self, mcp_server, port: int = 9982, max_history: int = 1000):
        self._mcp = mcp_server
        self._port = port
        self._state: dict[str, Any] = {}
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)
        self._subscriptions: dict[tuple[str, str], dict[str, Any]] = {}
        self._server = None

    async def start(self) -> None:
        self._server = await websockets.serve(
            self._handle_connection,
            "127.0.0.1",
            self._port,
        )

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle_connection(self, websocket) -> None:
        async for message in websocket:
            await self.process_raw_message(message)

    async def process_raw_message(self, message: str) -> None:
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            return
        await self.process_event(event)

    async def process_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type", "")
        data = event.get("data", {})
        resource_uri = self._event_to_resource_uri(event_type, data)

        if resource_uri:
            payload = {
                "event_schema_version": 1,
                "event": event,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            self._state[resource_uri] = payload
            notify = getattr(self._mcp, "notify_resource_updated", None)
            if callable(notify):
                try:
                    await notify(resource_uri)
                except Exception:
                    # If client transport does not support notifications, keep state silently.
                    pass

        history_entry = {
            **event,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(history_entry)

    async def set_state(self, resource_uri: str, payload: dict[str, Any], notify: bool = True) -> None:
        """Set resource state directly and optionally notify subscribers."""
        self._state[resource_uri] = payload
        self._history.append(
            {
                "type": "resource_update",
                "resource_uri": resource_uri,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if not notify:
            return
        notifier = getattr(self._mcp, "notify_resource_updated", None)
        if callable(notifier):
            try:
                await notifier(resource_uri)
            except Exception:
                pass

    def register_subscription(self, path: str, event_type: str, config: dict[str, Any]) -> None:
        self._subscriptions[(path, event_type)] = config

    def unregister_subscription(self, path: str, event_type: str) -> bool:
        return self._subscriptions.pop((path, event_type), None) is not None

    def unregister_all_for_path(self, path: str) -> int:
        """Remove all subscriptions for a given path, return count removed."""
        keys = [k for k in self._subscriptions if k[0] == path]
        for k in keys:
            del self._subscriptions[k]
        return len(keys)

    def get_subscription(self, path: str, event_type: str) -> dict[str, Any] | None:
        return self._subscriptions.get((path, event_type))

    def list_subscriptions(self) -> dict[tuple[str, str], dict[str, Any]]:
        return dict(self._subscriptions)

    def get_state(self, resource_uri: str) -> dict[str, Any] | None:
        return self._state.get(resource_uri)

    def get_recent_events(self, event_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        events = list(self._history)
        if event_type:
            events = [event for event in events if event.get("type") == event_type]
        return events[-limit:]

    def stats(self) -> dict[str, Any]:
        return {
            "port": self._port,
            "state_count": len(self._state),
            "history_count": len(self._history),
            "subscriptions_count": len(self._subscriptions),
            "listening": self._server is not None,
        }

    def _event_to_resource_uri(self, event_type: str, data: dict[str, Any]) -> str | None:
        path = data.get("path", "")
        if event_type == "chop_change":
            channel = data.get("channel", "")
            if path and channel:
                return chop_uri(path, channel)
        elif event_type == "par_change":
            name = data.get("name", "")
            if path and name:
                return par_uri(path, name)
        elif event_type == "cook_complete":
            if path:
                return cook_uri(path)
        elif event_type == "node_error":
            if path:
                return error_uri(path)
        elif event_type == "timeline":
            return "td://timeline/state"
        return None
