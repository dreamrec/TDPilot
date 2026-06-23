"""Local corpus bridge for grounding BrainPlans in cited TD docs facts."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from td_mcp.models.brain import CorpusEvidenceRecord, DataDomain

OFFICIAL_DERIVATIVE_DOCS_PREFIX = "https://docs.derivative.ca/"
_VECTOR_DIMS = 64
_FAMILY_SUFFIXES = ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP")
_SOURCE_MARKERS = {
    "exact_operator": "exact",
    "docs_search": "search",
}


def build_corpus_evidence(
    *,
    intent: str,
    operators: list[str],
    card_index,
    limit_per_query: int = 8,
    max_records: int = 24,
) -> list[CorpusEvidenceRecord]:
    """Return deterministic, cited corpus evidence for selected plan operators.

    The bridge deliberately stays local-first: exact operator lookup provides
    authoritative docs cards, search provides broader corpus recall when the
    backend supports it, and a small stable hashed-vector score reranks records
    without requiring hosted embedding services.
    """
    if card_index is None:
        return []

    selected_ops = _dedupe([str(op_type) for op_type in operators if str(op_type).strip()])
    records: dict[str, CorpusEvidenceRecord] = {}

    for op_type in selected_ops:
        card = _safe_get_operator(card_index, op_type)
        record = _record_from_card(
            card,
            source="exact_operator",
            intent=intent,
            query=op_type,
            preferred_op_type=op_type,
        )
        _upsert_record(records, record)

    if hasattr(card_index, "search"):
        for query in _search_queries(intent, selected_ops):
            for card in _safe_search(card_index, query, limit=limit_per_query):
                op_type = _extract_op_type(card)
                enriched = _merge_operator_card(
                    card, _safe_get_operator(card_index, op_type) if op_type else None
                )
                record = _record_from_card(
                    enriched,
                    source="docs_search",
                    intent=intent,
                    query=query,
                    preferred_op_type=op_type,
                )
                _upsert_record(records, record)

    return sorted(
        records.values(),
        key=lambda record: (-record.score, record.evidence_id),
    )[:max_records]


def corpus_evidence_markers(records: list[CorpusEvidenceRecord]) -> list[str]:
    """Return compact grounding markers for structured corpus records."""
    return [record.evidence_id for record in records]


def _upsert_record(records: dict[str, CorpusEvidenceRecord], record: CorpusEvidenceRecord | None) -> None:
    if record is None:
        return
    current = records.get(record.evidence_id)
    if current is None or record.score > current.score:
        records[record.evidence_id] = record


def _record_from_card(
    card: Any,
    *,
    source: str,
    intent: str,
    query: str,
    preferred_op_type: str | None = None,
) -> CorpusEvidenceRecord | None:
    if not isinstance(card, dict):
        return None
    docs_url = _official_docs_url(card)
    if not docs_url:
        return None
    op_type = preferred_op_type or _extract_op_type(card)
    display_name = str(card.get("display_name") or card.get("operator_name") or op_type or "").strip()
    summary = _compact_text(str(card.get("summary") or card.get("content") or ""))
    text = _card_text(card, op_type=op_type, display_name=display_name, summary=summary)
    score = _record_score(source=source, intent=intent, query=query, text=text)
    return CorpusEvidenceRecord(
        evidence_id=_evidence_id(source, op_type or display_name or docs_url),
        source=source,  # type: ignore[arg-type]
        op_type=op_type,
        family=_family_for(card, op_type),
        display_name=display_name,
        docs_url=docs_url,
        summary=summary,
        key_params=_key_param_names(card),
        key_concepts=_string_list(card.get("key_concepts"))[:8],
        matched_terms=_matched_terms(f"{intent} {query}", text),
        query=query,
        score=score,
    )


def _safe_get_operator(card_index, op_type: str | None) -> dict | None:
    if not op_type:
        return None
    try:
        card = card_index.get_operator(op_type)
    except Exception:
        return None
    return card if isinstance(card, dict) else None


def _safe_search(card_index, query: str, *, limit: int) -> list[dict]:
    try:
        hits = card_index.search(query, card_types=["operators"], limit=limit)
    except Exception:
        return []
    return [hit for hit in hits if isinstance(hit, dict)]


def _search_queries(intent: str, operators: list[str]) -> list[str]:
    queries = []
    if intent.strip():
        queries.append(" ".join([intent.strip(), *operators[:8]]))
    queries.extend(operators)
    return _dedupe(queries)


def _merge_operator_card(search_card: dict, exact_card: dict | None) -> dict:
    if exact_card is None:
        return search_card
    merged = dict(exact_card)
    for key, value in search_card.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def _extract_op_type(card: dict) -> str | None:
    value = card.get("op_type") or card.get("operator_type")
    if isinstance(value, str) and value.strip():
        return value.strip()
    name = card.get("operator_name")
    if isinstance(name, str) and name.strip():
        parts = name.split()
        if len(parts) >= 2 and parts[-1].upper() in _FAMILY_SUFFIXES:
            return "".join(part.lower() for part in parts[:-1]) + parts[-1].upper()
    return None


def _official_docs_url(card: dict) -> str:
    for key in ("docs_url", "source_url", "url", "href"):
        value = card.get(key)
        if isinstance(value, str) and value.startswith(OFFICIAL_DERIVATIVE_DOCS_PREFIX):
            return value
    return ""


def _key_param_names(card: dict) -> list[str]:
    params = []
    raw_params = card.get("key_params") or card.get("parameters") or []
    if not isinstance(raw_params, list):
        return []
    for item in raw_params:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                params.append(name.strip())
        elif isinstance(item, str) and item.strip():
            params.append(item.strip().splitlines()[-1])
    return _dedupe(params)[:12]


def _family_for(card: dict, op_type: str | None) -> DataDomain | None:
    raw_family = card.get("family") or card.get("operator_family")
    if isinstance(raw_family, str):
        family = raw_family.strip().upper()
        if family in _FAMILY_SUFFIXES:
            return family  # type: ignore[return-value]
    if op_type:
        for suffix in _FAMILY_SUFFIXES:
            if op_type.upper().endswith(suffix):
                return suffix  # type: ignore[return-value]
    return None


def _record_score(*, source: str, intent: str, query: str, text: str) -> float:
    semantic = _local_embedding_score(f"{intent} {query}", text)
    if source == "exact_operator":
        return round(min(1.0, 0.72 + (semantic * 0.28)), 4)
    return round(semantic, 4)


def _local_embedding_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0
    query_vec = _hashed_vector(query_tokens)
    text_vec = _hashed_vector(text_tokens)
    dot = sum(query_vec[index] * text_vec[index] for index in range(_VECTOR_DIMS))
    query_norm = math.sqrt(sum(value * value for value in query_vec))
    text_norm = math.sqrt(sum(value * value for value in text_vec))
    if query_norm == 0.0 or text_norm == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (query_norm * text_norm)))


def _hashed_vector(tokens: list[str]) -> list[float]:
    vector = [0.0] * _VECTOR_DIMS
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=2).digest()
        index = int.from_bytes(digest, "big") % _VECTOR_DIMS
        vector[index] += 1.0
    return vector


def _matched_terms(query: str, text: str) -> list[str]:
    text_tokens = set(_tokens(text))
    return [token for token in _dedupe(_tokens(query)) if token in text_tokens][:12]


def _card_text(card: dict, *, op_type: str | None, display_name: str, summary: str) -> str:
    parts = [op_type or "", display_name, summary]
    parts.extend(_key_param_names(card))
    parts.extend(_string_list(card.get("key_concepts")))
    parts.extend(_string_list(card.get("common_gotchas")))
    return " ".join(parts)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]


def _compact_text(text: str, *, limit: int = 360) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "."


def _evidence_id(source: str, identity: str) -> str:
    marker = _SOURCE_MARKERS.get(source, source)
    slug = re.sub(r"[^A-Za-z0-9_:-]+", "-", identity.strip()).strip("-") or "unknown"
    return f"corpus:{marker}:{slug}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


__all__ = ["build_corpus_evidence", "corpus_evidence_markers", "OFFICIAL_DERIVATIVE_DOCS_PREFIX"]
