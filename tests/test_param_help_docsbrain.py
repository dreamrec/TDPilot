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
            "parameter_names": ["amp", "period", "outputresolution"],
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
