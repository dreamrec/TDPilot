"""Process-wide sentinel that tracks whether a patch-apply undo block is
currently active. Injected into patch.applier.apply_plan by the MCP tool
wrapper. See spec §2.2 + §6.3.

The class lives in the MCP-free patch/ package so unit tests can
construct instances without any MCP plumbing. A single process-wide
instance is held in td_mcp.tool_registry (created lazily by the patch
tool wrapper).
"""

from __future__ import annotations


class UndoBlockSentinel:
    """Tracks whether our applier has an undo block open."""

    def __init__(self) -> None:
        self._active: str | None = None

    def is_active(self) -> bool:
        return self._active is not None

    def mark_active(self, label: str) -> None:
        if self._active is not None:
            raise RuntimeError(
                f"sentinel already active: {self._active!r}; caller must end the prior undo block first"
            )
        self._active = label

    def mark_inactive(self) -> None:
        self._active = None

    @property
    def active_label(self) -> str | None:
        return self._active
