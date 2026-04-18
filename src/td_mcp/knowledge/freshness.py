"""Provenance tracking and freshness scoring for knowledge cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class Provenance:
    """Track the origin and freshness of a knowledge card.

    Confidence levels:
    - "verified"   — last_verified is within the last 90 days
    - "stale"      — last_verified is older than 90 days
    - "unverified" — no last_verified date provided
    """

    source: str = "local_card"
    fetched_at: str | None = None
    last_verified: str = ""
    td_build: str = ""
    confidence: str = ""

    def __post_init__(self) -> None:
        if not self.confidence:
            self.confidence = self._compute_confidence()

    def _compute_confidence(self) -> str:
        if not self.last_verified:
            return "unverified"
        try:
            verified_date = datetime.fromisoformat(self.last_verified)
            # Make both dates timezone-aware for comparison
            now = datetime.now(timezone.utc)
            if verified_date.tzinfo is None:
                verified_date = verified_date.replace(tzinfo=timezone.utc)
            delta = now - verified_date
            if delta.days <= 90:
                return "verified"
            return "stale"
        except (ValueError, TypeError):
            return "unverified"

    def to_dict(self) -> dict:
        """Return all fields as a plain dict."""
        return asdict(self)
