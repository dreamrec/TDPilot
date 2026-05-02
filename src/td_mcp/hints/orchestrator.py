"""Hint query API + auto-injection rule table.

This module is the *only* public surface most callers should touch:

    from td_mcp.hints import query_hints, auto_inject_hints

``query_hints`` is what ``td_get_hints`` is built on top of. ``auto_inject_hints``
is what the high-risk-tool wrappers call to decide whether to attach hints to
a tool response without the caller asking for them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from td_mcp.hints.loader import HintMatch, default_registry


# Auto-injection rules, keyed by tool name. Each rule is a callable that
# inspects the request payload + response and returns a (topic, op_type,
# intent_text, error_text, reason) tuple when injection should fire, or
# None otherwise.
#
# Keep these patterns LITERAL and SAFE to match — no eval, no string
# concatenation that could leak request payloads back into the response.
@dataclass(frozen=True)
class _AutoTrigger:
    tool: str
    detector: Any  # callable(payload, response) -> dict | None


def _trigger_create_node(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    op_type = (
        payload.get("type")
        or payload.get("op_type")
        or payload.get("node_type")
        or ""
    ).strip()
    if not op_type:
        return None
    risky = {
        "feedbackTOP",
        "feedbackEdgeTOP",
        "glslTOP",
        "glslMAT",
        "moviefileoutTOP",
        "extensionDAT",
        "panelCOMP",
        "geometryCOMP",
        "audiofileinCHOP",
    }
    if op_type in risky:
        return {
            "op_type": op_type,
            "reason": f"op_type={op_type}",
        }
    return None


_REFERENCE_PARAM_NAMES = re.compile(
    r"^(instanceop|material|camera|lights|geometry|top|chop|sop|dat|comp|cameras|geometries)$",
    re.IGNORECASE,
)


def _trigger_set_params(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return None
    for name, value in params.items():
        if not isinstance(name, str):
            continue
        if not _REFERENCE_PARAM_NAMES.match(name.strip()):
            continue
        if isinstance(value, str) and value.strip():
            return {
                "topic": "render_pipeline",
                "intent": f"set parameter {name} to a string reference",
                "reason": f"reference-style param '{name}' assigned a string value",
            }
    return None


_RESTRICTED_HINTS_PATTERNS = (
    "import ",
    "open(",
    "subprocess",
    "socket",
    "__import__",
    ".text=",
    ".par.file=",
)


def _trigger_exec_python(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    code = payload.get("code") or ""
    if not isinstance(code, str):
        return None
    code_lower = code.lower()
    for pat in _RESTRICTED_HINTS_PATTERNS:
        if pat.lower() in code_lower:
            return {
                "topic": "render_pipeline",
                "intent": "execute python; possible restricted-mode violation",
                "reason": f"code contains pattern {pat!r}",
            }
    return None


def _trigger_get_errors(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    text = ""
    if isinstance(response, dict):
        for key in ("errors", "warnings", "messages", "text"):
            value = response.get(key)
            if isinstance(value, str):
                text += value + "\n"
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        text += item + "\n"
                    elif isinstance(item, dict):
                        msg = item.get("message") or item.get("error") or item.get("text")
                        if isinstance(msg, str):
                            text += msg + "\n"
    text = text.strip()
    if not text:
        return None
    triggers = [
        ("Not enough sources", "feedbackTOP", "feedback"),
        ("missing input", None, "render_pipeline"),
        ("extension", "extensionDAT", "extensions"),
    ]
    text_lower = text.lower()
    for needle, op_type, topic in triggers:
        if needle.lower() in text_lower:
            return {
                "op_type": op_type,
                "topic": topic,
                "error_text": text[:500],
                "reason": f"detected error pattern {needle!r}",
            }
    return None


def _trigger_planning(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    blob = ""
    for source in (payload, response):
        if not isinstance(source, dict):
            continue
        for value in source.values():
            if isinstance(value, str):
                blob += value + "\n"
    blob_lower = blob.lower()
    keywords = [
        ("feedback", "feedbackTOP", "feedback"),
        ("glsl", "glslTOP", "glsl"),
        ("audio", None, "audio_reactive"),
    ]
    for needle, op_type, topic in keywords:
        if needle in blob_lower:
            return {
                "op_type": op_type,
                "topic": topic,
                "intent": needle,
                "reason": f"plan/preview blob mentions {needle!r}",
            }
    return None


AUTO_INJECT_RULES: dict[str, Any] = {
    "td_create_node": _trigger_create_node,
    "td_set_params": _trigger_set_params,
    "td_exec_python": _trigger_exec_python,
    "td_get_errors": _trigger_get_errors,
    "td_plan_patch": _trigger_planning,
    "td_patch_preview": _trigger_planning,
}


def query_hints(
    *,
    topic: str | None = None,
    op_type: str | None = None,
    intent: str | None = None,
    node_path: str | None = None,
    error_text: str | None = None,
    max_hints: int = 8,
) -> dict[str, Any]:
    """Return hints + metadata in the shape ``td_get_hints`` exposes."""
    registry = default_registry()
    matches: list[HintMatch] = registry.find(
        topic=topic,
        op_type=op_type,
        intent=intent,
        error_text=error_text,
        node_path=node_path,
    )
    selected = matches[: max(1, min(max_hints, 20))] if matches else []
    response_hints = []
    next_tools: list[str] = []
    for m in selected:
        response_hints.append(m.hint.as_response_dict())
        for nt in m.hint.next_tools:
            if nt not in next_tools:
                next_tools.append(nt)
    confidence = 0.0
    if selected:
        max_score = max(m.score for m in selected) or 1.0
        confidence = min(1.0, max_score / 5.0)
    return {
        "topic": topic,
        "op_type": op_type,
        "confidence": round(confidence, 2),
        "hints": response_hints,
        "next_tools": next_tools,
        "hint_pack_version": registry.pack_version,
        "available_topics": registry.topics(),
        "available_op_types": registry.op_types(),
    }


def auto_inject_hints(
    tool_name: str,
    payload: dict[str, Any] | None,
    response: Any,
    *,
    max_hints: int = 4,
) -> dict[str, Any] | None:
    """Decide whether to attach hints to a tool response without the caller asking.

    Returns ``None`` when no auto-trigger fires; otherwise returns the
    ``hints`` block that the high-risk-tool wrapper should merge into the
    response.

    Defensive: any exception inside the detector is swallowed (returning
    ``None``) so a buggy hint pattern can never break a tool call.
    """
    detector = AUTO_INJECT_RULES.get(tool_name)
    if detector is None:
        return None
    try:
        signal = detector(payload or {}, response if isinstance(response, dict) else {})
    except Exception:
        return None
    if not signal:
        return None
    try:
        result = query_hints(
            topic=signal.get("topic"),
            op_type=signal.get("op_type"),
            intent=signal.get("intent"),
            error_text=signal.get("error_text"),
            max_hints=max_hints,
        )
    except Exception:
        return None
    if not result.get("hints"):
        return None
    return {
        "auto_triggered": True,
        "trigger_reason": signal.get("reason"),
        "items": result["hints"],
        "next_tools": result.get("next_tools", []),
        "hint_pack_version": result.get("hint_pack_version"),
    }
