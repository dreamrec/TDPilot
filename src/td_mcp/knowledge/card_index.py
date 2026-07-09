"""CardIndex — loads, indexes, and searches structured JSON knowledge cards.

This is the compact default retrieval path (no downloads). When the optional
FTS5 DocsBrain database is present locally, ``tool_registry`` loads DocsBrain
instead and this index is only its fallback — see the brain-selection logic in
``td_mcp.tool_registry`` (DocsBrain if ``docsbrain.db`` exists, else
CardIndex). Multi-token queries here use OR-matching with an AND boost, with
query-side synonym expansion (``td_mcp.knowledge.synonyms``) in front of
tokenization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from td_mcp.knowledge.synonyms import expand_query_tokens

# Map card subdirectory names to the key field used for exact lookup.
_KEY_FIELDS = {
    "operators": "op_type",
    "palette": "component_name",
    "release": "build",
    "snippets": "snippet_id",
    "articles": "article_id",
}


class CardIndex:
    """In-memory index of JSON knowledge cards organised by type.

    Directory layout expected::

        cards_dir/
            operators/   *.json  keyed by op_type
            palette/     *.json  keyed by component_name
            release/     *.json  keyed by build
            snippets/    *.json  keyed by snippet_id
            articles/    *.json  keyed by article_id
    """

    def __init__(self, cards_dir: str | Path) -> None:
        self._cards_dir = Path(cards_dir)
        # Each bucket maps key_value -> card dict
        self._buckets: dict[str, dict[str, dict]] = {
            "operators": {},
            "palette": {},
            "release": {},
            "snippets": {},
            "articles": {},
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
                # Optional family filter. Snippet cards can be cross-family
                # guides (for example GLSL snippets that cover GLSL POP), so
                # allow reviewed nested metadata to opt into related families.
                if family and not self._matches_family(card, family):
                    continue

                score = self._score_card(card, query_lower, key_field)
                if score > 0:
                    results.append((score, card))

        results.sort(key=lambda t: t[0], reverse=True)
        return [card for _, card in results[:limit]]

    @staticmethod
    def _score_card(card: dict, query_lower: str, key_field: str) -> float:
        """Field-boosted relevance score.

        Ranking (per field): exact phrase > all token groups (AND boost) >
        per-group OR hits. A token group is the query token plus its synonym
        aliases — any variant appearing in the text counts as a hit for that
        group, so "glow" retrieves bloom cards and "sound" retrieves audio
        cards without the FTS5 download.
        """
        score = 0.0
        query_tokens = [token for token in query_lower.replace("_", " ").split() if token]
        token_groups = expand_query_tokens(query_tokens)

        def _field_score(text: str, phrase_pts: float, and_pts: float, or_pts: float) -> float:
            if query_lower in text:
                return phrase_pts
            if not token_groups:
                return 0.0
            hits = sum(1 for group in token_groups if any(variant in text for variant in group))
            if hits == len(token_groups):
                return and_pts
            return or_pts * hits

        # Primary key field (highest boost)
        key_val = str(card.get(key_field, "")).lower()
        score += _field_score(key_val, 10.0, 8.0, 1.5)

        # display_name (medium boost)
        display = str(card.get("display_name", "")).lower()
        score += _field_score(display, 5.0, 4.0, 0.75)

        # summary (low boost)
        summary = str(card.get("summary", "")).lower()
        score += _field_score(summary, 1.0, 0.75, 0.15)

        nested_text = CardIndex._nested_search_text(card)
        if query_lower in nested_text:
            score += 0.75
        elif token_groups:
            matched_groups = sum(
                1 for group in token_groups if any(variant in nested_text for variant in group)
            )
            if matched_groups == len(token_groups):
                score += 0.5 + (0.05 * matched_groups)
            elif matched_groups:
                score += 0.03 * matched_groups

        return score

    @staticmethod
    def _nested_search_text(value: Any) -> str:
        strings: list[str] = []

        def visit(item: Any) -> None:
            if isinstance(item, str):
                strings.append(item.lower())
            elif isinstance(item, dict):
                for nested in item.values():
                    visit(nested)
            elif isinstance(item, list):
                for nested in item:
                    visit(nested)

        visit(value)
        return " ".join(strings)

    @staticmethod
    def _matches_family(card: dict, family: str) -> bool:
        target = family.upper()
        families: set[str] = set()

        def add(value: Any) -> None:
            if isinstance(value, str) and value.strip():
                families.add(value.strip().upper())
            elif isinstance(value, list):
                for item in value:
                    add(item)

        add(card.get("family"))
        add(card.get("families"))
        add(card.get("related_families"))
        for collection_key in ("official_examples", "templates"):
            collection = card.get(collection_key, [])
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict):
                    continue
                add(item.get("family"))
                add(item.get("families"))
                for op_type in item.get("operators", []):
                    family_suffix = CardIndex._family_from_op_type(op_type)
                    if family_suffix:
                        families.add(family_suffix)
                op_type = item.get("op_type")
                family_suffix = CardIndex._family_from_op_type(op_type)
                if family_suffix:
                    families.add(family_suffix)

        return target in families

    @staticmethod
    def _family_from_op_type(op_type: Any) -> str | None:
        if not isinstance(op_type, str):
            return None
        for suffix in ("COMP", "CHOP", "SOP", "TOP", "DAT", "MAT", "POP"):
            if op_type.upper().endswith(suffix):
                return suffix
        return None

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

    def get_article(self, article_id: str) -> dict | None:
        """Exact lookup by article_id. Returns None if not found."""
        return self._buckets["articles"].get(article_id)

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
