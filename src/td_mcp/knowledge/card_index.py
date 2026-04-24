"""CardIndex — loads, indexes, and searches structured JSON knowledge cards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Map card subdirectory names to the key field used for exact lookup.
_KEY_FIELDS = {
    "operators": "op_type",
    "palette": "component_name",
    "release": "build",
    "snippets": "snippet_id",
}


class CardIndex:
    """In-memory index of JSON knowledge cards organised by type.

    Directory layout expected::

        cards_dir/
            operators/   *.json  keyed by op_type
            palette/     *.json  keyed by component_name
            release/     *.json  keyed by build
            snippets/    *.json  keyed by snippet_id
    """

    def __init__(self, cards_dir: str | Path) -> None:
        self._cards_dir = Path(cards_dir)
        # Each bucket maps key_value -> card dict
        self._buckets: dict[str, dict[str, dict]] = {
            "operators": {},
            "palette": {},
            "release": {},
            "snippets": {},
        }
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        for subdir, key_field in _KEY_FIELDS.items():
            directory = self._cards_dir / subdir
            if not directory.is_dir():
                continue
            for json_file in sorted(directory.glob("*.json")):
                try:
                    card = json.loads(json_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                key = card.get(key_field)
                if key:
                    self._buckets[subdir][str(key)] = card

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Total number of loaded cards across all types."""
        return sum(len(b) for b in self._buckets.values())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        card_types: list[str] | None = None,
        family: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Simple text search with field-specific boosting.

        Boost order: key field (op_type / component_name) > display_name > summary.
        """
        query_lower = query.lower()
        results: list[tuple[float, dict]] = []

        buckets_to_search = (
            {ct: self._buckets[ct] for ct in card_types if ct in self._buckets}
            if card_types
            else self._buckets
        )

        for bucket_name, bucket in buckets_to_search.items():
            key_field = _KEY_FIELDS.get(bucket_name, "")
            for card in bucket.values():
                # Optional family filter
                if family and card.get("family", "").upper() != family.upper():
                    continue

                score = self._score_card(card, query_lower, key_field)
                if score > 0:
                    results.append((score, card))

        results.sort(key=lambda t: t[0], reverse=True)
        return [card for _, card in results[:limit]]

    @staticmethod
    def _score_card(card: dict, query_lower: str, key_field: str) -> float:
        score = 0.0
        # Primary key field (highest boost)
        key_val = str(card.get(key_field, "")).lower()
        if query_lower in key_val:
            score += 10.0

        # display_name (medium boost)
        display = str(card.get("display_name", "")).lower()
        if query_lower in display:
            score += 5.0

        # summary (low boost)
        summary = str(card.get("summary", "")).lower()
        if query_lower in summary:
            score += 1.0

        return score

    # ------------------------------------------------------------------
    # Exact lookups
    # ------------------------------------------------------------------

    def get_operator(self, op_type: str) -> dict | None:
        """Exact lookup by op_type. Returns None if not found."""
        return self._buckets["operators"].get(op_type)

    def get_palette(self, component_name: str) -> dict | None:
        """Exact lookup by component_name. Returns None if not found."""
        return self._buckets["palette"].get(component_name)

    def get_release(self, build: str) -> dict | None:
        """Exact lookup by build string. Returns None if not found."""
        return self._buckets["release"].get(build)

    # ------------------------------------------------------------------
    # Compatibility check
    # ------------------------------------------------------------------

    def check_compatibility(self, op_type: str, current_build: str) -> dict[str, Any]:
        """Compare an operator card's build_relevance against a build string.

        Returns ``{"status": "compatible"|"caution"|"incompatible", "reason": "..."}``.
        """
        card = self.get_operator(op_type)
        if card is None:
            return {
                "status": "caution",
                "reason": f"No card found for operator '{op_type}'.",
            }

        relevance = card.get("build_relevance", "")
        if not relevance:
            return {
                "status": "caution",
                "reason": "Card has no build_relevance field.",
            }

        try:
            min_build = self._parse_build(relevance)
            cur_build = self._parse_build(current_build)
        except ValueError:
            return {
                "status": "caution",
                "reason": f"Cannot parse build strings: relevance='{relevance}', current='{current_build}'.",
            }

        if cur_build >= min_build:
            return {
                "status": "compatible",
                "reason": f"Build {current_build} meets minimum {relevance}.",
            }
        else:
            return {
                "status": "incompatible",
                "reason": f"Build {current_build} is below minimum {relevance}.",
            }

    @staticmethod
    def _parse_build(build_str: str) -> int:
        """Extract a numeric build number from strings like '2025.30000+' or '2025.32460.0'."""
        cleaned = build_str.replace("+", "").strip()
        # Try to parse the part after the dot as the build number
        if "." in cleaned:
            parts = cleaned.split(".")
            # Take only major.minor, ignore patch (e.g. "2025.32460.0")
            return int(parts[0]) * 100000 + int(parts[1])
        return int(cleaned)
