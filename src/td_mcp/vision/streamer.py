"""Continuous TOP frame streaming manager."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

from td_mcp.events.uri import top_frame_uri


class TopStreamer:
    """Runs higher-rate TOP capture loops and publishes frame resources."""

    def __init__(self, td_client, event_manager, max_fps: float = 15.0):
        self._td_client = td_client
        self._event_manager = event_manager
        self._max_fps = max(0.5, float(max_fps))
        self._tasks: dict[str, asyncio.Task] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._last_hash: dict[str, str] = {}
        self._stats: dict[str, int] = {
            "emitted": 0,
            "dropped_unchanged": 0,
            "errors": 0,
        }

    def active_streams(self) -> dict[str, dict[str, Any]]:
        return dict(self._configs)

    def stats(self) -> dict[str, Any]:
        return {
            "max_fps": self._max_fps,
            "active_count": len(self._configs),
            "emitted": self._stats["emitted"],
            "dropped_unchanged": self._stats["dropped_unchanged"],
            "errors": self._stats["errors"],
        }

    async def start_stream(
        self,
        *,
        path: str,
        fps: float = 8.0,
        quality: float = 0.25,
        include_image: bool = False,
        emit_unchanged: bool = False,
    ) -> dict[str, Any]:
        await self.stop_stream(path)
        normalized_fps = max(0.5, min(float(fps), self._max_fps))
        config = {
            "path": path,
            "fps": normalized_fps,
            "quality": float(quality),
            "include_image": bool(include_image),
            "emit_unchanged": bool(emit_unchanged),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self._configs[path] = config
        self._tasks[path] = asyncio.create_task(self._run(path))
        return config

    async def stop_stream(self, path: str) -> bool:
        task = self._tasks.pop(path, None)
        self._configs.pop(path, None)
        self._last_hash.pop(path, None)
        if not task:
            return False
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return True

    async def stop(self) -> None:
        for path in list(self._tasks.keys()):
            await self.stop_stream(path)

    async def _run(self, path: str) -> None:
        while path in self._configs:
            config = self._configs[path]
            fps = max(0.5, float(config.get("fps", 8.0)))
            interval = max(0.01, 1.0 / fps)
            quality = float(config.get("quality", 0.25))
            include_image = bool(config.get("include_image", False))
            emit_unchanged = bool(config.get("emit_unchanged", False))

            try:
                screenshot = await self._td_client.request(
                    "screenshot",
                    {"path": path, "quality": quality},
                )
                frame_hash = self._frame_hash(screenshot)

                if not emit_unchanged and frame_hash is not None and self._last_hash.get(path) == frame_hash:
                    self._stats["dropped_unchanged"] += 1
                else:
                    if frame_hash is not None:
                        self._last_hash[path] = frame_hash
                    payload = {
                        "frame_schema_version": 2,
                        "path": path,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "stream": {
                            "mode": "continuous",
                            "fps": fps,
                            "quality": quality,
                            "include_image": include_image,
                            "emit_unchanged": emit_unchanged,
                        },
                        "image": self._prepare_image_payload(
                            screenshot,
                            include_image=include_image,
                            frame_hash=frame_hash,
                        ),
                    }
                    await self._event_manager.set_state(top_frame_uri(path), payload, notify=True)
                    self._stats["emitted"] += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._stats["errors"] += 1
                await self._event_manager.set_state(
                    top_frame_uri(path),
                    {
                        "frame_schema_version": 2,
                        "path": path,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "stream": {
                            "mode": "continuous",
                            "fps": fps,
                            "quality": quality,
                            "include_image": include_image,
                            "emit_unchanged": emit_unchanged,
                        },
                        "error": str(exc),
                    },
                    notify=True,
                )

            await asyncio.sleep(interval)

    def _frame_hash(self, screenshot: dict[str, Any]) -> str | None:
        data = screenshot.get("data_base64")
        if not isinstance(data, str):
            return None
        return hashlib.sha1(data.encode("ascii", errors="ignore")).hexdigest()

    def _prepare_image_payload(
        self,
        screenshot: dict[str, Any],
        *,
        include_image: bool,
        frame_hash: str | None,
    ) -> dict[str, Any]:
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
        if frame_hash is not None:
            payload["frame_hash"] = frame_hash
        payload.setdefault(
            "note",
            "Base64 image omitted to reduce token usage. Ask user before enabling include_image=true.",
        )
        return payload
