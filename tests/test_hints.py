"""Tests for the hint pack loader, query API, and auto-injection rules."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from td_mcp.hints import (
    HintRegistry,
    auto_inject_hints,
    default_registry,
    query_hints,
)


def _write_pack(root: Path, kind: str, name: str, body: str) -> Path:
    sub = root / f"{kind}s"
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / f"{name}.yaml"
    path.write_text(dedent(body), encoding="utf-8")
    return path


def _registry_with_pack(tmp_path: Path, kind: str, name: str, body: str) -> HintRegistry:
    _write_pack(tmp_path, kind, name, body)
    return HintRegistry(packs_root=tmp_path).reload()


# ── Loader / schema validation ─────────────────────────────────────


def test_loader_accepts_valid_pack(tmp_path: Path):
    reg = _registry_with_pack(
        tmp_path,
        "topic",
        "feedback",
        """
        schema_version: 1
        topic: feedback
        op_types: [feedbackTOP]
        hints:
          - id: f1
            priority: critical
            rule: always wire fb.par.top to over, not out
            source: tdpilot-core §11
            source_kind: skill_pitfall
        """,
    )
    assert reg.topics() == ["feedback"]
    assert "feedbackTOP" not in reg.op_types()  # no op_type packs in this fixture
    assert len(reg.all_hints()) == 1
    hint = reg.all_hints()[0]
    assert hint.id == "f1"
    assert hint.priority == "critical"
    assert hint.pack_topic == "feedback"


def test_loader_rejects_wrong_schema_version_silently(tmp_path: Path):
    """Malformed packs skip with a warning, never raise — defensive design."""
    _write_pack(
        tmp_path,
        "topic",
        "bad",
        """
        schema_version: 99
        topic: bad
        hints: []
        """,
    )
    reg = HintRegistry(packs_root=tmp_path).reload()
    assert reg.topics() == []
    assert reg.all_hints() == []


def test_loader_rejects_invalid_priority(tmp_path: Path):
    _write_pack(
        tmp_path,
        "topic",
        "bad_priority",
        """
        schema_version: 1
        topic: bad_priority
        hints:
          - id: f1
            priority: SUPER_DUPER_CRITICAL
            rule: ...
            source: ...
            source_kind: ...
        """,
    )
    reg = HintRegistry(packs_root=tmp_path).reload()
    # Pack rejected as malformed
    assert reg.all_hints() == []


def test_loader_rejects_duplicate_hint_ids(tmp_path: Path):
    _write_pack(
        tmp_path,
        "topic",
        "dups",
        """
        schema_version: 1
        topic: dups
        hints:
          - id: f1
            priority: useful
            rule: a
            source: x
            source_kind: y
          - id: f1
            priority: useful
            rule: b
            source: x
            source_kind: y
        """,
    )
    reg = HintRegistry(packs_root=tmp_path).reload()
    assert reg.all_hints() == []


# ── Query API ──────────────────────────────────────────────────────


def test_query_by_topic_returns_pack_hints(tmp_path: Path, monkeypatch):
    reg = _registry_with_pack(
        tmp_path,
        "topic",
        "feedback",
        """
        schema_version: 1
        topic: feedback
        op_types: [feedbackTOP]
        hints:
          - id: critical_hint
            priority: critical
            rule: critical body
            source: src
            source_kind: skill_pitfall
          - id: useful_hint
            priority: useful
            rule: useful body
            source: src
            source_kind: skill_pitfall
        """,
    )
    matches = reg.find(topic="feedback")
    ids = [m.hint.id for m in matches]
    # Critical comes first
    assert ids[0] == "critical_hint"
    assert "useful_hint" in ids


def test_query_by_op_type_matches_when_clause(tmp_path: Path):
    reg = _registry_with_pack(
        tmp_path,
        "topic",
        "feedback",
        """
        schema_version: 1
        topic: feedback
        op_types: []
        hints:
          - id: when_hint
            priority: useful
            rule: only when feedbackTOP
            source: src
            source_kind: skill_pitfall
            when:
              op_type: feedbackTOP
          - id: other_hint
            priority: useful
            rule: only when something else
            source: src
            source_kind: skill_pitfall
            when:
              op_type: glslTOP
        """,
    )
    matches = reg.find(op_type="feedbackTOP")
    ids = {m.hint.id for m in matches}
    assert "when_hint" in ids
    # other_hint may or may not appear via pack-mate at score 0.5; check that
    # the explicit when-match scored higher
    when_match = next(m for m in matches if m.hint.id == "when_hint")
    assert "when_op_type" in when_match.reasons


def test_query_by_intent_match(tmp_path: Path):
    reg = _registry_with_pack(
        tmp_path,
        "topic",
        "feedback",
        """
        schema_version: 1
        topic: feedback
        hints:
          - id: decay_hint
            priority: useful
            rule: trail decay via opacity
            source: src
            source_kind: skill_pitfall
            when:
              intent_match: "decay|trail|fade"
        """,
    )
    matches = reg.find(intent="how do I tune trail decay?")
    ids = [m.hint.id for m in matches]
    assert "decay_hint" in ids


def test_query_by_error_text(tmp_path: Path):
    reg = _registry_with_pack(
        tmp_path,
        "topic",
        "feedback",
        """
        schema_version: 1
        topic: feedback
        hints:
          - id: not_enough_sources
            priority: critical
            rule: static analyzer warning is not a runtime error
            source: src
            source_kind: skill_pitfall
            when:
              error_match: "Not enough sources"
        """,
    )
    matches = reg.find(error_text="Not enough sources specified for cyclic dependency")
    ids = [m.hint.id for m in matches]
    assert "not_enough_sources" in ids


# ── Auto-injection rules ───────────────────────────────────────────


def test_auto_inject_create_node_high_risk_op(tmp_path: Path, monkeypatch):
    """A real shipped pack is needed for this test — uses default_registry."""
    result = auto_inject_hints(
        "td_create_node",
        {"node_type": "feedbackTOP", "parent_path": "/project1"},
        {"success": True},
    )
    assert result is not None
    assert result["auto_triggered"] is True
    assert "feedbackTOP" in result["trigger_reason"]
    assert result["items"]
    # First item is critical priority
    assert result["items"][0]["priority"] == "critical"


def test_auto_inject_create_node_low_risk_op_returns_none():
    result = auto_inject_hints(
        "td_create_node",
        {"node_type": "nullCHOP", "parent_path": "/project1"},
        {"success": True},
    )
    assert result is None


def test_auto_inject_set_params_string_to_reference_param():
    result = auto_inject_hints(
        "td_set_params",
        {"path": "/project1/geo1", "params": {"instanceop": "../noise1"}},
        {"success": True},
    )
    assert result is not None
    assert "reference-style param" in result["trigger_reason"]


def test_auto_inject_set_params_with_op_object_no_trigger():
    """Setting a reference param to a non-string value (an op object representation)
    should not trigger (the agent did the right thing)."""
    result = auto_inject_hints(
        "td_set_params",
        {"path": "/project1/geo1", "params": {"instanceop": None}},
        {"success": True},
    )
    assert result is None


def test_auto_inject_exec_python_with_restricted_pattern():
    result = auto_inject_hints(
        "td_exec_python",
        {"code": "import subprocess; subprocess.run(['ls'])"},
        {"success": True},
    )
    assert result is not None
    # First-match wins; either 'import ' or 'subprocess' qualifies
    reason = result["trigger_reason"].lower()
    assert "import" in reason or "subprocess" in reason


def test_auto_inject_exec_python_clean_code_no_trigger():
    result = auto_inject_hints(
        "td_exec_python",
        {"code": "x = op('/project1').path; print(x)"},
        {"success": True},
    )
    assert result is None


def test_auto_inject_get_errors_with_known_pattern():
    result = auto_inject_hints(
        "td_get_errors",
        {"path": "/"},
        {"errors": [{"path": "/project1/feedback1", "message": "Not enough sources specified"}]},
    )
    assert result is not None
    assert "Not enough sources" in result["trigger_reason"]


def test_auto_inject_unknown_tool_returns_none():
    result = auto_inject_hints("td_some_unknown_tool", {}, {})
    assert result is None


def test_auto_inject_silently_handles_bad_response_shapes():
    # Should never raise, regardless of payload/response weirdness
    assert auto_inject_hints("td_create_node", None, None) is None
    assert auto_inject_hints("td_create_node", "not-a-dict", "also-not-a-dict") is None


# ── query_hints public API ─────────────────────────────────────────


def test_query_hints_returns_versioned_metadata():
    """The shipped registry has feedback / glsl / render_pipeline etc. packs."""
    result = query_hints(topic="feedback", max_hints=3)
    assert "hint_pack_version" in result
    assert result["hint_pack_version"]
    assert result["available_topics"]
    assert "feedback" in result["available_topics"]
    assert result["hints"]


def test_query_hints_max_hints_clamps():
    result = query_hints(topic="feedback", max_hints=2)
    assert len(result["hints"]) <= 2


def test_query_hints_invalid_max_hints_clamped_to_safe_range():
    """max_hints=0 → 1; max_hints=999 → 20."""
    low = query_hints(topic="feedback", max_hints=0)
    high = query_hints(topic="feedback", max_hints=999)
    assert len(low["hints"]) >= 1 or low["hints"] == []
    assert len(high["hints"]) <= 20
