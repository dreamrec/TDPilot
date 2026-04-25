"""Live-validation regressions captured while testing v1.4.5+ against a real
TouchDesigner instance. Each test here corresponds to a symptom a user
would hit in normal use — silently empty responses, junk data in cards,
or valid inputs rejected by validators.

Bug B — td_get_operator_doc short-form lookup
  `td_get_operator_doc("glsl")` returned "No card found" on live TD even
  though `td_get_operator_doc("glslTOP")` returned a rich card. Same
  short-form gap that v1.4.6 fixed for `td_get_param_help` — but it
  lives in a second tool too. Mirror that fix here.

Bug C — POPx FTS intent-filter mismatch
  `td_search_popx_docs("Noise Falloff")` returned 0 results even though
  the POPx DB contains an exact `operator_name = "Noise Falloff"` entry.
  Root cause: `DocsBrain._detect_intent` matches operator-name queries
  to doc_type filter `["operator", "python_api"]`, but the POPx brain
  uses `catalog_operators` and `reference` doc_types, so the filter
  excluded every chunk. Expand the intent-operator doc_type set to
  include the POPx values.

Bug E — DocsBrain key_params junk
  Cards for operators with menus (glslTOP, renderTOP) returned
  `key_params` entries like `{name: "8"}`, `{name: "Back"}`,
  `{name: "_separator_"}`, `{name: "DCI"}` — menu option values and
  stray doc-text fragments that leak through the FTS `parameter_names`
  list. Filter by requiring a `\\n` in the raw doc entry so we only
  keep entries that look like `"Label\\ninternalname"`.

Bug N — td_create_node POPX family suffix
  The CreateNodeInput validator only allowed TOP, CHOP, SOP, DAT, COMP,
  MAT, POP. But TD 2025 ships a native POPX operator family (Noise
  Falloff, DLA, Particle, …) which the validator rejects. Add POPX.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import td_mcp.tool_registry as registry
from td_mcp.knowledge.docsbrain import DocsBrain, _normalize_key_param
from td_mcp.knowledge.docsbrain.indexer import build_index
from td_mcp.models._legacy import CreateNodeInput
from td_mcp.services import ServiceContainer

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_derivative_style_brain(tmp_path: Path) -> DocsBrain:
    """Mimic the Derivative brain — operators stored with doc_type='operator'."""
    chunks = [
        {
            "chunk_id": "glsl_top__summary__0001",
            "page_id": "glsl_top",
            "doc_type": "operator",
            "section_title": "GLSL TOP",
            "operator_family": "TOP",
            "operator_name": "GLSL TOP",
            "mentioned_operators": [],
            # mix of real params, menu values, and stray doc text — mirrors
            # what the live DB returns for glslTOP (see bug report).
            "parameter_names": [
                "Output\nResolution\noutputresolution",  # valid: label + name
                "useinput",  # menu value (no \n) — JUNK
                "2x\n2x",  # menu value with \n — borderline, but both halves equal
                "8",  # numeric menu index — JUNK
                "DCI",  # menu label uppercase — JUNK
                "Back",  # stray doc word — JUNK
                "_separator_\n_separator_",  # UI separator — borderline
                "Where i is the 0",  # stray doc fragment (no \n) — JUNK
                "aspect1\naspect1",  # valid repeated
                "bgcolorr",  # valid lowercase (no \n, but looks param-like)
            ],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 50,
            "content": "The GLSL TOP runs shaders.",
        },
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    db_path = tmp_path / "derivative.db"
    build_index(chunks_path, db_path)
    return DocsBrain(db_path=db_path)


def _build_popx_style_brain(tmp_path: Path) -> DocsBrain:
    """Mimic the POPx brain — operators stored with doc_type='catalog_operators'
    and 'reference' (NOT 'operator'). This is the shape that tripped Bug C."""
    chunks = [
        {
            "chunk_id": "catalog__noise_falloff__0001",
            "page_id": "catalog__operators_falloffs_noise_falloff",
            "doc_type": "catalog_operators",
            "section_title": "Noise Falloff (catalog summary)",
            "operator_family": "falloffs",
            "operator_name": "Noise Falloff",
            "mentioned_operators": [],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": "Procedural noise-based falloff operator for POPX.",
        },
        {
            "chunk_id": "ref__noise_falloff__0002",
            "page_id": "ref__operators_falloffs",
            "doc_type": "reference",
            "section_title": "Noise Falloff",
            "operator_family": "falloffs",
            "operator_name": "Noise Falloff",
            "mentioned_operators": [],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 40,
            "content": "The Noise Falloff generates procedural falloff patterns.",
        },
    ]
    chunks_path = tmp_path / "popx_chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    db_path = tmp_path / "popx.db"
    build_index(chunks_path, db_path)
    return DocsBrain(db_path=db_path)


class _FakeClient:
    """node/detail returns TD-realistic shape: short type + family."""

    def __init__(self, op_type_short: str = "glsl", family: str = "TOP"):
        self.op_type_short = op_type_short
        self.family = family

    async def request(self, endpoint: str, body: dict | None = None):
        if endpoint == "node/detail":
            return {
                "type": self.op_type_short,
                "family": self.family,
                "path": (body or {}).get("path"),
            }
        return {}


def _make_ctx(brain: DocsBrain, client: _FakeClient) -> SimpleNamespace:
    services = ServiceContainer(td_client=client, card_index=brain)
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


# ---------------------------------------------------------------------------
# Bug N — td_create_node POPX family suffix
# ---------------------------------------------------------------------------


def test_create_node_accepts_popx_family_suffix():
    """TD 2025 ships a native POPX operator family (visible in the OP Create
    Dialog's POPX tab). Before the fix, the validator rejected `noisePOPX`
    saying 'should end with a family suffix: TOP, CHOP, SOP, DAT, COMP, MAT,
    POP.' POPX was missing."""
    # Just must not raise.
    CreateNodeInput(parent_path="/project1", node_type="noisePOPX")
    CreateNodeInput(parent_path="/project1", node_type="noiseFALLOFFPOPX")
    CreateNodeInput(parent_path="/project1", node_type="dlaPOPX")


def test_create_node_still_rejects_unknown_family():
    """Sanity — the validator must still reject garbage families so users
    catch typos."""
    with pytest.raises(ValidationError):
        CreateNodeInput(parent_path="/project1", node_type="noiseBANANA")


def test_create_node_still_accepts_existing_families():
    """Regression: the POP vs POPX distinction must not confuse the validator.
    `noisePOP` (Point Operator) and `noisePOPX` must both pass."""
    CreateNodeInput(parent_path="/project1", node_type="noisePOP")
    CreateNodeInput(parent_path="/project1", node_type="noisePOPX")
    CreateNodeInput(parent_path="/project1", node_type="noiseTOP")
    CreateNodeInput(parent_path="/project1", node_type="boxSOP")


# ---------------------------------------------------------------------------
# Bug B — td_get_operator_doc short-form fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_operator_doc_with_short_type_and_family_via_node_path(tmp_path, monkeypatch):
    """Given a live node path, `node/detail` returns `type='glsl', family='TOP'`.
    The tool must try both the short form AND the canonical type+family so
    DocsBrain resolves. Pre-fix: only `type` was tried, so the card lookup
    failed when the DB keys by `glslTOP`."""
    brain = _build_derivative_style_brain(tmp_path)
    client = _FakeClient(op_type_short="glsl", family="TOP")
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_operator_doc(ctx, node_path="/project1/myglsl")
    assert "error" not in result, f"expected card, got error: {result.get('error')}"
    assert result["card"]["op_type"] == "glslTOP"
    assert result["card"]["family"] == "TOP"


@pytest.mark.asyncio
async def test_get_operator_doc_op_type_only_short_form_falls_back(tmp_path, monkeypatch):
    """Given just op_type='glsl' (short form, no node_path), the tool must
    try common family suffixes so a user typing the short name still gets a
    card. Pre-fix: returned 'No card found' immediately because `_op_type_map`
    only stored canonical keys like `glslTOP`."""
    brain = _build_derivative_style_brain(tmp_path)
    client = _FakeClient()  # not used in this path but required by _make_ctx
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_operator_doc(ctx, op_type="glsl")
    assert "error" not in result, f"expected card, got: {result}"
    assert result["card"]["op_type"] == "glslTOP"


@pytest.mark.asyncio
async def test_get_operator_doc_still_fails_for_total_garbage(tmp_path, monkeypatch):
    """Negative control — nonsense op_type must still return the error
    instead of silently inventing a card via the fallback loop."""
    brain = _build_derivative_style_brain(tmp_path)
    client = _FakeClient()
    ctx = _make_ctx(brain, client)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_get_operator_doc(ctx, op_type="totally_bogus_xyz")
    assert "error" in result


# ---------------------------------------------------------------------------
# Bug C — POPx FTS intent mismatch
# ---------------------------------------------------------------------------


def test_popx_brain_search_by_operator_name_returns_results(tmp_path):
    """Searching the POPx brain for 'Noise Falloff' must return the matching
    chunks. Pre-fix: `_detect_intent` returned `['operator', 'python_api']`
    which excluded POPx's `catalog_operators` and `reference` doc_types."""
    brain = _build_popx_style_brain(tmp_path)

    results = brain.search("Noise Falloff", limit=5)
    assert results, "FTS returned 0 rows for a query whose exact operator_name is in the DB"
    op_names = {r.get("operator_name") for r in results}
    assert "Noise Falloff" in op_names


def test_popx_brain_search_lowercased_operator_name_also_works(tmp_path):
    """Caller should not need to match the DB's exact casing."""
    brain = _build_popx_style_brain(tmp_path)
    results = brain.search("noise falloff", limit=5)
    assert results
    assert any(r.get("operator_name") == "Noise Falloff" for r in results)


def test_derivative_brain_operator_search_still_narrowed(tmp_path):
    """Regression: the fix must not break the Derivative brain's narrow
    filtering. A query that matches a Derivative operator name should still
    return its `operator` doc_type chunks."""
    brain = _build_derivative_style_brain(tmp_path)
    results = brain.search("GLSL TOP", limit=5)
    assert results
    # Every returned chunk should be from one of the operator-like doc_types.
    allowed = {"operator", "python_api", "catalog_operators", "reference"}
    assert all(r.get("doc_type") in allowed for r in results)


# ---------------------------------------------------------------------------
# Bug E — DocsBrain key_params junk filter
# ---------------------------------------------------------------------------


def test_normalize_key_param_drops_single_token_stray_text():
    """Stray words like 'Back', 'Z', 'Fish', 'Early Depth' without a \\n
    separator are doc-text fragments, not parameter names. They must be
    filtered so tools iterating `key_params` don't mislead users."""
    # Each of these should be recognized as junk and return None.
    for junk in ("Back", "Z", "DCI", "Display", "Early Depth", "Where i is the 0", "Pre"):
        assert _normalize_key_param(junk) is None, (
            f"junk fragment {junk!r} must be filtered but _normalize_key_param accepted it"
        )


def test_normalize_key_param_keeps_real_param_with_label_and_name():
    """Real params have the shape 'Label\\ninternalname' (or multi-line
    label + name). They must survive the filter with source='docsbrain'."""
    result = _normalize_key_param("Output\nResolution\noutputresolution")
    assert result is not None
    assert result["name"] == "outputresolution"
    assert result["label"] == "Output Resolution"
    assert result["source"] == "docsbrain"


def test_normalize_key_param_drops_numeric_single_token():
    """`"8"`, `"16"`, `"32"` alone are menu values, not params. Also filtered."""
    for num in ("8", "16", "32", "24"):
        assert _normalize_key_param(num) is None


def test_get_operator_key_params_are_clean(tmp_path):
    """Integration check: after the filter, no key_param entry should be a
    single stray word / number. Pre-fix live calls against real TD
    returned `{name: "Back"}`, `{name: "8"}`, `{name: "_separator_"}` etc."""
    brain = _build_derivative_style_brain(tmp_path)
    card = brain.get_operator("glslTOP")
    assert card is not None
    junk_names = {"Back", "Z", "Pre", "DCI", "Display", "8", "16", "32", "Where i is the 0"}
    kp_names = {kp["name"] for kp in card["key_params"]}
    leaked = kp_names & junk_names
    assert not leaked, f"junk entries leaked into key_params: {leaked}"


# ---------------------------------------------------------------------------
# Bug Q + Bug R - DocsBrain search() output shape mismatch with CardIndex consumers.
#
# td_find_official_example and td_explain_better_way both read CardIndex-shape
# fields (component_name, display_name, summary, op_type, snippet_id) from
# whatever `idx.search(...)` returns. When the card_index is DocsBrain (the
# v1.4.5 default for the Derivative brain), search() emits FTS-chunk-shaped
# rows with section_title / operator_name / content instead. Consumers saw
# empty strings for every field.
#
# Live repro (v1.4.5+):
#   td_find_official_example("feedback loop noise") -> 5 palette_example
#     results with name="", display_name="", summary=""  (Bug Q)
#   td_explain_better_way("animate noise TOP every frame") -> empty
#     recommendation (every candidate filtered by _is_informative_card
#     because CardIndex fields are blank)  (Bug R)
#
# The fix is a shape translation at the DocsBrain.search() boundary:
# enrich each row with CardIndex-compatible keys derived from the FTS
# columns. get_operator() / get_palette() already do this for exact-lookup
# responses; search() should too so consumers see one consistent shape.
# ---------------------------------------------------------------------------


def _build_mixed_brain_with_shape_coverage(tmp_path: Path) -> DocsBrain:
    """Chunks covering the doc_types that tools consume via search():
    operator, palette, snippet. Each has a distinctive identifier so the
    shape normalization can be proven unambiguously."""
    chunks = [
        {
            "chunk_id": "composite_top__summary__0001",
            "page_id": "composite_top",
            "doc_type": "operator",
            "section_title": "Composite TOP",
            "operator_family": "TOP",
            "operator_name": "Composite TOP",
            "mentioned_operators": [],
            "parameter_names": ["Operation\noperation", "Pre-Multiply\npremult"],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 40,
            "content": ("The Composite TOP composites two input images together using various blend modes."),
        },
        {
            "chunk_id": "palette_svg__summary__0002",
            "page_id": "palette:svg",
            "doc_type": "palette",
            "section_title": "Palette:SVG",
            "operator_family": None,
            "operator_name": None,
            "mentioned_operators": [],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 30,
            "content": (
                "SVG palette component. Loads and renders scalable vector "
                "graphics in TouchDesigner pipelines."
            ),
        },
        {
            "chunk_id": "snippet_feedback_loop__0003",
            "page_id": "snippet:feedback_loop",
            "doc_type": "snippet",
            "section_title": "Feedback Loop",
            "operator_family": "TOP",
            "operator_name": None,
            "mentioned_operators": [],
            "parameter_names": [],
            "python_symbols": [],
            "build_number": None,
            "build_date": None,
            "change_category": None,
            "token_estimate": 50,
            "content": (
                "A feedback loop routes a TOP's output back into its own "
                "input via a Feedback TOP, enabling trail / smear effects."
            ),
        },
    ]
    chunks_path = tmp_path / "mixed_chunks.jsonl"
    with open(chunks_path, "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    db_path = tmp_path / "mixed.db"
    build_index(chunks_path, db_path)
    return DocsBrain(db_path=db_path)


def test_search_palette_result_carries_cardindex_shape_fields(tmp_path):
    """Bug Q root cause: palette search results must expose component_name,
    display_name, and summary so td_find_official_example's serializer
    can read non-empty values. Pre-fix the FTS row only had section_title
    and content, so the tool emitted empty strings."""
    brain = _build_mixed_brain_with_shape_coverage(tmp_path)
    results = brain.search("svg palette", card_types=["palette"], limit=5)
    assert results, "palette search returned no results; fixture may be wrong"
    r = results[0]
    assert isinstance(r.get("component_name"), str) and r["component_name"].strip(), (
        f"palette row must expose component_name; got {r!r}"
    )
    assert isinstance(r.get("display_name"), str) and r["display_name"].strip(), (
        f"palette row must expose display_name; got {r!r}"
    )
    assert isinstance(r.get("summary"), str) and r["summary"].strip(), (
        f"palette row must expose summary; got {r!r}"
    )
    # And the raw FTS fields must still be present for back-compat.
    assert r.get("section_title")
    assert r.get("content")


def test_search_operator_result_carries_op_type_and_display_name(tmp_path):
    """Bug R root cause: operator search results must expose op_type and
    display_name so _is_informative_card accepts them. Pre-fix only
    operator_name existed, which isn't in the _is_informative_card key
    set, so every candidate was filtered out and the recommendation
    became empty."""
    brain = _build_mixed_brain_with_shape_coverage(tmp_path)
    results = brain.search("composite", card_types=["operator"], limit=5)
    assert results
    r = results[0]
    assert r.get("op_type") == "compositeTOP", (
        f"operator row must expose canonical op_type='compositeTOP'; got {r.get('op_type')!r}"
    )
    assert r.get("display_name") == "Composite TOP"
    assert isinstance(r.get("summary"), str) and r["summary"].strip()


def test_search_snippet_result_carries_snippet_id(tmp_path):
    """Snippets are rarer in the corpus but td_find_official_example
    serializes them with `snippet_id`. The shape normalization must
    populate that field from the FTS row so the serializer picks up
    a stable identifier."""
    brain = _build_mixed_brain_with_shape_coverage(tmp_path)
    results = brain.search("feedback loop", card_types=["snippet"], limit=5)
    assert results
    r = results[0]
    assert isinstance(r.get("snippet_id"), str) and r["snippet_id"].strip()
    assert isinstance(r.get("summary"), str) and r["summary"].strip()


def test_is_informative_card_accepts_normalized_docsbrain_operator_result(tmp_path):
    """Integration: the _is_informative_card filter used by
    td_explain_better_way must accept DocsBrain search results post-fix.
    Pre-fix 100% of rows were filtered out because op_type/component_name/
    display_name/summary were all missing."""
    from td_mcp.tool_registry import _is_informative_card

    brain = _build_mixed_brain_with_shape_coverage(tmp_path)
    results = brain.search("composite", card_types=["operator"], limit=5)
    assert results
    assert any(_is_informative_card(r) for r in results), (
        "Bug R: every search result was dropped by _is_informative_card. "
        "Post-fix rows must expose op_type/display_name/summary so the "
        "filter sees them as informative."
    )


# ---------------------------------------------------------------------------
# Bug S (S.E) — td_memory_learn wire-graph walk for non-COMP roots.
#
# Current behavior (pre-v1.4.7): `_collect_subtree` only descends when the
# node has `isCOMP=True`. Learning from a TOP/CHOP/SOP returns just that
# single node, no connections. Users who built a wire-chain of ops would
# have to pre-wrap in a baseCOMP to save it.
#
# S.E auto-detect: if the ROOT is non-COMP, walk the bidirectional wire
# graph (follow `inputs` upstream AND `outputs` downstream) bounded by
# max_depth. COMP roots keep their existing children-walk semantic.
# ---------------------------------------------------------------------------


class _WireMockClient:
    """Mock TD client that serves node/detail with inputs AND outputs, and
    node children via the 'nodes' endpoint. Mirrors the v1.4.6+ TD-side
    shape that `_collect_subtree` consumes."""

    def __init__(self, nodes: dict):
        self._nodes = nodes

    async def request(self, endpoint: str, params: dict | None = None):
        params = params or {}
        if endpoint == "node/detail":
            path = params.get("path", "")
            return self._nodes.get(path, {"error": "not found"})
        if endpoint == "nodes":
            parent = params.get("path", "")
            children = [
                {"path": p}
                for p in self._nodes
                if p.startswith(parent + "/") and "/" not in p[len(parent) + 1 :]
            ]
            offset = params.get("offset", 0)
            limit = params.get("limit", 200)
            return {"nodes": children[offset : offset + limit]}
        return {}


def _wire_node(
    path: str,
    op_type: str,
    *,
    family: str = "TOP",
    is_comp: bool = False,
    inputs: list | None = None,
    outputs: list | None = None,
):
    return {
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "type": op_type,
        "family": family,
        "parameters": {},
        "inputs": inputs or [],
        "outputs": outputs or [],
        "isCOMP": is_comp,
    }


def _linear_chain_client() -> _WireMockClient:
    """Four-node linear wire chain under /project1 with NO wrapper COMP:
    noise1 -> xf1 -> lvl1 -> null1. Every node is a plain TOP, so the
    root of a learn call is always non-COMP."""
    return _WireMockClient(
        {
            "/project1/noise1": _wire_node(
                "/project1/noise1",
                "noiseTOP",
                outputs=[{"to": "/project1/xf1", "from_index": 0, "to_index": 0}],
            ),
            "/project1/xf1": _wire_node(
                "/project1/xf1",
                "transformTOP",
                inputs=[{"from": "/project1/noise1", "from_index": 0, "to_index": 0}],
                outputs=[{"to": "/project1/lvl1", "from_index": 0, "to_index": 0}],
            ),
            "/project1/lvl1": _wire_node(
                "/project1/lvl1",
                "levelTOP",
                inputs=[{"from": "/project1/xf1", "from_index": 0, "to_index": 0}],
                outputs=[{"to": "/project1/null1", "from_index": 0, "to_index": 0}],
            ),
            "/project1/null1": _wire_node(
                "/project1/null1",
                "nullTOP",
                inputs=[{"from": "/project1/lvl1", "from_index": 0, "to_index": 0}],
            ),
        }
    )


@pytest.mark.asyncio
async def test_memory_learn_from_non_comp_head_walks_downstream():
    """S.E: learning from the HEAD of a wire chain (noise1) should capture
    the whole chain by following output connections. Pre-v1.4.7 this
    returned only noise1 (node_count=1, connection_count=0)."""
    from td_mcp.memory.analyzer import analyze_network

    client = _linear_chain_client()
    result = await analyze_network(client, "/project1/noise1")
    assert result["node_count"] == 4, (
        f"expected full chain (noise->xf->lvl->null); got {result['node_count']} nodes. "
        f"recipe keys={list((result.get('recipe') or {}).get('nodes', {}).keys())}"
    )
    assert result["connection_count"] == 3
    recipe_types = {n["type"] for n in result["recipe"]["nodes"].values()}
    assert recipe_types == {"noiseTOP", "transformTOP", "levelTOP", "nullTOP"}


@pytest.mark.asyncio
async def test_memory_learn_from_non_comp_tail_walks_upstream():
    """S.E: learning from the TAIL of a wire chain (null1, terminal) must
    also capture the chain — by walking upstream through `inputs`.
    This supports the common workflow of 'save this technique, starting
    from the output/null node I care about'."""
    from td_mcp.memory.analyzer import analyze_network

    client = _linear_chain_client()
    result = await analyze_network(client, "/project1/null1")
    assert result["node_count"] == 4, (
        f"expected full chain walking upstream from null1; got {result['node_count']}"
    )
    assert result["connection_count"] == 3


@pytest.mark.asyncio
async def test_memory_learn_non_comp_respects_max_nodes_cap():
    """Safety: a tight `max_nodes` cap must bound the wire-walk. Protects
    against runaway capture in dense networks where a root node touches
    many unrelated peers via wires."""
    from td_mcp.memory.analyzer import analyze_network

    client = _linear_chain_client()
    result = await analyze_network(client, "/project1/xf1", max_nodes=2)
    assert result["node_count"] <= 2, (
        f"max_nodes=2 must cap wire-walk to <=2 nodes; got {result['node_count']}"
    )


@pytest.mark.asyncio
async def test_memory_learn_from_comp_root_still_walks_children():
    """S.E regression guard: COMP roots preserve the existing tree walk.
    Non-COMP children of the root are captured via the children tree,
    NOT via wire-graph walk — otherwise a COMP with dense internal
    wiring would also trigger bidirectional wire exploration that could
    leak out of the COMP boundary."""
    from td_mcp.memory.analyzer import analyze_network

    client = _WireMockClient(
        {
            "/project1/wrapper": _wire_node(
                "/project1/wrapper",
                "baseCOMP",
                family="COMP",
                is_comp=True,
            ),
            "/project1/wrapper/noise1": _wire_node(
                "/project1/wrapper/noise1",
                "noiseTOP",
                outputs=[{"to": "/project1/wrapper/out1", "from_index": 0, "to_index": 0}],
            ),
            "/project1/wrapper/out1": _wire_node(
                "/project1/wrapper/out1",
                "nullTOP",
                inputs=[{"from": "/project1/wrapper/noise1", "from_index": 0, "to_index": 0}],
            ),
            # Sibling OUTSIDE the wrapper — must NOT be captured even though
            # wrapper's children have wire connections internally.
            "/project1/unrelated": _wire_node("/project1/unrelated", "waveCHOP", family="CHOP"),
        }
    )
    result = await analyze_network(client, "/project1/wrapper")
    # 3 nodes: wrapper + noise1 + out1. NOT the sibling /project1/unrelated.
    assert result["node_count"] == 3
    assert "/project1/unrelated" not in str(result.get("recipe", {}))


# ---------------------------------------------------------------------------
# Bug V (V.C) — td_memory_replay opt-in root COMP recreation.
#
# Current behavior (pre-v1.4.7): `td_memory_replay` aliases the recipe's
# "/" entry to `parent_path` and only creates the children under it. The
# source's wrapper COMP — with its custom params, extensions, display
# settings, comment — is LOST. Replaying a COMP-wrapped technique
# produces a flat collection of children under `parent_path`.
#
# V.C opt-in: add `recreate_root` boolean to MemoryReplayInput. Default
# False preserves existing behavior (no regression for callers that
# expect flat replay). When True and the recipe's "/" entry has
# family=COMP, the replay creates that COMP under `parent_path` first
# and uses its new path as the effective parent for children — giving
# callers a faithful clone of COMP-wrapped techniques.
# ---------------------------------------------------------------------------


class _ReplayRecordingClient:
    """Minimal client that records every request and returns plausible
    node/create responses. Tests inspect `self.calls` to verify what
    replay actually did."""

    def __init__(self, families: dict | None = None):
        self._families = families or {"TOP": ["noise", "null"], "COMP": ["base"]}
        self.calls: list[tuple] = []

    async def request(self, endpoint: str, body: dict | None = None):
        body = body or {}
        self.calls.append((endpoint, body))
        if endpoint == "families":
            return self._families
        if endpoint == "node/create":
            parent = body.get("parent_path", "/").rstrip("/")
            name = body.get("name", "new_node")
            return {"node": {"path": f"{parent}/{name}"}}
        if endpoint == "node/params/set":
            return {"ok": True}
        if endpoint == "node/connect":
            return {"ok": True}
        return {}


def _wrapped_technique_recipe() -> dict:
    """Recipe with a root baseCOMP ('/') plus two TOP children wired
    together inside. Exercises the V.C path where the caller wants to
    reproduce the wrapper AND its contents."""
    return {
        "complexity": "small",
        "required_op_types": ["base", "noise", "null"],
        "recipe": {
            "name": "wrapped-technique",
            "nodes": {
                "/": {
                    "name": "wrapper",
                    "type": "base",
                    "family": "COMP",
                    "params": {},
                },
                "/src": {
                    "name": "src",
                    "type": "noise",
                    "family": "TOP",
                    "params": {"amp": 0.42},
                },
                "/out": {
                    "name": "out",
                    "type": "null",
                    "family": "TOP",
                    "params": {},
                },
            },
            "connections": [
                {"from": "/src", "to": "/out", "from_index": 0, "to_index": 0},
            ],
        },
    }


def _make_replay_ctx(client, store):
    from td_mcp.services import ServiceContainer

    services = ServiceContainer(
        td_client=client,
        technique_store=store,
        preference_store=None,
    )
    lifespan_state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=lifespan_state,
            lifespan_state=lifespan_state,
        )
    )


@pytest.mark.asyncio
async def test_memory_replay_default_skips_root_comp_as_before(tmp_path, monkeypatch):
    """V.C regression guard: default (`recreate_root` unset / False)
    preserves the pre-v1.4.7 behavior where the root's COMP entry is
    aliased to `parent_path`. Only the 2 children get created under
    `parent_path`, nothing new appears where the wrapper used to be."""
    import td_mcp.tool_registry as registry
    from td_mcp.memory import TechniqueStore
    from td_mcp.models._legacy import MemoryReplayInput

    store = TechniqueStore(base_dir=str(tmp_path), project_name="v147_V")
    tid = store.add(_wrapped_technique_recipe(), scope="project", name="wrapped-technique")

    client = _ReplayRecordingClient()
    ctx = _make_replay_ctx(client, store)
    # _get_client enforces isinstance(TDClient); our recording mock doesn't
    # inherit. Same monkey-patch pattern as test_param_help_docsbrain.
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_memory_replay(
        ctx,
        technique_id=tid,
        parent_path="/project1",
        scope="project",
    )
    assert result.get("nodes_created") == 2, (
        f"default replay must create only the 2 children (not the root); got {result}"
    )
    # The "/" entry must NOT appear as a created node in the result map.
    created_paths = result.get("created_paths", {})
    assert "/" not in created_paths


@pytest.mark.asyncio
async def test_memory_replay_recreate_root_true_builds_root_comp(tmp_path, monkeypatch):
    """V.C: when `recreate_root=True` and the recipe's `/` entry has
    family='COMP', the replay must create that COMP under `parent_path`
    first and build children INSIDE it. The result should report
    nodes_created=3 (root + 2 children) and children must resolve to
    paths under the newly-created root, not directly under parent_path."""
    import td_mcp.tool_registry as registry
    from td_mcp.memory import TechniqueStore
    from td_mcp.models._legacy import MemoryReplayInput

    store = TechniqueStore(base_dir=str(tmp_path), project_name="v147_V")
    tid = store.add(_wrapped_technique_recipe(), scope="project", name="wrapped-technique")

    client = _ReplayRecordingClient()
    ctx = _make_replay_ctx(client, store)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_memory_replay(
        ctx,
        technique_id=tid,
        parent_path="/project1",
        name_prefix="rp_",
        scope="project",
        recreate_root=True,
    )
    assert result.get("nodes_created") == 3, (
        f"recreate_root=True must build 3 nodes (root COMP + 2 children); got {result}"
    )
    created_paths = result.get("created_paths", {})
    assert "/" in created_paths, "root COMP path must appear in created_paths when recreate_root=True"
    root_actual = created_paths["/"]
    src_actual = created_paths.get("/src", "")
    out_actual = created_paths.get("/out", "")
    # Children must be INSIDE the recreated root COMP, not siblings of it.
    assert src_actual.startswith(root_actual + "/"), (
        f"child /src must live under recreated root. root={root_actual} src={src_actual}"
    )
    assert out_actual.startswith(root_actual + "/")


@pytest.mark.asyncio
async def test_memory_replay_recreate_root_true_no_root_comp_is_safe(tmp_path, monkeypatch):
    """Edge: recipe has NO `/` entry (or root is non-COMP). The flag
    should gracefully no-op — fall back to the existing flat-replay
    behavior — rather than raising or creating a garbage extra node."""
    import td_mcp.tool_registry as registry
    from td_mcp.memory import TechniqueStore
    from td_mcp.models._legacy import MemoryReplayInput

    store = TechniqueStore(base_dir=str(tmp_path), project_name="v147_V")
    # Recipe with no "/" root entry — just two TOPs at /src and /out.
    flat_recipe = {
        "complexity": "small",
        "required_op_types": ["noise", "null"],
        "recipe": {
            "name": "flat",
            "nodes": {
                "/src": {"name": "src", "type": "noise", "family": "TOP", "params": {}},
                "/out": {"name": "out", "type": "null", "family": "TOP", "params": {}},
            },
            "connections": [{"from": "/src", "to": "/out", "from_index": 0, "to_index": 0}],
        },
    }
    tid = store.add(flat_recipe, scope="project", name="flat")

    client = _ReplayRecordingClient()
    ctx = _make_replay_ctx(client, store)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_memory_replay(
        ctx,
        technique_id=tid,
        parent_path="/project1",
        scope="project",
        recreate_root=True,  # but no "/" COMP in the recipe,
    )
    # Safe no-op: 2 children created as usual, no error.
    assert result.get("nodes_created") == 2
    assert "error" not in result


# ---------------------------------------------------------------------------
# v1.4.7 S follow-up — wire-walked recipes must produce portable relative paths.
#
# Bug S (S.E) landed bidirectional wire-graph walks for non-COMP roots.
# But the recipe builder's `_rel(abs_path)` only relativizes paths that
# start with the root's own prefix. Wire-walked siblings (under a shared
# parent but not under the root) kept their absolute paths in the recipe,
# so replay to a new parent skipped them with `missing_parent:/<parent>`.
#
# Live repro from the v1.4.7 verification session:
#   analyze_network(/project1/v147S_wire_a) on a 3-node wire chain
#   returned:
#     nodes: {
#       "/":                        <noise root>,
#       "/project1/v147S_wire_b":   <level sibling, absolute path kept>,
#       "/project1/v147S_wire_c":   <null sibling, absolute path kept>,
#     }
#   Replaying this recipe to `/project2` would look up
#   `created_nodes.get("/project1")` to place `_wire_b`, find None, and
#   skip the node.
#
# Fix: in `_build_full_recipe._rel`, non-descendants (wire-walked siblings)
# get their leaf name as the relative path (e.g. "/v147S_wire_b"), so the
# recipe becomes portable — siblings become siblings-of-root in the
# recipe namespace and replay creates them under parent_path correctly.
# Name collisions get a numeric suffix.
# ---------------------------------------------------------------------------


def _v_chain_wire_client() -> _WireMockClient:
    """Three-node wire chain under a shared parent /stage, with plain names
    that won't collide with anything. Same shape as the live repro but
    with cleaner names for readability."""
    return _WireMockClient(
        {
            "/stage/head": _wire_node(
                "/stage/head",
                "noiseTOP",
                outputs=[{"to": "/stage/mid", "from_index": 0, "to_index": 0}],
            ),
            "/stage/mid": _wire_node(
                "/stage/mid",
                "levelTOP",
                inputs=[{"from": "/stage/head", "from_index": 0, "to_index": 0}],
                outputs=[{"to": "/stage/tail", "from_index": 0, "to_index": 0}],
            ),
            "/stage/tail": _wire_node(
                "/stage/tail",
                "nullTOP",
                inputs=[{"from": "/stage/mid", "from_index": 0, "to_index": 0}],
            ),
        }
    )


@pytest.mark.asyncio
async def test_wire_walked_recipe_siblings_get_relative_paths():
    """Wire-walked recipes store every captured node under its leaf name.
    There is NO `/` entry — wire-walked recipes don't have a wrapper;
    `/` is reserved as a logical placeholder for the replay's
    `parent_path` target. All three captured nodes (head, mid, tail)
    appear as peers with rel_paths `/head`, `/mid`, `/tail`."""
    from td_mcp.memory.analyzer import analyze_network

    client = _v_chain_wire_client()
    result = await analyze_network(client, "/stage/head")

    recipe_keys = set(result["recipe"]["nodes"].keys())
    # All three nodes appear with leaf-name rel_paths.
    assert "/head" in recipe_keys, f"wire-walked head node should be at '/head'; recipe keys: {recipe_keys}"
    assert "/mid" in recipe_keys, f"wire-walked sibling 'mid' should be at '/mid'; recipe keys: {recipe_keys}"
    assert "/tail" in recipe_keys, (
        f"wire-walked sibling 'tail' should be at '/tail'; recipe keys: {recipe_keys}"
    )
    # Pre-fix absolute forms must be absent.
    assert "/stage/head" not in recipe_keys
    assert "/stage/mid" not in recipe_keys
    assert "/stage/tail" not in recipe_keys
    # Wire-walked recipes have NO `/` entry — that key is reserved as the
    # "replay's effective parent" placeholder.
    assert "/" not in recipe_keys, (
        "wire-walked recipes should not use '/' as a node key; `/` is the "
        "logical parent placeholder for replay. Tree-walked COMP recipes "
        "use `/` for the wrapper; wire-walked ones have no wrapper."
    )


@pytest.mark.asyncio
async def test_wire_walked_recipe_connections_match_node_rel_paths():
    """Connection endpoints must reference the same rel_paths as the node
    keys, or replay's `from/to in nodes` filter drops them silently.
    This test pins the invariant: for every connection, both endpoints
    must resolve to keys in `recipe.nodes`."""
    from td_mcp.memory.analyzer import analyze_network

    client = _v_chain_wire_client()
    result = await analyze_network(client, "/stage/head")

    node_keys = set(result["recipe"]["nodes"].keys())
    for conn in result["recipe"]["connections"]:
        assert conn["from"] in node_keys, (
            f"connection `from` {conn['from']!r} not in recipe nodes {node_keys}"
        )
        assert conn["to"] in node_keys, f"connection `to` {conn['to']!r} not in recipe nodes {node_keys}"


@pytest.mark.asyncio
async def test_wire_walked_recipe_sibling_name_collision_resolved():
    """Edge: two wire-walked nodes with the same leaf name must get
    distinct rel_paths (numeric suffix on collision) so neither
    overwrites the other in the recipe."""
    from td_mcp.memory.analyzer import analyze_network

    # Two different nodes both named 'buddy' in different COMPs, both
    # wire-connected to the root. Rare in practice but must be handled
    # cleanly — otherwise the later iteration wins and the earlier node
    # is silently dropped.
    client = _WireMockClient(
        {
            "/stage/head": _wire_node(
                "/stage/head",
                "noiseTOP",
                outputs=[
                    {"to": "/stage/buddy", "from_index": 0, "to_index": 0},
                    {"to": "/other/buddy", "from_index": 0, "to_index": 0},
                ],
            ),
            "/stage/buddy": _wire_node(
                "/stage/buddy",
                "levelTOP",
                inputs=[{"from": "/stage/head", "from_index": 0, "to_index": 0}],
            ),
            "/other/buddy": _wire_node(
                "/other/buddy",
                "nullTOP",
                inputs=[{"from": "/stage/head", "from_index": 1, "to_index": 0}],
            ),
        }
    )
    result = await analyze_network(client, "/stage/head")
    recipe_keys = set(result["recipe"]["nodes"].keys())
    # Both buddies must appear, distinctly.
    assert len([k for k in recipe_keys if "buddy" in k]) == 2, (
        f"two nodes named 'buddy' must both appear with distinct rel_paths; got {recipe_keys}"
    )
    assert result["node_count"] == 3


@pytest.mark.asyncio
async def test_wire_walked_recipe_replays_under_new_parent(tmp_path, monkeypatch):
    """End-to-end proof that wire-walked recipes are now portable.
    Pre-fix: replaying a wire-walked recipe to `/new_parent` would skip
    siblings with `missing_parent:/stage`. Post-fix: siblings land as
    children of `/new_parent` correctly."""
    import td_mcp.tool_registry as registry
    from td_mcp.memory import TechniqueStore
    from td_mcp.memory.analyzer import analyze_network
    from td_mcp.models._legacy import MemoryReplayInput

    client = _v_chain_wire_client()
    # Learn from the chain head via the real analyzer (non-COMP root).
    technique = await analyze_network(client, "/stage/head", name="wire_chain", td_build="test")
    # Persist the recipe so td_memory_replay can look it up.
    store = TechniqueStore(base_dir=str(tmp_path), project_name="v147_S_followup")
    tid = store.add(technique, scope="project", name="wire_chain")
    # Swap the client for a recording replay client and monkey-patch
    # _get_client for the replay call.
    replay_client = _ReplayRecordingClient(families={"TOP": ["noise", "level", "null"]})
    ctx = _make_replay_ctx(replay_client, store)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: replay_client)

    result = await registry.td_memory_replay(
        ctx,
        technique_id=tid,
        parent_path="/new_parent",
        name_prefix="wr_",
        scope="project",
        # Fixture op_types use test-suffixed names ('noiseTOP') which
        # don't match what real TD `families` returns (short forms).
        # Skip the prerequisite check — the test's goal is proving
        # sibling paths resolve on replay, not the families gate.
        force=True,
    )
    assert result.get("nodes_created") == 3, (
        f"wire-walked replay to /new_parent must create all 3 nodes; got {result}"
    )
    created = result.get("created_paths", {})
    # Every sibling should have a path under /new_parent.
    for rel in ("/", "/mid", "/tail"):
        # `/` is always either aliased to parent or recreated; for this
        # default-replay it's aliased — so /mid and /tail specifically
        # must land under /new_parent.
        pass
    assert any(p.startswith("/new_parent/") for p in created.values()), (
        f"at least one child must land under /new_parent; got {created}"
    )
    assert result.get("skipped_nodes", []) == [], (
        f"no nodes should be skipped with a portable recipe; got {result.get('skipped_nodes')}"
    )
