from __future__ import annotations

from td_mcp.brain.operator_intents import select_operator_intent_route
from td_mcp.models.brain import CorpusEvidenceRecord


def _record(op_type: str, summary: str, *, score: float = 0.92) -> CorpusEvidenceRecord:
    family = next(
        (
            suffix
            for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP")
            if op_type.endswith(suffix)
        ),
        None,
    )
    return CorpusEvidenceRecord(
        evidence_id=f"corpus:search:{op_type}",
        source="docs_search",
        op_type=op_type,
        family=family,
        display_name=op_type,
        docs_url=f"https://docs.derivative.ca/{op_type}",
        summary=summary,
        key_params=[],
        key_concepts=[],
        matched_terms=summary.lower().split()[:6],
        query=summary,
        score=score,
    )


def test_operator_intent_routes_cover_corpus_grounded_ndi_video_post_fx():
    route = select_operator_intent_route(
        "network video input with soft post effects and stable output",
        [
            _record("ndiinTOP", "network video input source over NDI"),
            _record("levelTOP", "post effect color correction for video"),
            _record("nullTOP", "stable TOP output"),
        ],
    )

    assert route is not None
    assert route.route_id == "network_video_post_fx"
    assert route.operator_chain == ("ndiinTOP", "levelTOP", "nullTOP")
    assert "device-source-required" in route.risk_flags


def test_operator_intent_routes_cover_corpus_grounded_table_switcher():
    route = select_operator_intent_route(
        "table driven cue switcher for scenes and looks",
        [
            _record("tableDAT", "table of cue rows and scene data"),
            _record("selectDAT", "select cue row from table data"),
            _record("switchTOP", "switch visual inputs by index"),
            _record("nullTOP", "stable TOP output"),
        ],
    )

    assert route is not None
    assert route.route_id == "table_driven_top_switch"
    assert route.operator_chain == ("tableDAT", "selectDAT", "switchTOP", "nullTOP")


def test_operator_intent_routes_cover_corpus_grounded_udp_dat_ingest():
    route = select_operator_intent_route(
        "listen for udp packets and expose a stable table output",
        [
            _record("udpinDAT", "UDP network packet ingest source that appends messages to a DAT table"),
            _record("nullDAT", "stable DAT table output for downstream references"),
        ],
    )

    assert route is not None
    assert route.route_id == "udp_dat_table_ingest"
    assert route.operator_chain == ("udpinDAT", "nullDAT")
    assert "device-source-required" in route.risk_flags


def test_operator_intent_routes_cover_corpus_grounded_protocol_dat_ingests():
    cases = [
        (
            "read serial sensor messages into a stable dat table output",
            "serial_dat_table_ingest",
            ("serialDAT", "nullDAT"),
            [
                _record("serialDAT", "Serial device message ingest source that appends sensor rows to DAT"),
                _record("nullDAT", "stable DAT table output for downstream references"),
            ],
        ),
        (
            "listen for osc control messages and expose a stable dat table output",
            "osc_dat_table_ingest",
            ("oscinDAT", "nullDAT"),
            [
                _record("oscinDAT", "OSC message ingest source that appends address rows to DAT"),
                _record("nullDAT", "stable DAT table output for downstream references"),
            ],
        ),
        (
            "connect to websocket messages and expose a stable dat output",
            "websocket_dat_table_ingest",
            ("websocketDAT", "nullDAT"),
            [
                _record("websocketDAT", "WebSocket endpoint message source that appends messages to DAT"),
                _record("nullDAT", "stable DAT output for downstream references"),
            ],
        ),
        (
            "fetch an http api response into a stable dat output",
            "web_client_dat_request_output",
            ("webclientDAT", "nullDAT"),
            [
                _record(
                    "webclientDAT", "Web Client DAT sends HTTP requests and outputs API responses to a DAT"
                ),
                _record("nullDAT", "stable DAT output for downstream references"),
            ],
        ),
        (
            "host an http server endpoint with callback dat and stable output while Web Client DAT docs are present",
            "web_server_dat_endpoint",
            ("webserverDAT", "nullDAT"),
            [
                _record("webclientDAT", "HTTP request client distractor for fetching API responses"),
                _record("webserverDAT", "Web Server DAT hosts HTTP and WebSocket endpoints with callbacks"),
                _record("nullDAT", "stable DAT output for downstream references"),
            ],
        ),
        (
            "subscribe to mqtt topic messages and expose a stable dat table output",
            "mqtt_dat_table_ingest",
            ("mqttclientDAT", "nullDAT"),
            [
                _record("mqttclientDAT", "MQTT broker topic message source that appends payloads to DAT"),
                _record("nullDAT", "stable DAT table output for downstream references"),
            ],
        ),
    ]

    for intent, route_id, operator_chain, records in cases:
        route = select_operator_intent_route(intent, records)

        assert route is not None
        assert route.route_id == route_id
        assert route.operator_chain == operator_chain
        assert "device-source-required" in route.risk_flags


def test_operator_intent_routes_prefer_mqtt_primary_intent_over_websocket_distractor():
    route = select_operator_intent_route(
        "subscribe to MQTT topic payload messages and expose a stable DAT table output while WebSocket DAT docs are present",
        [
            _record(
                "websocketDAT", "WebSocket endpoint message source distractor that appends messages to DAT"
            ),
            _record("mqttclientDAT", "MQTT broker topic message source that appends payloads to DAT"),
            _record("nullDAT", "stable DAT table output for downstream references"),
        ],
    )

    assert route is not None
    assert route.route_id == "mqtt_dat_table_ingest"
    assert route.operator_chain == ("mqttclientDAT", "nullDAT")


def test_operator_intent_routes_cover_chop_controlled_texture():
    route = select_operator_intent_route(
        "oscillator controlled brightness wash over procedural texture",
        [
            _record("lfoCHOP", "oscillator modulation source for control signals"),
            _record("mathCHOP", "scale CHOP channels for brightness control"),
            _record("nullCHOP", "stable CHOP output"),
            _record("noiseTOP", "procedural texture source"),
            _record("levelTOP", "brightness level adjustment"),
            _record("nullTOP", "stable TOP output"),
        ],
    )

    assert route is not None
    assert route.route_id == "chop_controlled_texture"
    assert route.operator_chain == ("lfoCHOP", "mathCHOP", "nullCHOP", "noiseTOP", "levelTOP", "nullTOP")


def test_operator_intent_routes_cover_corpus_grounded_midi_control_bridge():
    route = select_operator_intent_route(
        "MIDI CC performance controller should become a normalized CHOP output",
        [
            _record("waveCHOP", "generic oscillator source distractor for control signals"),
            _record("noiseCHOP", "random modulation source distractor for control signals"),
            _record("midiinCHOP", "MIDI In CHOP receives MIDI controller note and CC channels"),
            _record("mathCHOP", "normalize and scale incoming MIDI control channels"),
            _record("nullCHOP", "stable CHOP output for downstream references"),
        ],
    )

    assert route is not None
    assert route.route_id == "midi_chop_control_bridge"
    assert route.operator_chain == ("midiinCHOP", "mathCHOP", "nullCHOP")
    assert "device-source-required" in route.risk_flags


def test_operator_intent_routes_cover_pop_preview_texture():
    route = select_operator_intent_route(
        "point field preview as a simple TOP output with noise motion",
        [
            _record("circlePOP", "point field POP source"),
            _record("noisePOP", "noise motion for POP points"),
            _record("nullPOP", "stable POP output"),
            _record("rendersimpleTOP", "simple TOP preview render"),
            _record("nullTOP", "stable TOP output"),
        ],
    )

    assert route is not None
    assert route.route_id == "pop_preview_top_output"
    assert route.operator_chain == ("circlePOP", "noisePOP", "nullPOP", "rendersimpleTOP", "nullTOP")


def test_operator_intent_routes_cover_sop_render_preview_texture():
    route = select_operator_intent_route(
        "terrain geometry surface preview rendered as a TOP output",
        [
            _record("gridSOP", "geometry source grid terrain surface"),
            _record("noiseSOP", "noise displacement SOP geometry process"),
            _record("nullSOP", "stable SOP output"),
            _record("geometryCOMP", "geometry component references SOP output"),
            _record("cameraCOMP", "camera component for render preview"),
            _record("lightCOMP", "light component for render preview"),
            _record("renderTOP", "render TOP output stage"),
            _record("nullTOP", "stable TOP output"),
        ],
    )

    assert route is not None
    assert route.route_id == "sop_render_preview_top_output"
    assert route.operator_chain == (
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    )


def test_operator_intent_routes_cover_chop_controlled_sop_render_preview():
    route = select_operator_intent_route(
        "lfo export binding drives terrain sop displacement into a rendered top preview",
        [
            _record("lfoCHOP", "oscillator modulation source for control signals"),
            _record("mathCHOP", "scale CHOP channels for terrain displacement control"),
            _record("gridSOP", "geometry source grid terrain surface"),
            _record("noiseSOP", "noise displacement SOP geometry process"),
            _record("nullSOP", "stable SOP output"),
            _record("geometryCOMP", "geometry component references SOP output"),
            _record("renderTOP", "render TOP output stage"),
            _record("nullTOP", "stable TOP output"),
        ],
    )

    assert route is not None
    assert route.route_id == "chop_controlled_sop_render_preview"
    assert route.operator_chain == (
        "lfoCHOP",
        "mathCHOP",
        "nullCHOP",
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    )
    assert "atlas-chop-export-binding" in route.risk_flags
