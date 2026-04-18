"""Periodic TOP capture monitor."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from td_mcp.events.uri import top_frame_uri


class VisualMonitor:
    """Runs background capture loops and publishes latest frame resources."""

    def __init__(self, td_client, event_manager):
        self._td_client = td_client
        self._event_manager = event_manager
        self._tasks: dict[str, asyncio.Task] = {}
        self._configs: dict[str, dict[str, Any]] = {}

    def active_monitors(self) -> dict[str, dict[str, Any]]:
        return dict(self._configs)

    async def start_monitor(
        self,
        *,
        path: str,
        interval: float = 2.0,
        quality: float = 0.3,
        include_image: bool = False,
    ) -> dict[str, Any]:
        await self.stop_monitor(path)
        config = {
            "path": path,
            "interval": interval,
            "quality": quality,
            "include_image": bool(include_image),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._configs[path] = config
        self._tasks[path] = asyncio.create_task(self._run(path))
        return config

    async def stop_monitor(self, path: str) -> bool:
        task = self._tasks.pop(path, None)
        self._configs.pop(path, None)
        if not task:
            return False
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return True

    async def stop(self) -> None:
        for path in list(self._tasks.keys()):
            await self.stop_monitor(path)

    async def _run(self, path: str) -> None:
        while path in self._configs:
            config = self._configs[path]
            interval = float(config.get("interval", 2.0))
            quality = float(config.get("quality", 0.3))
            include_image = bool(config.get("include_image", False))
            try:
                screenshot = await self._td_client.request(
                    "screenshot",
                    {"path": path, "quality": quality},
                )
                payload = {
                    "frame_schema_version": 1,
                    "path": path,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "image": self._prepare_image_payload(screenshot, include_image=include_image),
                }
                uri = top_frame_uri(path)
                await self._event_manager.set_state(uri, payload, notify=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                uri = top_frame_uri(path)
                await self._event_manager.set_state(
                    uri,
                    {
                        "frame_schema_version": 1,
                        "path": path,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "error": str(exc),
                    },
                    notify=True,
                )
            await asyncio.sleep(max(0.1, interval))

    def _prepare_image_payload(self, screenshot: dict[str, Any], *, include_image: bool) -> dict[str, Any]:
        if include_image:
            return screenshot

        payload = dict(screenshot)
        omitted: list[str] = []
        for key in ("data_base64", "data_uri", "raw"):
            if key in payload:
                payload.pop(key, None)
                omitted.append(key)

        payload["image_omitted"] = True
        if omitted:
            payload["omitted_fields"] = omitted
        payload.setdefault(
            "note",
            "Base64 image omitted to reduce token usage. Ask user before enabling include_image=true.",
        )
        return payload
