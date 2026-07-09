"""ParamSemantics exposure in td_get_param_help / td_get_operator_doc.

The knowledge tools serialize the brain's docs-grounded ParamSemantics
contracts (enum_values, valid_range, default_strategy, cook_risk) into their
responses — read-only use of td_mcp.brain.param_semantics. Compact: only
non-null fields appear.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as registry
from td_mcp.registry.tools_knowledge import (
    _param_semantics_for_op,
    _param_semantics_for_param,
)
from td_mcp.services import ServiceContainer


class _FakeCardIndex:
    def __init__(self, cards: dict[str, dict]):
        self._cards = cards

    def get_operator(self, op_type: str):
        return self._cards.get(op_type)


class _FakeClient:
    def __init__(self, op_type: str, family: str):
        self.op_type = op_type
        self.family = family

    async def request(self, endpoint: str, body: dict | None = None):
        if endpoint == "node/params":
            return {"parameters": {"frequency": {"value": 2.0, "default": 1.0}}}
        if endpoint == "node/detail":
            return {"type": self.op_type, "family": self.family, "path": (body or {}).get("path")}
        return {}


def _make_ctx(card_index, client) -> SimpleNamespace:
    services = ServiceContainer(td_client=client, card_index=card_index)
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


# ---------------------------------------------------------------------------
# Helper-level behavior
# ---------------------------------------------------------------------------


def test_param_semantics_for_op_returns_compact_non_null_fields():
    semantics = _param_semantics_for_op("renderTOP")

    assert semantics, "renderTOP should have known param semantics"
    camera = semantics["camera"]
    assert camera["value_kind"] == "op_ref"
    assert camera["expected_op_type"] == "cameraCOMP"
    assert camera["cook_risk"] == "high"
    assert camera["default_strategy"]
    assert camera["official_source"].startswith("https://docs.derivative.ca/")
    # Compact contract: null/empty fields are omitted entirely.
    assert "valid_range" not in camera
    assert "enum_values" not in camera
    for fields in semantics.values():
        for key, value in fields.items():
            assert value not in (None, [], ""), f"null-ish field {key} leaked into compact semantics"


def test_param_semantics_for_op_resolves_short_type_plus_family():
    short = _param_semantics_for_op("render", "TOP")
    full = _param_semantics_for_op("renderTOP")

    assert short == full
    assert short


def test_param_semantics_for_param_returns_range_fields():
    frequency = _param_semantics_for_param("lfoCHOP", "CHOP", "frequency")

    assert frequency is not None
    assert frequency["valid_range"] == [0.0, 100000.0]
    assert frequency["unit"] == "cycles_per_second"
    assert frequency["cook_risk"] == "medium"


def test_param_semantics_for_unknown_op_or_param_is_empty():
    assert _param_semantics_for_op("definitelyNotAnOpTOP") == {}
    assert _param_semantics_for_param("renderTOP", "TOP", "not_a_param") is None


# ---------------------------------------------------------------------------
# Tool-level responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_operator_doc_serializes_param_semantics(monkeypatch):
    card = {"op_type": "renderTOP", "family": "TOP", "display_name": "Render TOP", "summary": "renders"}
    client = _FakeClient("renderTOP", "TOP")
    ctx = _make_ctx(_FakeCardIndex({"renderTOP": card}), client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_operator_doc(ctx, op_type="renderTOP")

    assert result["card"] == card
    assert "param_semantics" in result
    assert result["param_semantics"]["camera"]["expected_op_type"] == "cameraCOMP"
    assert result["param_semantics"]["geometry"]["expected_op_type"] == "geometryCOMP"


@pytest.mark.asyncio
async def test_get_operator_doc_omits_param_semantics_when_unknown(monkeypatch):
    card = {"op_type": "somefutureTOP", "family": "TOP", "summary": "no semantics known"}
    client = _FakeClient("somefutureTOP", "TOP")
    ctx = _make_ctx(_FakeCardIndex({"somefutureTOP": card}), client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_operator_doc(ctx, op_type="somefutureTOP")

    assert result["card"] == card
    assert "param_semantics" not in result


@pytest.mark.asyncio
async def test_get_param_help_serializes_param_semantics_for_param(monkeypatch):
    client = _FakeClient("lfo", "CHOP")
    ctx = _make_ctx(_FakeCardIndex({}), client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(ctx, node_path="/project1/lfo1", param_name="frequency")

    assert result["param_semantics"]["valid_range"] == [0.0, 100000.0]
    assert result["param_semantics"]["default_strategy"]


@pytest.mark.asyncio
async def test_get_param_help_omits_param_semantics_when_unknown(monkeypatch):
    client = _FakeClient("lfo", "CHOP")
    ctx = _make_ctx(_FakeCardIndex({}), client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(ctx, node_path="/project1/lfo1", param_name="not_a_param")

    assert "param_semantics" not in result
