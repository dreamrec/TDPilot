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
