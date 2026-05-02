"""Pack loading + schema validation for hints.

Pack schema (YAML):

    schema_version: 1                # int, required
    topic: feedback                  # str, required for topic packs
    op_types: [feedbackTOP]          # list[str], optional
    hints:                            # list, required
      - id: feedback_canonical_chain         # str, required (unique within pack)
        priority: critical|useful|context    # str, required
        rule: |                              # str, required (multiline ok)
          ...rule body...
        source: tdpilot-core §11             # str, required (citation)
        source_kind: skill_pitfall           # str, required
        when:                                # dict, optional auto-trigger spec
          op_type: feedbackTOP
          error_match: "Not enough sources"
          intent_match: "decay|trail|fade"
    next_tools: [td_get_param_help]  # list[str], optional

Source kinds recognized today: skill_pitfall, user_essay, official_doc,
hint_pack. Unknown values are accepted and surfaced verbatim in responses.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


PRIORITY_RANK = {"critical": 0, "useful": 1, "context": 2}
VALID_PRIORITIES = frozenset(PRIORITY_RANK.keys())
PACK_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Hint:
    """A single rule entry within a pack."""

    id: str
    priority: str
    rule: str
    source: str
    source_kind: str
    pack_id: str
    pack_kind: str  # "topic" | "op_type"
    pack_topic: str | None = None
    pack_op_types: tuple[str, ...] = field(default_factory=tuple)
    when: dict[str, Any] = field(default_factory=dict)
    next_tools: tuple[str, ...] = field(default_factory=tuple)

    def as_response_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority,
            "rule": self.rule.strip(),
            "source": self.source,
            "source_kind": self.source_kind,
        }


@dataclass(frozen=True)
class HintMatch:
    hint: Hint
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class HintPack:
    pack_id: str
    pack_kind: str
    topic: str | None
    op_types: tuple[str, ...]
    hints: tuple[Hint, ...]
    next_tools: tuple[str, ...]
    schema_version: int


def _coerce_str_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(x).strip() for x in value if str(x).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _validate_hint_dict(raw: Any, pack_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"hint in pack {pack_id!r} is not a mapping: {type(raw).__name__}")
    for required in ("id", "priority", "rule", "source", "source_kind"):
        if not raw.get(required):
            raise ValueError(f"hint in pack {pack_id!r} missing required field {required!r}")
    if raw["priority"] not in VALID_PRIORITIES:
        raise ValueError(
            f"hint {raw['id']!r} in pack {pack_id!r} has invalid priority "
            f"{raw['priority']!r}; allowed: {sorted(VALID_PRIORITIES)}"
        )
    return raw


def _parse_pack(path: Path, pack_kind: str) -> HintPack:
    """Parse one YAML pack from disk. Raises ``ValueError`` on schema failure."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"pack {path.name!r} is not a YAML mapping")
    schema_version = int(raw.get("schema_version", 0))
    if schema_version != PACK_SCHEMA_VERSION:
        raise ValueError(
            f"pack {path.name!r} schema_version={schema_version} (expected {PACK_SCHEMA_VERSION})"
        )

    pack_id = path.stem
    topic = raw.get("topic") if pack_kind == "topic" else None
    op_types = _coerce_str_list(raw.get("op_types"))
    pack_next_tools = _coerce_str_list(raw.get("next_tools"))
    raw_hints = raw.get("hints") or []
    if not isinstance(raw_hints, list):
        raise ValueError(f"pack {path.name!r} 'hints' must be a list")

    hints: list[Hint] = []
    seen_ids: set[str] = set()
    for entry in raw_hints:
        validated = _validate_hint_dict(entry, pack_id)
        if validated["id"] in seen_ids:
            raise ValueError(
                f"pack {pack_id!r} contains duplicate hint id {validated['id']!r}"
            )
        seen_ids.add(validated["id"])
        when = validated.get("when") or {}
        if when and not isinstance(when, dict):
            raise ValueError(
                f"hint {validated['id']!r} in pack {pack_id!r} has non-mapping 'when'"
            )
        next_tools = _coerce_str_list(validated.get("next_tools"))
        hints.append(
            Hint(
                id=validated["id"],
                priority=validated["priority"],
                rule=str(validated["rule"]),
                source=str(validated["source"]),
                source_kind=str(validated["source_kind"]),
                pack_id=pack_id,
                pack_kind=pack_kind,
                pack_topic=topic if isinstance(topic, str) else None,
                pack_op_types=op_types,
                when=dict(when),
                next_tools=next_tools,
            )
        )

    return HintPack(
        pack_id=pack_id,
        pack_kind=pack_kind,
        topic=topic if isinstance(topic, str) else None,
        op_types=op_types,
        hints=tuple(hints),
        next_tools=pack_next_tools,
        schema_version=schema_version,
    )


def _scan_dir(packs_root: Path, pack_kind: str) -> list[HintPack]:
    sub = packs_root / f"{pack_kind}s"
    if not sub.exists():
        return []
    out: list[HintPack] = []
    for path in sorted(sub.glob("*.yaml")):
        try:
            out.append(_parse_pack(path, pack_kind))
        except Exception as exc:
            logger.warning("Skipping malformed hint pack %s: %s", path, exc)
    return out


class HintRegistry:
    """In-memory query API over the loaded hint packs.

    Single-process / single-threaded usage assumed (mirrors the rest of
    the MCP server). Reload-from-disk is supported but explicit — callers
    own the lifecycle.
    """

    def __init__(self, packs_root: Path | None = None) -> None:
        if packs_root is None:
            packs_root = Path(__file__).resolve().parent / "packs"
        self._packs_root = packs_root
        self._topic_packs: list[HintPack] = []
        self._op_type_packs: list[HintPack] = []
        self._all_hints: list[Hint] = []
        self._loaded = False
        self.pack_version = "v1.6.0-1"

    @property
    def packs_root(self) -> Path:
        return self._packs_root

    def reload(self) -> "HintRegistry":
        self._topic_packs = _scan_dir(self._packs_root, "topic")
        self._op_type_packs = _scan_dir(self._packs_root, "op_type")
        self._all_hints = []
        for pack in (*self._topic_packs, *self._op_type_packs):
            self._all_hints.extend(pack.hints)
        self._loaded = True
        return self

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    def all_hints(self) -> list[Hint]:
        self._ensure_loaded()
        return list(self._all_hints)

    def topics(self) -> list[str]:
        self._ensure_loaded()
        return sorted({pack.topic for pack in self._topic_packs if pack.topic})

    def op_types(self) -> list[str]:
        self._ensure_loaded()
        seen: set[str] = set()
        for pack in self._op_type_packs:
            for ot in pack.op_types:
                seen.add(ot)
        return sorted(seen)

    def find(
        self,
        *,
        topic: str | None = None,
        op_type: str | None = None,
        intent: str | None = None,
        error_text: str | None = None,
        node_path: str | None = None,
    ) -> list[HintMatch]:
        """Score every hint and return matches sorted by priority then score.

        Each candidate hint accumulates a score from:
          * topic match (+3.0)
          * op_type match in pack metadata (+2.0)
          * op_type match in hint.when.op_type (+2.0)
          * error_match substring inside hint.when.error_match (+2.0)
          * intent_match substring inside hint.when.intent_match (+1.5)

        Hints with no positive signal are filtered out unless they're in
        the same pack as a matched hint AND topic/op_type was requested
        (covers the "give me the feedback pack" intent without spam).
        """
        self._ensure_loaded()
        topic_l = topic.strip().lower() if topic else None
        op_type_l = op_type.strip() if op_type else None
        intent_l = intent.strip().lower() if intent else None
        error_l = error_text.strip().lower() if error_text else None

        matches: list[HintMatch] = []
        for hint in self._all_hints:
            score = 0.0
            reasons: list[str] = []

            if topic_l and hint.pack_topic and hint.pack_topic.lower() == topic_l:
                score += 3.0
                reasons.append("topic")

            if op_type_l:
                if op_type_l in hint.pack_op_types:
                    score += 2.0
                    reasons.append("pack_op_type")
                when_op = hint.when.get("op_type") if isinstance(hint.when, dict) else None
                if when_op and when_op == op_type_l:
                    score += 2.0
                    reasons.append("when_op_type")

            if error_l and isinstance(hint.when, dict):
                when_err = hint.when.get("error_match")
                if isinstance(when_err, str) and when_err and when_err.lower() in error_l:
                    score += 2.0
                    reasons.append("error_match")

            if intent_l and isinstance(hint.when, dict):
                when_int = hint.when.get("intent_match")
                if isinstance(when_int, str) and when_int:
                    pattern = when_int.lower()
                    matched = False
                    if pattern in intent_l:
                        matched = True
                    else:
                        try:
                            if re.search(pattern, intent_l):
                                matched = True
                        except re.error:
                            pass
                    if matched:
                        score += 1.5
                        reasons.append("intent_match")

            if score > 0:
                matches.append(HintMatch(hint=hint, score=score, reasons=tuple(reasons)))

        # Bring in pack-mates of strongly-matched topic/op_type hints with a small
        # baseline score so a "give me the feedback pack" query returns the
        # whole pack rather than only the strict-matched rules.
        if topic_l or op_type_l:
            matched_pack_ids = {m.hint.pack_id for m in matches}
            existing_ids = {(m.hint.pack_id, m.hint.id) for m in matches}
            for hint in self._all_hints:
                if hint.pack_id not in matched_pack_ids:
                    continue
                if (hint.pack_id, hint.id) in existing_ids:
                    continue
                matches.append(
                    HintMatch(hint=hint, score=0.5, reasons=("pack_mate",))
                )

        matches.sort(
            key=lambda m: (
                PRIORITY_RANK.get(m.hint.priority, 99),
                -m.score,
                m.hint.id,
            )
        )
        return matches


_DEFAULT: HintRegistry | None = None


def default_registry() -> HintRegistry:
    """Return the process-wide default registry, lazy-loading on first call."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = HintRegistry().reload()
    return _DEFAULT
