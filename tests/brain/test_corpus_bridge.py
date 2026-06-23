from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain import atlas_drafter
from td_mcp.brain.corpus_bridge import build_corpus_evidence
from td_mcp.brain.planner import build_brain_plan


def _operator_card(op_type: str, summary: str, *, params: list[str] | None = None) -> dict:
    family = next(
        (
            suffix
            for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP")
            if op_type.endswith(suffix)
        ),
        "TOP",
    )
    return {
        "card_type": "operator",
        "op_type": op_type,
        "family": family,
        "display_name": op_type,
        "docs_url": f"https://docs.derivative.ca/{op_type}",
        "summary": summary,
        "key_params": [{"name": name, "type": "Float", "note": f"{name} control"} for name in params or []],
        "key_concepts": ["feedback", "operator evidence"] if "feedback" in summary.lower() else [],
    }


class SearchableCardIndex:
    def __init__(self, cards: dict[str, dict]):
        self.cards = cards
        self.search_calls: list[dict] = []

    def get_operator(self, op_type: str):
        return self.cards.get(op_type)

    def search(
        self,
        query: str,
        card_types: list[str] | None = None,
        family: str | None = None,
        limit: int = 10,
    ):
        self.search_calls.append({"query": query, "card_types": card_types, "family": family, "limit": limit})
        haystack = query.lower()
        hits = []
        for card in self.cards.values():
            text = " ".join(str(card.get(key, "")) for key in ("op_type", "display_name", "summary")).lower()
            if any(token in text for token in haystack.split()):
                hits.append(card)
        hits.append(
            {
                "card_type": "operator",
                "op_type": "blogTOP",
                "summary": "Third-party blog mirror with no official citation.",
            }
        )
        return hits[:limit]


def test_corpus_bridge_returns_exact_search_and_local_rerank_records():
    cards = {
        "feedbackTOP": _operator_card(
            "feedbackTOP",
            "Recursive feedback trails with target TOP reset and decay.",
            params=["top", "reset", "resetpulse"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Image level correction for feedback decay and brightness shaping.",
            params=["opacity", "brightness"],
        ),
    }
    index = SearchableCardIndex(cards)

    records = build_corpus_evidence(
        intent="build recursive feedback trails with decay",
        operators=["feedbackTOP", "levelTOP"],
        card_index=index,
    )

    evidence_ids = [record.evidence_id for record in records]
    assert "corpus:exact:feedbackTOP" in evidence_ids
    assert "corpus:exact:levelTOP" in evidence_ids
    assert "corpus:search:feedbackTOP" in evidence_ids
    assert all(record.docs_url.startswith("https://docs.derivative.ca/") for record in records)
    assert all(0.0 <= record.score <= 1.0 for record in records)
    feedback_exact = next(record for record in records if record.evidence_id == "corpus:exact:feedbackTOP")
    assert feedback_exact.key_params == ["top", "reset", "resetpulse"]
    assert feedback_exact.matched_terms
    assert "corpus:search:blogTOP" not in evidence_ids
    assert index.search_calls


@pytest.mark.asyncio
async def test_feedback_plan_carries_structured_corpus_evidence_when_docs_are_enabled():
    operators = ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"]
    cards = {
        op_type: _operator_card(op_type, f"{op_type} official feedback planning docs")
        for op_type in operators
    }
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": operators}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="build a clean feedback displacement loop",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=SearchableCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert any(record.op_type == "feedbackTOP" for record in plan.corpus_evidence)
    assert any(record.source == "docs_search" for record in plan.corpus_evidence)
    assert "corpus:exact:feedbackTOP" in plan.grounding_evidence
    assert any(item.startswith("corpus:search:") for item in plan.grounding_evidence)


@pytest.mark.asyncio
async def test_plan_omits_corpus_evidence_when_docs_are_disabled():
    operators = ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"]
    cards = {
        op_type: _operator_card(op_type, f"{op_type} official feedback planning docs")
        for op_type in operators
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": operators}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="build a clean feedback displacement loop",
        target_root="/project1",
        include_docs=False,
        card_index=index,
    )

    assert plan.corpus_evidence == []
    assert not any(item.startswith("corpus:") for item in plan.grounding_evidence)
    assert index.search_calls == []


@pytest.mark.asyncio
async def test_open_prompt_plans_atlas_grounded_candidate_topology():
    cases = [
        (
            "volumetric organic light field with fluid caustic motion",
            {
                "noiseTOP": _operator_card(
                    "noiseTOP",
                    "Volumetric organic light field texture source for fluid caustic motion.",
                ),
                "levelTOP": _operator_card(
                    "levelTOP",
                    "Brightness shaping and contrast control for organic light visuals.",
                ),
                "nullTOP": _operator_card("nullTOP", "Stable TOP output for inspected light visuals."),
            },
            "noiseTOP",
        ),
        (
            "depth tracked body silhouette sculpture with skeletal presence",
            {
                "kinectazureTOP": _operator_card(
                    "kinectazureTOP",
                    "Depth tracked body silhouette imagery and sensor input for skeletal presence.",
                ),
                "nullTOP": _operator_card("nullTOP", "Stable TOP output for inspected sensor imagery."),
            },
            "kinectazureTOP",
        ),
        (
            "kinetic typography projection mapping with layered text fields",
            {
                "textTOP": _operator_card(
                    "textTOP",
                    "Typography and layered text fields for projection mapping compositions.",
                ),
                "transformTOP": _operator_card("transformTOP", "Kinetic placement and texture transforms."),
                "nullTOP": _operator_card("nullTOP", "Stable TOP output for projection texture inspection."),
            },
            "textTOP",
        ),
    ]

    for intent, cards, expected_op in cases:
        index = SearchableCardIndex(cards)
        client = FakeTDClient(
            scripted={
                "families": {"families": {"TOP": list(cards)}},
                "nodes": {"nodes": []},
            }
        )

        plan = await build_brain_plan(
            client,
            intent=intent,
            target_root="/project1",
            card_index=index,
        )

        assert plan.concept_graph.profile == "generic"
        assert plan.blocked_questions == []
        assert plan.missing_facts == []
        assert plan.candidate_graphs
        assert expected_op in plan.candidate_graphs[0].required_ops
        assert plan.patch_plan.operations
        assert any(
            op.kind == "create_node" and op.args["op_type"] == expected_op
            for op in plan.patch_plan.operations
        )
        assert "planner:open_prompt_atlas_drafted" in plan.grounding_evidence
        assert any(item.startswith("operator-intent:") for item in plan.grounding_evidence)
        assert any(record.op_type == expected_op for record in plan.corpus_evidence)
        assert any(item.startswith("corpus:search:") for item in plan.grounding_evidence)


@pytest.mark.asyncio
async def test_open_prompt_synthesizes_topology_from_retrieved_operator_cards():
    cards = {
        "moviefileinTOP": _operator_card(
            "moviefileinTOP",
            "Cinematic video texture source for delayed cached frame treatments.",
        ),
        "cacheTOP": _operator_card(
            "cacheTOP",
            "Stores cached frames for delayed visual trails and temporal texture offsets.",
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Gentle color shaping and level correction for cinematic video texture output.",
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for final video texture inspection.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": list(cards)}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="cinematic delayed video texture with cached frames and gentle color shaping",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    candidate = plan.candidate_graphs[0]
    assert candidate.required_ops == ["moviefileinTOP", "cacheTOP", "levelTOP", "nullTOP"]
    assert candidate.pattern_ids == ["atlas:synthesized:top_card_chain"]
    assert "atlas-synthesis:accepted" in plan.grounding_evidence
    assert "atlas-synthesis:source:moviefileinTOP" in plan.grounding_evidence
    assert "atlas-synthesis:process:cacheTOP" in plan.grounding_evidence
    assert "atlas-synthesis:process:levelTOP" in plan.grounding_evidence
    assert "atlas-synthesis:output:nullTOP" in plan.grounding_evidence
    assert "docs:blogTOP" not in plan.grounding_evidence
    assert "blogTOP" not in candidate.required_ops
    assert "atlas_synthesis:retrieved_cards" in candidate.explanation
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_synthesizes_multi_domain_dat_controlled_topology():
    cards = {
        "tableDAT": _operator_card(
            "tableDAT",
            "Scene cue table DAT source for a small table of looks and switch control rows.",
            params=["rows", "cols"],
        ),
        "selectDAT": _operator_card(
            "selectDAT",
            "Selects a cue row from a table DAT for control routing.",
            params=["rowselect", "colselect"],
        ),
        "moviefileinTOP": _operator_card(
            "moviefileinTOP",
            "Video texture source for a cue driven visual switcher.",
            params=["file"],
        ),
        "switchTOP": _operator_card(
            "switchTOP",
            "Switches between TOP inputs using a DAT driven index control.",
            params=["index", "blend"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for the final switched visual texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["tableDAT", "selectDAT"],
                    "TOP": ["moviefileinTOP", "switchTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="cue sheet controlled video selector with scene looks and final TOP output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:dat_controlled_top_card_chain"]
    assert candidate.required_ops == ["tableDAT", "selectDAT", "moviefileinTOP", "switchTOP", "nullTOP"]
    assert {concept.domain for concept in candidate.concepts} == {"DAT", "TOP"}
    assert any(
        edge.kind == "control" and edge.source == "control_stage_selectdat" for edge in candidate.edges
    )
    assert "atlas-synthesis:multi-domain:dat-to-top" in plan.grounding_evidence
    assert "atlas-synthesis:control:tableDAT" in plan.grounding_evidence
    assert "atlas-synthesis:control:selectDAT" in plan.grounding_evidence
    assert "atlas-synthesis:process:switchTOP" in plan.grounding_evidence
    assert "param-semantics-draft:switchTOP.blend:needs-live-readback" in plan.grounding_evidence
    assert "param-semantics-drafts-need-review" in plan.risk_flags
    connections = [op for op in plan.patch_plan.operations if op.kind == "connect"]
    assert all(
        not (op.args["from"].endswith("/selectdat") and op.args["to"].endswith("/switch"))
        for op in connections
    )
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_routes_udp_packets_to_stable_dat_output():
    cards = {
        "udpinDAT": _operator_card(
            "udpinDAT",
            "UDP network packet ingest source that appends received messages to a DAT table.",
            params=["protocol", "port", "active", "clamp", "maxlines"],
        ),
        "nullDAT": _operator_card(
            "nullDAT",
            "Stable DAT table output for downstream packet consumers.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["udpinDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="listen for udp packets and expose a stable table output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:udp_dat_table_ingest"]
    assert candidate.required_ops == ["udpinDAT", "nullDAT"]
    assert candidate.validation_needs == ["protocol_table_output", "output_node_present"]
    assert "device-source-required" in candidate.risk_flags
    assert "operator-intent:udp_dat_table_ingest" in plan.grounding_evidence
    assert plan.patch_plan.required_ops == ["udpinDAT", "nullDAT"]
    assert plan.patch_plan.validation_plan.capture_frames == []


@pytest.mark.asyncio
async def test_open_prompt_routes_protocol_messages_to_stable_dat_output():
    cases = [
        (
            "read COM port sensor messages into a stable table output",
            "serial_dat_table_ingest",
            "serialDAT",
            "Serial device message ingest source that appends sensor rows to a DAT table.",
            ["port", "baudrate", "active", "clamp", "maxlines"],
        ),
        (
            "listen for osc messages and expose a stable table output",
            "osc_dat_table_ingest",
            "oscinDAT",
            "OSC message ingest source that appends address rows to a DAT table.",
            ["port", "address", "active", "clamp", "maxlines"],
        ),
        (
            "connect to websocket messages and expose a stable table output",
            "websocket_dat_table_ingest",
            "websocketDAT",
            "WebSocket endpoint message source that appends messages to a DAT table.",
            ["netaddress", "port", "active", "clamp", "maxlines"],
        ),
        (
            "subscribe to mqtt topic messages and expose a stable table output",
            "mqtt_dat_table_ingest",
            "mqttclientDAT",
            "MQTT broker topic message source that appends payloads to a DAT table.",
            ["netaddress", "keepalive", "active", "clamp", "maxlines"],
        ),
    ]

    for intent, route_id, source_op, summary, params in cases:
        cards = {
            source_op: _operator_card(source_op, summary, params=params),
            "nullDAT": _operator_card(
                "nullDAT",
                "Stable DAT table output for downstream message consumers.",
            ),
        }
        index = SearchableCardIndex(cards)
        client = FakeTDClient(
            scripted={
                "families": {
                    "families": {
                        "DAT": [source_op, "nullDAT"],
                    }
                },
                "nodes": {"nodes": []},
            }
        )

        plan = await build_brain_plan(
            client,
            intent=intent,
            target_root="/project1",
            card_index=index,
        )

        assert plan.blocked_questions == []
        candidate = plan.candidate_graphs[0]
        assert candidate.pattern_ids == [f"atlas:{route_id}"]
        assert candidate.required_ops == [source_op, "nullDAT"]
        assert candidate.validation_needs == ["protocol_table_output", "output_node_present"]
        assert "device-source-required" in candidate.risk_flags
        assert f"operator-intent:{route_id}" in plan.grounding_evidence
        assert plan.patch_plan.required_ops == [source_op, "nullDAT"]
        assert plan.patch_plan.validation_plan.capture_frames == []


@pytest.mark.asyncio
async def test_open_prompt_prefers_typed_dat_role_graph_when_table_stage_is_grounded():
    cards = {
        "serialDAT": _operator_card(
            "serialDAT",
            "Serial device message source for COM port sensor rows.",
            params=["port", "baudrate", "active", "clamp", "maxlines"],
        ),
        "tableDAT": _operator_card(
            "tableDAT",
            "Table DAT processing stage that normalizes received sensor rows for diagnostics.",
            params=["rows", "cols"],
        ),
        "nullDAT": _operator_card(
            "nullDAT",
            "Stable DAT table output for downstream normalized row consumers.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["serialDAT", "tableDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="read COM port sensor rows into a normalized table output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_role_graph_dat_pipeline_card_chain"]
    assert candidate.required_ops == ["serialDAT", "tableDAT", "nullDAT"]
    assert candidate.validation_needs == ["protocol_table_output", "output_node_present"]
    assert "atlas-typed-role-graph" in candidate.risk_flags
    assert "device-source-required" in candidate.risk_flags
    assert "atlas-synthesis:typed-role-graph" in candidate.grounding_evidence
    assert "atlas-synthesis:role-graph:source->process->output" in candidate.grounding_evidence
    assert "atlas-synthesis:source:serialDAT" in candidate.grounding_evidence
    assert "atlas-synthesis:process:tableDAT" in candidate.grounding_evidence
    assert "atlas-synthesis:output:nullDAT" in candidate.grounding_evidence
    assert "roles:source->process->output" in candidate.explanation
    assert "operators:serialDAT,tableDAT,nullDAT" in candidate.explanation
    assert [(edge.source, edge.target, edge.kind) for edge in candidate.edges] == [
        ("dat_source", "dat_stage_tabledat", "data"),
        ("dat_stage_tabledat", "output", "data"),
    ]
    assert plan.patch_plan.required_ops == ["serialDAT", "tableDAT", "nullDAT"]
    assert plan.patch_plan.validation_plan.capture_frames == []


@pytest.mark.asyncio
async def test_open_prompt_synthesizes_chop_controlled_topology():
    cards = {
        "lfoCHOP": _operator_card(
            "lfoCHOP",
            "Oscillator CHOP source for repeating control signals and modulation.",
            params=["frequency", "amplitude"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Scales and remaps CHOP channels for brightness control ranges.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for exported modulation control channels.",
        ),
        "noiseTOP": _operator_card(
            "noiseTOP",
            "Procedural texture source for a brightness wash visual.",
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Brightness and level adjustment stage for a procedural texture.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for the final controlled texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["lfoCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="oscillator controlled brightness wash over procedural texture with final TOP output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:chop_controlled_top_card_chain"]
    assert candidate.required_ops == ["lfoCHOP", "mathCHOP", "nullCHOP", "noiseTOP", "levelTOP", "nullTOP"]
    assert {concept.domain for concept in candidate.concepts} == {"CHOP", "TOP"}
    assert any(
        edge.kind == "control"
        and edge.source == "control_stage_nullchop"
        and edge.target == "visual_stage_leveltop"
        for edge in candidate.edges
    )
    assert "atlas-synthesis:multi-domain:chop-to-top" in plan.grounding_evidence
    assert "atlas-synthesis:control:mathCHOP" in plan.grounding_evidence
    assert "atlas-synthesis:output:nullCHOP" in plan.grounding_evidence
    assert "atlas-synthesis:process:levelTOP" in plan.grounding_evidence
    connections = [op for op in plan.patch_plan.operations if op.kind == "connect"]
    assert all(
        not (op.args["from"].endswith("/nullchop") and op.args["to"].endswith("/level")) for op in connections
    )
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_synthesizes_chop_controlled_topology_with_binding():
    cards = {
        "lfoCHOP": _operator_card(
            "lfoCHOP",
            "Oscillator CHOP source for repeating control signals and modulation.",
            params=["frequency", "amp"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Scales and remaps CHOP channels for brightness control ranges.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for exported modulation control channels.",
        ),
        "noiseTOP": _operator_card(
            "noiseTOP",
            "Procedural texture source for a brightness wash visual.",
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Brightness and level adjustment stage for a procedural texture.",
            params=["brightness1", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for the final controlled texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["lfoCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="oscillator export binding controls brightness over a procedural texture",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    level_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/level")
    ]
    assert level_params
    assert level_params[0].args["params"] == {"brightness1": {"expr": "op('/project1/out_chop')[0]"}}
    assert "atlas-synthesis:binding:out_chop->levelTOP.brightness1" in plan.grounding_evidence
    assert any(
        marker.startswith("atlas-synthesis:topology-role-relevance:1:")
        and "control:" in marker
        and "output:" in marker
        for marker in plan.grounding_evidence
    )
    assert "atlas-synthesis:topology-role-family:1:control:CHOP:1" in plan.grounding_evidence
    assert "topology_role_relevance:" in plan.candidate_graphs[0].explanation


@pytest.mark.asyncio
async def test_open_prompt_uses_typed_role_graph_for_chop_top_without_curated_route_terms():
    cards = {
        "waveCHOP": _operator_card(
            "waveCHOP",
            "Waveform signal source for repeating channel curves.",
            params=["wavetype", "period", "amp"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for channel signals.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable channel output for shaped signals.",
        ),
        "noiseTOP": _operator_card(
            "noiseTOP",
            "Procedural texture wash source.",
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Image level shaping stage for texture wash.",
            params=["brightness1", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for final texture wash.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["waveCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="waveform signal shapes procedural texture wash into stable output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_role_graph_chop_top_card_chain"]
    assert candidate.required_ops == [
        "waveCHOP",
        "mathCHOP",
        "nullCHOP",
        "noiseTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"CHOP", "TOP"}
    assert any(
        edge.kind == "control"
        and edge.source == "control_stage_nullchop"
        and edge.target == "visual_stage_leveltop"
        for edge in candidate.edges
    )
    level_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/level")
    ]
    assert level_params
    assert level_params[0].args["params"] == {"brightness1": {"expr": "op('/project1/out_chop')[0]"}}
    assert "atlas-synthesis:typed-role-graph" in plan.grounding_evidence
    assert "atlas-synthesis:role-graph:control->visual" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_open_prompt_uses_typed_bridge_graph_for_dat_to_chop_output():
    cards = {
        "tableDAT": _operator_card(
            "tableDAT",
            "Table DAT source containing sensor rows for channel conversion.",
            params=["rows", "cols"],
        ),
        "selectDAT": _operator_card(
            "selectDAT",
            "Select DAT processing stage that extracts numeric sensor rows.",
            params=["rowselect", "colselect"],
        ),
        "dattoCHOP": _operator_card(
            "dattoCHOP",
            "DAT to CHOP bridge converts selected DAT rows into CHOP channels.",
            params=["dat"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for normalized channel values.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for normalized sensor channels.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["tableDAT", "selectDAT"],
                    "CHOP": ["dattoCHOP", "mathCHOP", "nullCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="sensor table rows become normalized channels with stable output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_dat_to_chop_card_chain"]
    assert candidate.required_ops == ["tableDAT", "selectDAT", "dattoCHOP", "mathCHOP", "nullCHOP"]
    assert {concept.domain for concept in candidate.concepts} == {"DAT", "CHOP"}
    assert [(edge.source, edge.target, edge.kind) for edge in candidate.edges] == [
        ("source", "source_stage_selectdat", "data"),
        ("source_stage_selectdat", "bridge_stage_dattochop", "reference"),
        ("bridge_stage_dattochop", "target_stage_mathchop", "data"),
        ("target_stage_mathchop", "output", "data"),
    ]
    bridge_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/datto")
    ]
    assert bridge_params
    assert bridge_params[0].args["params"]["dat"].endswith("/select")
    assert "atlas-synthesis:typed-role-graph-search" in plan.grounding_evidence
    assert "atlas-synthesis:role-graph:source->bridge->process->output" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:DAT->CHOP:dattoCHOP" in plan.grounding_evidence
    assert "atlas_synthesis:typed_graph_search" in candidate.explanation
    assert plan.patch_plan.required_ops == ["tableDAT", "selectDAT", "dattoCHOP", "mathCHOP", "nullCHOP"]
    assert plan.patch_plan.validation_plan.capture_frames == []


@pytest.mark.asyncio
async def test_open_prompt_uses_stable_source_output_before_typed_chop_to_top_bridge():
    cards = {
        "lfoCHOP": _operator_card(
            "lfoCHOP",
            "Oscillator CHOP source for repeating control signals and modulation.",
            params=["frequency", "amplitude"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for normalized control channels.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for exported modulation control channels.",
        ),
        "choptoTOP": _operator_card(
            "choptoTOP",
            "CHOP to TOP bridge converts control channels into a texture image.",
            params=["chop", "dataformat"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Texture shaping stage after channel conversion.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for the converted control texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["lfoCHOP", "mathCHOP", "nullCHOP", "choptoTOP"],
                    "TOP": ["levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="normalized oscillator channels become a texture output through a CHOP to TOP bridge",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_chop_to_top_card_chain"]
    assert candidate.required_ops == ["lfoCHOP", "mathCHOP", "nullCHOP", "choptoTOP", "levelTOP", "nullTOP"]
    assert {concept.domain for concept in candidate.concepts} == {"CHOP", "TOP"}
    assert [(edge.source, edge.target, edge.kind) for edge in candidate.edges] == [
        ("source", "source_stage_mathchop", "data"),
        ("source_stage_mathchop", "source_stage_nullchop", "data"),
        ("source_stage_nullchop", "bridge_stage_choptotop", "reference"),
        ("bridge_stage_choptotop", "target_stage_leveltop", "data"),
        ("target_stage_leveltop", "output", "data"),
    ]
    bridge_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/chopto")
    ]
    assert bridge_params
    assert bridge_params[0].args["params"]["chop"].endswith("/out_chop")
    assert "atlas-synthesis:typed-role-graph-search" in plan.grounding_evidence
    assert "atlas-synthesis:role-graph:source->bridge->process->output" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:CHOP->TOP:choptoTOP" in plan.grounding_evidence
    assert "atlas-synthesis:output:nullCHOP" in plan.grounding_evidence
    assert "operators:lfoCHOP,mathCHOP,nullCHOP,choptoTOP,levelTOP,nullTOP" in candidate.explanation
    assert plan.patch_plan.required_ops == [
        "lfoCHOP",
        "mathCHOP",
        "nullCHOP",
        "choptoTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_searches_multi_hop_typed_bridge_graph_from_dat_to_top():
    cards = {
        "tableDAT": _operator_card(
            "tableDAT",
            "Table DAT source containing sensor rows that should become texture pixels.",
            params=["rows", "cols"],
        ),
        "selectDAT": _operator_card(
            "selectDAT",
            "Select DAT processing stage that extracts normalized numeric sensor rows.",
            params=["rowselect", "colselect"],
        ),
        "dattoCHOP": _operator_card(
            "dattoCHOP",
            "DAT to CHOP bridge converts selected DAT rows into CHOP channels.",
            params=["dat"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for normalized channel values.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for normalized sensor channels.",
        ),
        "choptoTOP": _operator_card(
            "choptoTOP",
            "CHOP to TOP bridge converts normalized channels into texture pixels.",
            params=["chop", "dataformat"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Texture shaping stage after channel conversion.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for the converted sensor texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["tableDAT", "selectDAT"],
                    "CHOP": ["dattoCHOP", "mathCHOP", "nullCHOP", "choptoTOP"],
                    "TOP": ["levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="sensor table rows become normalized channels and then a texture output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_dat_to_chop_to_top_card_chain"]
    assert candidate.required_ops == [
        "tableDAT",
        "selectDAT",
        "dattoCHOP",
        "mathCHOP",
        "nullCHOP",
        "choptoTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"DAT", "CHOP", "TOP"}
    assert [(edge.source, edge.target, edge.kind) for edge in candidate.edges] == [
        ("source", "source_stage_selectdat", "data"),
        ("source_stage_selectdat", "bridge_stage_dattochop", "reference"),
        ("bridge_stage_dattochop", "mid_stage_mathchop", "data"),
        ("mid_stage_mathchop", "mid_stage_nullchop", "data"),
        ("mid_stage_nullchop", "bridge_stage_choptotop", "reference"),
        ("bridge_stage_choptotop", "target_stage_leveltop", "data"),
        ("target_stage_leveltop", "output", "data"),
    ]
    bridge_params = {
        op.target: op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and (op.target.endswith("/datto") or op.target.endswith("/chopto"))
    }
    assert any(params["dat"].endswith("/select") for params in bridge_params.values() if "dat" in params)
    assert any(params["chop"].endswith("/out_chop") for params in bridge_params.values() if "chop" in params)
    assert "atlas-synthesis:typed-bridge-graph-search:multi-hop" in plan.grounding_evidence
    assert (
        "atlas-synthesis:role-graph:source->bridge->process->output->bridge->process->output"
        in plan.grounding_evidence
    )
    assert "atlas-synthesis:bridge:DAT->CHOP:dattoCHOP" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:CHOP->TOP:choptoTOP" in plan.grounding_evidence
    assert "atlas-synthesis:source-output-before-bridge:nullCHOP" in plan.grounding_evidence
    assert (
        "operators:tableDAT,selectDAT,dattoCHOP,mathCHOP,nullCHOP,choptoTOP,levelTOP,nullTOP"
        in candidate.explanation
    )
    assert plan.patch_plan.required_ops == [
        "tableDAT",
        "selectDAT",
        "dattoCHOP",
        "mathCHOP",
        "nullCHOP",
        "choptoTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_searches_three_hop_typed_bridge_graph_from_dat_to_chop():
    cards = {
        "tableDAT": _operator_card(
            "tableDAT",
            "Table DAT source containing point rows for a generated point field.",
            params=["rows", "cols"],
        ),
        "selectDAT": _operator_card(
            "selectDAT",
            "Select DAT processing stage that extracts normalized point rows.",
            params=["rowselect", "colselect"],
        ),
        "dattoPOP": _operator_card(
            "dattoPOP",
            "DAT to POP bridge converts selected DAT rows into a POP point field.",
            params=["dat"],
        ),
        "noisePOP": _operator_card(
            "noisePOP",
            "Adds organic displacement to POP point fields.",
            params=["amplitude"],
        ),
        "nullPOP": _operator_card(
            "nullPOP",
            "Stable POP output for the generated point field.",
        ),
        "poptoTOP": _operator_card(
            "poptoTOP",
            "POP to TOP bridge previews a stable POP point field as texture pixels.",
            params=["pop"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Texture shaping stage for point field preview pixels.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for the point field preview texture.",
        ),
        "toptoCHOP": _operator_card(
            "toptoCHOP",
            "TOP to CHOP bridge samples preview texture pixels into control channels.",
            params=["top"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for sampled preview channels.",
            params=["range1", "range2"],
        ),
        "outCHOP": _operator_card(
            "outCHOP",
            "Stable CHOP output for sampled preview control channels.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["tableDAT", "selectDAT"],
                    "POP": ["dattoPOP", "noisePOP", "nullPOP"],
                    "TOP": ["poptoTOP", "levelTOP", "nullTOP"],
                    "CHOP": ["toptoCHOP", "mathCHOP", "outCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="sensor table point rows become a POP preview texture sampled into control channels",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == [
        "atlas:synthesized:typed_bridge_graph_dat_to_pop_to_top_to_chop_card_chain"
    ]
    assert candidate.required_ops == [
        "tableDAT",
        "selectDAT",
        "dattoPOP",
        "noisePOP",
        "nullPOP",
        "poptoTOP",
        "levelTOP",
        "nullTOP",
        "toptoCHOP",
        "mathCHOP",
        "outCHOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"DAT", "POP", "TOP", "CHOP"}
    assert [(edge.source, edge.target, edge.kind) for edge in candidate.edges] == [
        ("source", "source_stage_selectdat", "data"),
        ("source_stage_selectdat", "bridge_stage_dattopop", "reference"),
        ("bridge_stage_dattopop", "mid_stage_noisepop", "data"),
        ("mid_stage_noisepop", "mid_stage_nullpop", "data"),
        ("mid_stage_nullpop", "bridge_stage_poptotop", "reference"),
        ("bridge_stage_poptotop", "mid2_stage_leveltop", "data"),
        ("mid2_stage_leveltop", "mid2_stage_nulltop", "data"),
        ("mid2_stage_nulltop", "bridge_stage_toptochop", "reference"),
        ("bridge_stage_toptochop", "target_stage_mathchop", "data"),
        ("target_stage_mathchop", "output", "data"),
    ]
    bridge_params = {
        op.target: op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params"
        and (op.target.endswith("/datto") or op.target.endswith("/popto") or op.target.endswith("/topto"))
    }
    assert any(params["dat"].endswith("/select") for params in bridge_params.values() if "dat" in params)
    assert any(params["pop"].endswith("/out_pop") for params in bridge_params.values() if "pop" in params)
    assert any(params["top"].endswith("/out1") for params in bridge_params.values() if "top" in params)
    assert "atlas-synthesis:typed-bridge-graph-search:multi-hop" in plan.grounding_evidence
    assert (
        "atlas-synthesis:role-graph:source->bridge->process->output->bridge->process->output->bridge->process->output"
        in plan.grounding_evidence
    )
    assert "atlas-synthesis:bridge:DAT->POP:dattoPOP" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:POP->TOP:poptoTOP" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:TOP->CHOP:toptoCHOP" in plan.grounding_evidence
    assert "atlas-synthesis:source-output-before-bridge:nullPOP" in plan.grounding_evidence
    assert "atlas-synthesis:source-output-before-bridge:nullTOP" in plan.grounding_evidence
    assert (
        "operators:tableDAT,selectDAT,dattoPOP,noisePOP,nullPOP,poptoTOP,levelTOP,nullTOP,"
        "toptoCHOP,mathCHOP,outCHOP"
    ) in candidate.explanation
    assert plan.patch_plan.required_ops == [
        "tableDAT",
        "selectDAT",
        "dattoPOP",
        "noisePOP",
        "nullPOP",
        "poptoTOP",
        "levelTOP",
        "nullTOP",
        "toptoCHOP",
        "mathCHOP",
        "outCHOP",
    ]
    assert plan.patch_plan.validation_plan.capture_frames == []


@pytest.mark.asyncio
async def test_open_prompt_searches_multi_hop_typed_bridge_graph_from_sop_to_top():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP mesh source grid for geometry preview.",
            params=["rows", "cols"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Displaces SOP surface before conversion.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP output for preview geometry.",
        ),
        "soptoPOP": _operator_card(
            "soptoPOP",
            "SOP to POP bridge converts stable SOP geometry into a POP point field.",
            params=["sop"],
        ),
        "noisePOP": _operator_card(
            "noisePOP",
            "Adds point displacement to converted POP fields.",
            params=["amplitude"],
        ),
        "nullPOP": _operator_card(
            "nullPOP",
            "Stable POP output before TOP preview.",
        ),
        "poptoTOP": _operator_card(
            "poptoTOP",
            "POP to TOP bridge previews stable POP point fields as texture pixels.",
            params=["pop"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Texture shaping stage for geometry preview pixels.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for geometry preview texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "POP": ["soptoPOP", "noisePOP", "nullPOP"],
                    "TOP": ["poptoTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="SOP mesh surface becomes a POP point preview texture output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_sop_to_pop_to_top_card_chain"]
    assert candidate.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "soptoPOP",
        "noisePOP",
        "nullPOP",
        "poptoTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"SOP", "POP", "TOP"}
    assert [(edge.source, edge.target, edge.kind) for edge in candidate.edges] == [
        ("source", "source_stage_noisesop", "data"),
        ("source_stage_noisesop", "source_stage_nullsop", "data"),
        ("source_stage_nullsop", "bridge_stage_soptopop", "reference"),
        ("bridge_stage_soptopop", "mid_stage_noisepop", "data"),
        ("mid_stage_noisepop", "mid_stage_nullpop", "data"),
        ("mid_stage_nullpop", "bridge_stage_poptotop", "reference"),
        ("bridge_stage_poptotop", "target_stage_leveltop", "data"),
        ("target_stage_leveltop", "output", "data"),
    ]
    bridge_params = {
        op.target: op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and (op.target.endswith("/sopto") or op.target.endswith("/popto"))
    }
    assert any(params["sop"].endswith("/out_sop") for params in bridge_params.values() if "sop" in params)
    assert any(params["pop"].endswith("/out_pop") for params in bridge_params.values() if "pop" in params)
    assert "atlas-synthesis:typed-bridge-graph-search:multi-hop" in plan.grounding_evidence
    assert (
        "atlas-synthesis:role-graph:source->bridge->process->output->bridge->process->output"
        in plan.grounding_evidence
    )
    assert "atlas-synthesis:bridge:SOP->POP:soptoPOP" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:POP->TOP:poptoTOP" in plan.grounding_evidence
    assert "atlas-synthesis:source-output-before-bridge:nullPOP" in plan.grounding_evidence
    assert (
        "operators:gridSOP,noiseSOP,nullSOP,soptoPOP,noisePOP,nullPOP,poptoTOP,levelTOP,nullTOP"
        in candidate.explanation
    )
    assert plan.patch_plan.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "soptoPOP",
        "noisePOP",
        "nullPOP",
        "poptoTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_prefers_direct_sop_render_preview_over_bridge_detour_when_both_are_grounded():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP surface source grid for sculpted height fields.",
            params=["rows", "cols"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Adds organic surface noise to SOP geometry.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP result for surface geometry.",
        ),
        "geometryCOMP": _operator_card(
            "geometryCOMP",
            "Geometry component that references a SOP output for TOP rendering.",
            params=["sop"],
        ),
        "cameraCOMP": _operator_card(
            "cameraCOMP",
            "Camera component for TOP render staging.",
        ),
        "lightCOMP": _operator_card(
            "lightCOMP",
            "Light component for readable surface shading.",
        ),
        "renderTOP": _operator_card(
            "renderTOP",
            "TOP image stage that references geometry, camera, and lights.",
            params=["geometry", "camera", "lights"],
        ),
        "soptoPOP": _operator_card(
            "soptoPOP",
            "SOP to POP bridge converts stable SOP geometry into a point field.",
            params=["sop"],
        ),
        "noisePOP": _operator_card(
            "noisePOP",
            "Adds point displacement to converted POP fields.",
            params=["amplitude"],
        ),
        "nullPOP": _operator_card(
            "nullPOP",
            "Stable POP output before TOP preview.",
        ),
        "poptoTOP": _operator_card(
            "poptoTOP",
            "POP to TOP bridge previews stable POP point fields as texture pixels.",
            params=["pop"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Texture shaping stage for geometry preview pixels.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable image result for final delivery.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "POP": ["soptoPOP", "noisePOP", "nullPOP"],
                    "TOP": ["renderTOP", "poptoTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "surface noise becomes final image output with a rendered SOP preview "
            "while transform layout cards are also available"
        ),
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    selected = plan.candidate_graphs[0]
    assert selected.pattern_ids == ["atlas:synthesized:sop_render_preview_top_card_chain"]
    assert selected.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    ]
    assert (
        "atlas-synthesis:topology-selected:1:atlas:synthesized:sop_render_preview_top_card_chain"
        in selected.grounding_evidence
    )
    assert "atlas-synthesis:topology-role-family:1:source:SOP:2" in selected.grounding_evidence
    assert "atlas-synthesis:topology-role-family:1:preview:TOP:2" in selected.grounding_evidence
    assert any(
        marker.startswith("atlas-synthesis:topology-role-relevance:1:")
        and "source:2" in marker
        and "preview:2" in marker
        for marker in selected.grounding_evidence
    )
    assert "topology_rank:1" in selected.explanation
    assert "topology_role_relevance:source=2" in selected.explanation
    assert any(
        candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_sop_to_pop_to_top_card_chain"]
        for candidate in plan.candidate_graphs[1:]
    )
    assert not any(
        "soptoPOP" in candidate.required_ops
        and "atlas:synthesized:typed_role_graph_pop_preview_top_card_chain" in candidate.pattern_ids
        for candidate in plan.candidate_graphs
    )
    assert not any(
        "poptoTOP" in candidate.required_ops
        and "atlas:synthesized:chop_controlled_top_card_chain" in candidate.pattern_ids
        for candidate in plan.candidate_graphs
    )


@pytest.mark.asyncio
async def test_open_prompt_sop_role_graph_search_uses_intent_relevant_process_stage():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP surface source grid for sculpted height fields.",
            params=["rows", "cols"],
        ),
        "transformSOP": _operator_card(
            "transformSOP",
            "Transform SOP repositions geometry for render preview layout and camera framing.",
            params=["tx", "ty", "tz"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Noise SOP adds organic surface noise shaping displacement before rendering.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP result for surface geometry.",
        ),
        "geometryCOMP": _operator_card(
            "geometryCOMP",
            "Geometry component that references a SOP output for TOP rendering.",
            params=["sop"],
        ),
        "cameraCOMP": _operator_card(
            "cameraCOMP",
            "Camera component for TOP render staging.",
        ),
        "lightCOMP": _operator_card(
            "lightCOMP",
            "Light component for readable surface shading.",
        ),
        "renderTOP": _operator_card(
            "renderTOP",
            "TOP image stage that references geometry, camera, and lights.",
            params=["geometry", "camera", "lights"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable image result for final delivery.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "transformSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "TOP": ["renderTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "surface noise becomes final image output with a rendered SOP preview "
            "while transform layout cards are also available"
        ),
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    selected = plan.candidate_graphs[0]
    assert selected.pattern_ids == ["atlas:synthesized:sop_render_preview_top_card_chain"]
    assert selected.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    ]
    assert "transformSOP" not in selected.required_ops
    assert "atlas-synthesis:role-graph-search:SOP:source->process->output" in selected.grounding_evidence
    assert "atlas-synthesis:role-graph-selected:SOP:1:gridSOP>noiseSOP>nullSOP" in selected.grounding_evidence
    assert any(
        marker.startswith("atlas-synthesis:role-graph-candidate:SOP:")
        and ":alternative:" in marker
        and "transformSOP" in marker
        for marker in selected.grounding_evidence
    )
    assert "atlas-synthesis:role-node:SOP:process:noiseSOP" in selected.grounding_evidence
    assert "source_role_search:source->process->output" in selected.explanation


def test_chop_export_sop_target_ranking_prefers_displacement_amp_over_layout_transform():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP terrain surface source grid.",
            params=["rows", "cols"],
        ),
        "transformSOP": _operator_card(
            "transformSOP",
            "Transform SOP handles layout positioning and camera framing.",
            params=["ty"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Noise SOP provides terrain displacement with an amplitude parameter.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP output for rendered terrain.",
        ),
    }

    selected = atlas_drafter._sop_export_control_target(
        ["gridSOP", "transformSOP", "noiseSOP", "nullSOP"],
        {
            "gridSOP": "source",
            "transformSOP": "process",
            "noiseSOP": "process",
            "nullSOP": "output",
        },
        cards,
        intent="LFO export binding drives terrain displacement and layout before TOP render",
    )

    assert selected is not None
    assert (selected.op_type, selected.param_name) == ("noiseSOP", "amp")

    evidence = atlas_drafter._sop_export_control_target_evidence(
        ["gridSOP", "transformSOP", "noiseSOP", "nullSOP"],
        {
            "gridSOP": "source",
            "transformSOP": "process",
            "noiseSOP": "process",
            "nullSOP": "output",
        },
        cards,
        selected,
        intent="LFO export binding drives terrain displacement and layout before TOP render",
    )

    assert "atlas-synthesis:sop-control-target-selected:noiseSOP.amp" in evidence
    assert "atlas-synthesis:sop-control-target-candidate-count:2" in evidence
    assert any(
        marker.startswith("atlas-synthesis:sop-control-target-candidate:2:alternative:transformSOP.ty")
        for marker in evidence
    )


@pytest.mark.asyncio
async def test_open_prompt_typed_graph_search_prefers_requested_single_bridge_target():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP mesh source grid for geometry sampling.",
            params=["rows", "cols"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Displaces SOP surface before conversion.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP output for downstream bridge references.",
        ),
        "soptoCHOP": _operator_card(
            "soptoCHOP",
            "SOP to CHOP bridge samples stable SOP geometry into control channels.",
            params=["sop"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for sampled geometry control channels.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for sampled geometry control channels.",
        ),
        "soptoPOP": _operator_card(
            "soptoPOP",
            "SOP to POP bridge converts stable SOP geometry into a point field.",
            params=["sop"],
        ),
        "noisePOP": _operator_card(
            "noisePOP",
            "Adds point displacement to converted POP fields.",
            params=["amplitude"],
        ),
        "nullPOP": _operator_card(
            "nullPOP",
            "Stable POP output before TOP preview.",
        ),
        "poptoTOP": _operator_card(
            "poptoTOP",
            "POP to TOP bridge previews stable POP point fields as texture pixels.",
            params=["pop"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Texture shaping stage for geometry preview pixels.",
            params=["brightness", "opacity"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for geometry preview texture.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "CHOP": ["soptoCHOP", "mathCHOP", "nullCHOP"],
                    "POP": ["soptoPOP", "noisePOP", "nullPOP"],
                    "TOP": ["poptoTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="SOP mesh surface becomes sampled control channels with stable CHOP output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_sop_to_chop_card_chain"]
    assert candidate.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "soptoCHOP",
        "mathCHOP",
        "nullCHOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"SOP", "CHOP"}
    assert "atlas-synthesis:typed-bridge-graph-search" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:SOP->CHOP:soptoCHOP" in plan.grounding_evidence
    assert "atlas-synthesis:bridge:SOP->POP:soptoPOP" not in plan.grounding_evidence
    assert "operators:gridSOP,noiseSOP,nullSOP,soptoCHOP,mathCHOP,nullCHOP" in candidate.explanation
    bridge_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/sopto")
    ]
    assert bridge_params
    assert bridge_params[0].args["params"]["sop"].endswith("/out_sop")
    assert plan.patch_plan.validation_plan.capture_frames == []


@pytest.mark.asyncio
async def test_open_prompt_typed_graph_search_uses_source_family_relevance_over_bridge_priority():
    cards = {
        "tableDAT": _operator_card(
            "tableDAT",
            "DAT table source with distracting SOP mesh surface sampled control wording.",
            params=["rows", "cols"],
        ),
        "selectDAT": _operator_card(
            "selectDAT",
            "DAT processing stage that claims sampled control channels for surface values.",
            params=["rowselect", "colselect"],
        ),
        "dattoCHOP": _operator_card(
            "dattoCHOP",
            "DAT to CHOP bridge converts table rows into control channels.",
            params=["dat"],
        ),
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP mesh source grid for geometry sampling.",
            params=["rows", "cols"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Displaces SOP mesh surface before channel conversion.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP output for downstream bridge references.",
        ),
        "soptoCHOP": _operator_card(
            "soptoCHOP",
            "SOP to CHOP bridge samples stable SOP geometry into control channels.",
            params=["sop"],
        ),
        "mathCHOP": _operator_card(
            "mathCHOP",
            "Range shaping stage for sampled geometry control channels.",
            params=["range1", "range2"],
        ),
        "nullCHOP": _operator_card(
            "nullCHOP",
            "Stable CHOP output for sampled geometry control channels.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["tableDAT", "selectDAT"],
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "CHOP": ["dattoCHOP", "soptoCHOP", "mathCHOP", "nullCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="SOP mesh surface becomes sampled control channels with stable CHOP output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_sop_to_chop_card_chain"]
    assert candidate.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "soptoCHOP",
        "mathCHOP",
        "nullCHOP",
    ]
    assert "atlas-synthesis:typed-bridge-selected:sop_to_chop:soptoCHOP" in plan.grounding_evidence
    assert "atlas-synthesis:typed-bridge-source-relevance:SOP:3" in plan.grounding_evidence
    assert "atlas-synthesis:typed-bridge-target-relevance:CHOP:8" in plan.grounding_evidence
    assert any(
        marker.startswith("atlas-synthesis:typed-bridge-candidate:") and "dat_to_chop:dattoCHOP" in marker
        for marker in plan.grounding_evidence
    )
    assert "source_relevance:SOP:3" in candidate.explanation
    assert "target_relevance:CHOP:8" in candidate.explanation
    assert "operators:gridSOP,noiseSOP,nullSOP,soptoCHOP,mathCHOP,nullCHOP" in candidate.explanation


@pytest.mark.asyncio
async def test_open_prompt_synthesizes_pop_preview_topology():
    cards = {
        "circlePOP": _operator_card(
            "circlePOP",
            "Point field POP source for circular particle layouts.",
            params=["count", "radius"],
        ),
        "noisePOP": _operator_card(
            "noisePOP",
            "Adds noise motion and organic displacement to POP point fields.",
            params=["amplitude"],
        ),
        "nullPOP": _operator_card(
            "nullPOP",
            "Stable POP output for a point field geometry stream.",
        ),
        "rendersimpleTOP": _operator_card(
            "rendersimpleTOP",
            "Simple TOP preview render stage for POP point field output.",
            params=["camera", "geometry"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for inspected point field preview.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "noisePOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="point field preview as a simple TOP output with noise motion",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:pop_preview_top_card_chain"]
    assert candidate.required_ops == ["circlePOP", "noisePOP", "nullPOP", "rendersimpleTOP", "nullTOP"]
    assert {concept.domain for concept in candidate.concepts} == {"POP", "TOP"}
    assert any(
        edge.kind == "reference"
        and edge.source == "source_stage_nullpop"
        and edge.target == "preview_stage_rendersimpletop"
        for edge in candidate.edges
    )
    assert "atlas-synthesis:multi-domain:pop-to-top-preview" in plan.grounding_evidence
    assert "atlas-synthesis:source:circlePOP" in plan.grounding_evidence
    assert "atlas-synthesis:process:noisePOP" in plan.grounding_evidence
    assert "atlas-synthesis:output:nullPOP" in plan.grounding_evidence
    preview_params = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target.endswith("/rendersimple")
    ]
    assert preview_params
    assert preview_params[0].args["params"]["pop"].endswith("/out_pop")
    connections = [op for op in plan.patch_plan.operations if op.kind == "connect"]
    assert all(
        not (op.args["from"].endswith("/nullpop") and op.args["to"].endswith("/rendersimple"))
        for op in connections
    )
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_uses_typed_source_preview_graph_without_preview_route_terms():
    cards = {
        "circlePOP": _operator_card(
            "circlePOP",
            "Point field POP source for circular particle layouts.",
            params=["count", "radius"],
        ),
        "noisePOP": _operator_card(
            "noisePOP",
            "Adds organic displacement to POP point fields.",
            params=["amplitude"],
        ),
        "nullPOP": _operator_card(
            "nullPOP",
            "Stable POP result for point field geometry.",
        ),
        "rendersimpleTOP": _operator_card(
            "rendersimpleTOP",
            "Official TOP image stage for POP point field output.",
            params=["pop", "normalizegeo"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable image result for final delivery.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "noisePOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="point field noise becomes final image output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_role_graph_pop_preview_top_card_chain"]
    assert candidate.required_ops == ["circlePOP", "noisePOP", "nullPOP", "rendersimpleTOP", "nullTOP"]
    assert {concept.domain for concept in candidate.concepts} == {"POP", "TOP"}
    assert any(
        edge.kind == "reference"
        and edge.source == "source_stage_nullpop"
        and edge.target == "preview_stage_rendersimpletop"
        for edge in candidate.edges
    )
    assert "atlas-synthesis:typed-role-graph" in plan.grounding_evidence
    assert "atlas-synthesis:role-graph:source->preview->output" in plan.grounding_evidence
    assert "atlas-synthesis:family:pop+top" in plan.grounding_evidence
    assert "atlas_synthesis:typed_role_graph" in candidate.explanation
    preview_params = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target.endswith("/rendersimple")
    ]
    assert preview_params
    assert preview_params[0].args["params"]["pop"].endswith("/out_pop")


@pytest.mark.asyncio
async def test_open_prompt_synthesizes_sop_render_preview_topology():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "Geometry source grid surface for terrain preview.",
            params=["rows", "cols"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Displaces SOP geometry with organic surface noise.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP output for rendered geometry preview.",
        ),
        "geometryCOMP": _operator_card(
            "geometryCOMP",
            "Geometry component that references a SOP output for rendering.",
            params=["sop"],
        ),
        "cameraCOMP": _operator_card(
            "cameraCOMP",
            "Camera component for TOP render previews.",
        ),
        "lightCOMP": _operator_card(
            "lightCOMP",
            "Light component for simple geometry render previews.",
        ),
        "renderTOP": _operator_card(
            "renderTOP",
            "TOP render stage that references geometry, camera, and lights.",
            params=["geometry", "camera", "lights"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable TOP output for inspected geometry render preview.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "TOP": ["renderTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="SOP surface preview as a TOP output with noise shaping",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:sop_render_preview_top_card_chain"]
    assert candidate.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"SOP", "COMP", "TOP"}
    assert any(
        edge.kind == "reference"
        and edge.source == "source_stage_nullsop"
        and edge.target == "preview_geometry"
        for edge in candidate.edges
    )
    assert "atlas-synthesis:multi-domain:sop-to-render-top-preview" in plan.grounding_evidence
    geo_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/geometry")
    ]
    assert geo_params
    assert geo_params[0].args["params"]["sop"].endswith("/out_sop")
    render_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/render")
    ]
    assert render_params
    assert render_params[0].args["params"] == {
        "geometry": "/project1/geometry",
        "camera": "/project1/camera",
        "lights": "/project1/light",
    }
    connections = [op for op in plan.patch_plan.operations if op.kind == "connect"]
    assert all(
        not (op.args["from"].endswith("/outsop") and op.args["to"].endswith("/render")) for op in connections
    )
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]


@pytest.mark.asyncio
async def test_open_prompt_uses_typed_sop_to_top_graph_without_preview_route_terms():
    cards = {
        "gridSOP": _operator_card(
            "gridSOP",
            "SOP surface source grid for sculpted height fields.",
            params=["rows", "cols"],
        ),
        "noiseSOP": _operator_card(
            "noiseSOP",
            "Adds organic surface noise to SOP geometry.",
            params=["amp"],
        ),
        "nullSOP": _operator_card(
            "nullSOP",
            "Stable SOP result for surface geometry.",
        ),
        "geometryCOMP": _operator_card(
            "geometryCOMP",
            "Geometry component that references a SOP output for TOP rendering.",
            params=["sop"],
        ),
        "cameraCOMP": _operator_card(
            "cameraCOMP",
            "Camera component for TOP render staging.",
        ),
        "lightCOMP": _operator_card(
            "lightCOMP",
            "Light component for readable surface shading.",
        ),
        "renderTOP": _operator_card(
            "renderTOP",
            "TOP image stage that references geometry, camera, and lights.",
            params=["geometry", "camera", "lights"],
        ),
        "nullTOP": _operator_card(
            "nullTOP",
            "Stable image result for final delivery.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "TOP": ["renderTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="surface noise becomes final image output",
        target_root="/project1",
        card_index=index,
    )

    assert plan.blocked_questions == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_role_graph_sop_render_preview_top_card_chain"]
    assert candidate.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    ]
    assert {concept.domain for concept in candidate.concepts} == {"SOP", "COMP", "TOP"}
    assert any(
        edge.kind == "reference"
        and edge.source == "source_stage_nullsop"
        and edge.target == "preview_geometry"
        for edge in candidate.edges
    )
    assert "atlas-synthesis:typed-role-graph" in plan.grounding_evidence
    assert "atlas-synthesis:role-graph:source->preview->output" in plan.grounding_evidence
    assert "atlas-synthesis:family:sop+comp+top" in plan.grounding_evidence
    assert "atlas_synthesis:typed_role_graph" in candidate.explanation
    geo_params = [
        op for op in plan.patch_plan.operations if op.kind == "set_params" and op.target.endswith("/geometry")
    ]
    assert geo_params
    assert geo_params[0].args["params"]["sop"].endswith("/out_sop")


@pytest.mark.asyncio
async def test_open_prompt_still_blocks_when_atlas_cannot_route_the_concept():
    cards = {
        "noiseTOP": _operator_card(
            "noiseTOP",
            "Procedural texture source for unrelated generative material tests.",
        ),
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": ["noiseTOP"]}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="ceremonial clock sculpture with memory ribbons and quiet stage cues",
        target_root="/project1",
        card_index=index,
    )

    assert plan.concept_graph.profile == "generic"
    assert plan.blocked_questions
    assert plan.patch_plan.operations == []
    assert "unsupported_open_prompt:atlas_grounded_planner_required" in plan.missing_facts
    assert "atlas_draft:no_operator_intent_route" in plan.missing_facts
    assert "planner:open_prompt_atlas_grounded" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_compiler_plan_carries_corpus_evidence_for_selected_candidate_ops():
    operators = {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "noiseTOP",
        "feedbackTOP",
        "levelTOP",
        "compositeTOP",
        "nullTOP",
        "baseCOMP",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "textDAT",
        "annotateCOMP",
        "infoCHOP",
        "errorDAT",
    }
    cards = {
        op_type: _operator_card(op_type, f"{op_type} official audio feedback control docs")
        for op_type in operators
    }
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiofileinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=SearchableCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "concept_compiled"
    assert "corpus:exact:feedbackTOP" in plan.grounding_evidence
    assert "corpus:exact:audiofileinCHOP" in plan.grounding_evidence
    assert any(record.op_type == "panelCHOP" for record in plan.corpus_evidence)
