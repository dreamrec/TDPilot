"""End-to-end behavioral test: td_get_param_help against a DocsBrain index.

Pre-v1.4.5 `td_get_param_help` always returned `card_param: None` when the
knowledge source was DocsBrain, because DocsBrain returned
``parameters: ["amp", "seed"]`` while the tool iterated ``card["key_params"]``.
This suite pins the Fix 3 behavior:

1. DocsBrain.get_operator() now returns `key_params` in CardIndex shape.
2. td_get_param_help iterates over key_params case-insensitively and
   surfaces the card source in provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as registry
from td_mcp.knowledge.docsbrain import DocsBrain
from td_mcp.knowledge.docsbrain.indexer import build_index
from td_mcp.services import ServiceContainer


def _build_brain_with_noisetop(tmp_path: Path) -> DocsBrain:
    chunks = [
        {
            "chunk_id": "noise_top__summary__0001",
            "page_id": "noise_top",
            "doc_type": "operator",
            "section_title": "Noise TOP",
            "operator_family": "TOP",
            "operator_name": "Noise TOP",
            "mentioned_operators": [],
            # v1.4.6: real DocsBrain scraping always emits "Label\nname"
            # (MediaWiki docs have the label and internal name on separate
            # lines). _normalize_key_param now drops single-token entries
            # as junk (stray doc text / menu values). Use the realistic
            # structure here so the test exercises the production path.
            "parameter_names": [
                "Amplitude\namp",
                "Period\nperiod",
                "Output\nResolution\noutputresolution",
            ],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": "The Noise TOP generates procedural noise textures. Amp controls amplitude.",
        },
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    db_path = tmp_path / "brain.db"
    build_index(chunks_path, db_path)
    return DocsBrain(db_path=db_path)


class _FakeClient:
    """Returns canned `node/params` + `node/detail` responses."""

    def __init__(self, op_type: str = "noiseTOP"):
        self.op_type = op_type

    async def request(self, endpoint: str, body: dict | None = None):
        if endpoint == "node/params":
            return {"parameters": {"amp": {"value": 0.5, "default": 0.5}}}
        if endpoint == "node/detail":
            return {"type": self.op_type, "path": body.get("path")}
        return {}


def _make_ctx(brain: DocsBrain, client: _FakeClient) -> SimpleNamespace:
    """Build a minimal lifespan context with `td_client` bypassed.

    `_get_client()` enforces `isinstance(td_client, TDClient)` which our
    FakeClient can't satisfy without subclassing. Tests that need a custom
    client monkeypatch `registry._get_client` directly (same pattern used
    in test_replay_validation.py).
    """
    services = ServiceContainer(
        td_client=client,
        card_index=brain,  # DocsBrain is a drop-in for CardIndex
    )
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


@pytest.mark.asyncio
async def test_param_help_returns_docsbrain_card_param_for_known_param(tmp_path, monkeypatch):
    """With DocsBrain active, known parameter names produce a
    card_param object (not None) and provenance.source reports
    `docsbrain` so callers can see where the data came from."""
    brain = _build_brain_with_noisetop(tmp_path)
    client = _FakeClient()
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(ctx, node_path="/project1/noise1", param_name="amp")

    assert result.get("card_param") is not None, (
        "pre-v1.4.5 regression would return None; post-fix must surface the matching param"
    )
    assert result["card_param"]["name"] == "amp"
    assert result["card_param"]["source"] == "docsbrain"
    assert result["provenance"]["source"] == "docsbrain"


@pytest.mark.asyncio
async def test_param_help_case_insensitive_match(tmp_path, monkeypatch):
    """Fix 3 calls for case-insensitive matching so
    `outputResolution` resolves to `outputresolution`."""
    brain = _build_brain_with_noisetop(tmp_path)
    client = _FakeClient()
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(
        ctx, node_path="/project1/noise1", param_name="outputResolution"
    )
    assert result.get("card_param") is not None
    assert result["card_param"]["name"] == "outputresolution"


@pytest.mark.asyncio
async def test_param_help_unknown_param_still_clean(tmp_path, monkeypatch):
    """Unknown parameter → card_param: None, no error."""
    brain = _build_brain_with_noisetop(tmp_path)
    client = _FakeClient()
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(ctx, node_path="/project1/noise1", param_name="does_not_exist")
    assert result.get("card_param") is None
    assert "error" not in result


# ---------------------------------------------------------------------------
# v1.4.6 live-gap regression: td_get_param_help against real TD response shapes.
#
# During v1.4.5 live validation on a real TD instance, td_get_param_help
# returned {"live": null, "card_param": null, provenance.source: "local_card"}
# for a valid noiseTOP + valid param — despite DocsBrain being fully wired
# (td_get_operator_doc against the same brain returned normalized key_params).
#
# Root cause was two orthogonal pre-existing gaps that the v1.4.5 Fix 3 tests
# never hit because the existing _FakeClient pre-normalized the op_type to
# "noiseTOP" and returned params regardless of the names filter:
#
#   Gap A (op_type short-form): TD's `node/detail` returns the short op_type
#     (`"type": "noise"`, `"family": "TOP"` separately), but DocsBrain keys
#     operators by canonical `"noiseTOP"`. The tool looked up with the short
#     form only, so no card matched and `card_source` stayed None.
#
#   Gap B (case-sensitive param filter): TD's `node/params` is case-sensitive
#     on the `names` filter. Passing `"outputResolution"` (mixed case) when
#     TD stores `"outputresolution"` returned an empty parameters dict, so
#     `live` came back null even though the param exists on the node.
#
# Together a user typing the natural `outputResolution` got a fully empty
# response. These tests pin both fallbacks.
# ---------------------------------------------------------------------------


class _LiveShapeClient:
    """Mimics TD's real response shapes — short op_type plus family from detail,
    case-sensitive name filter on params (TD's built-in params are canonically
    lowercase). Used to reproduce the gaps above without needing a live TD."""

    def __init__(self, op_type_short: str = "noise", family: str = "TOP"):
        self.op_type_short = op_type_short
        self.family = family
        self.params: dict = {"outputresolution": {"value": "useinput", "default": "useinput"}}

    async def request(self, endpoint: str, body: dict | None = None):
        if endpoint == "node/params":
            names = (body or {}).get("names") or []
            return {"parameters": {n: self.params[n] for n in names if n in self.params}}
        if endpoint == "node/detail":
            return {
                "type": self.op_type_short,
                "family": self.family,
                "path": (body or {}).get("path"),
            }
        return {}


@pytest.mark.asyncio
async def test_param_help_falls_back_to_type_plus_family_for_card_lookup(tmp_path, monkeypatch):
    """Gap A: with realistic TD shape (type='noise', family='TOP') the
    tool must fall back to the canonical 'noiseTOP' key so DocsBrain
    resolves the card. Pre-v1.4.6 this silently returned local_card."""
    brain = _build_brain_with_noisetop(tmp_path)
    client = _LiveShapeClient(op_type_short="noise", family="TOP")
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(
        ctx, node_path="/project1/noise1", param_name="outputresolution"
    )
    assert result.get("card_param") is not None, (
        "Gap A: short op_type 'noise' alone does not resolve in DocsBrain; "
        "the tool must retry with type+family ('noiseTOP'). Pre-v1.4.6 this "
        "silently returned card_param=None with provenance local_card."
    )
    assert result["card_param"]["name"] == "outputresolution"
    assert result["card_param"]["source"] == "docsbrain"
    assert result["provenance"]["source"] == "docsbrain"


@pytest.mark.asyncio
async def test_param_help_retries_lowercased_name_for_live_fetch(tmp_path, monkeypatch):
    """Gap B: TD's node/params filter is case-sensitive. If the caller
    passes a mixed-case built-in name like 'outputResolution', TD returns
    no match. The tool must retry with the lowercase form so callers
    don't get a silent `live: null` on a simple casing slip."""
    brain = _build_brain_with_noisetop(tmp_path)
    client = _LiveShapeClient(op_type_short="noise", family="TOP")
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(
        ctx, node_path="/project1/noise1", param_name="outputResolution"
    )
    assert result.get("live") is not None, (
        "Gap B: mixed-case name forwarded verbatim → TD returns empty. "
        "The tool must retry with the lowercase form."
    )
    # Gap A still in play here (short type → canonical fallback), so the
    # card_param must also resolve — both fixes together.
    assert result.get("card_param") is not None
    assert result["card_param"]["name"] == "outputresolution"
    assert result["provenance"]["source"] == "docsbrain"


@pytest.mark.asyncio
async def test_param_help_unknown_param_still_clean_against_live_shape(tmp_path, monkeypatch):
    """Negative control: unknown param against the live shape still
    returns card_param: None with no exception. Protects against an
    over-eager fallback that papers over genuinely bad input."""
    brain = _build_brain_with_noisetop(tmp_path)
    client = _LiveShapeClient(op_type_short="noise", family="TOP")
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_param_help(
        ctx, node_path="/project1/noise1", param_name="totally_not_a_param"
    )
    assert result.get("card_param") is None
    assert "error" not in result
