"""Small deterministic intent library for atlas-grounded open prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from td_mcp.models.brain import CorpusEvidenceRecord


@dataclass(frozen=True)
class OperatorIntentRoute:
    """A tiny concept-to-operator-family route before concrete graph drafting."""

    route_id: str
    label: str
    terms: tuple[str, ...]
    operator_chain: tuple[str, ...]
    validation_needs: tuple[str, ...] = ("output_node_present",)
    risk_flags: tuple[str, ...] = ("atlas-drafted-open-prompt",)
    description: str = ""
    score: float = field(default=0.0, compare=False)


OPERATOR_INTENT_ROUTES: tuple[OperatorIntentRoute, ...] = (
    OperatorIntentRoute(
        route_id="volumetric_light_texture",
        label="Volumetric light texture chain",
        terms=("volumetric", "organic", "light", "field", "fluid", "caustic", "cloud", "nebula"),
        operator_chain=("noiseTOP", "levelTOP", "nullTOP"),
        validation_needs=("top_output_present", "cheap_visual_metrics"),
        description="Generate a procedural TOP texture, shape its levels, then expose a stable TOP output.",
    ),
    OperatorIntentRoute(
        route_id="depth_body_silhouette",
        label="Depth tracked body silhouette",
        terms=("depth", "body", "silhouette", "skeletal", "skeleton", "person", "tracked", "sensor"),
        operator_chain=("kinectazureTOP", "nullTOP"),
        validation_needs=("top_output_present", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description="Use a depth-camera TOP source and immediately stabilize its image stream for inspection.",
    ),
    OperatorIntentRoute(
        route_id="kinetic_typography_mapping",
        label="Kinetic typography projection texture",
        terms=("kinetic", "typography", "type", "text", "projection", "mapping", "layered", "fields"),
        operator_chain=("textTOP", "transformTOP", "nullTOP"),
        validation_needs=("top_output_present", "cheap_visual_metrics"),
        description="Create a text texture, transform it for motion/projection placement, and expose a stable TOP.",
    ),
    OperatorIntentRoute(
        route_id="procedural_texture_motion",
        label="Procedural texture motion chain",
        terms=("procedural", "generative", "texture", "motion", "animated", "abstract", "visual"),
        operator_chain=("noiseTOP", "transformTOP", "levelTOP", "nullTOP"),
        validation_needs=("top_output_present", "cheap_visual_metrics"),
        description="Use procedural noise, image transforms, level shaping, and a stable TOP output.",
    ),
    OperatorIntentRoute(
        route_id="chop_controlled_texture",
        label="CHOP-controlled procedural TOP texture",
        terms=(
            "oscillator",
            "lfo",
            "modulation",
            "modulate",
            "control",
            "controlled",
            "brightness",
            "procedural",
            "texture",
        ),
        operator_chain=("lfoCHOP", "mathCHOP", "nullCHOP", "noiseTOP", "levelTOP", "nullTOP"),
        validation_needs=("control_output", "top_output_present", "cheap_visual_metrics"),
        description=("Use an official CHOP modulation branch to control a procedural TOP texture branch."),
    ),
    OperatorIntentRoute(
        route_id="midi_chop_control_bridge",
        label="MIDI control CHOP bridge",
        terms=(
            "midi",
            "cc",
            "controller",
            "control",
            "performance",
            "knob",
            "fader",
            "note",
            "channel",
            "normalized",
            "chop",
            "output",
            "bridge",
        ),
        operator_chain=("midiinCHOP", "mathCHOP", "nullCHOP"),
        validation_needs=("control_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official MIDI In CHOP, normalize the resulting channels with Math CHOP, "
            "and expose a stable CHOP output."
        ),
    ),
    OperatorIntentRoute(
        route_id="pop_preview_top_output",
        label="POP point-field preview TOP output",
        terms=("point", "field", "pop", "particle", "preview", "render", "simple", "top", "output", "noise"),
        operator_chain=("circlePOP", "noisePOP", "nullPOP", "rendersimpleTOP", "nullTOP"),
        validation_needs=("pop_output_attached", "finite_pop_bounds", "top_output_present"),
        description="Build a POP point-field branch and preview it through an official simple TOP renderer.",
    ),
    OperatorIntentRoute(
        route_id="sop_render_preview_top_output",
        label="SOP geometry render preview TOP output",
        terms=(
            "terrain",
            "geometry",
            "surface",
            "sop",
            "preview",
            "render",
            "rendered",
            "top",
            "output",
            "noise",
            "displacement",
        ),
        operator_chain=(
            "gridSOP",
            "noiseSOP",
            "nullSOP",
            "geometryCOMP",
            "cameraCOMP",
            "lightCOMP",
            "renderTOP",
            "nullTOP",
        ),
        validation_needs=("geometry_output_present", "render_top_output", "top_output_present"),
        description=(
            "Build a SOP geometry branch, reference it from a Geometry COMP, and render it to a TOP output."
        ),
    ),
    OperatorIntentRoute(
        route_id="chop_controlled_sop_render_preview",
        label="CHOP-controlled SOP render preview TOP output",
        terms=(
            "lfo",
            "oscillator",
            "modulation",
            "control",
            "controlled",
            "drive",
            "driven",
            "export",
            "binding",
            "terrain",
            "surface",
            "sop",
            "mesh",
            "geometry",
            "displacement",
            "render",
            "preview",
            "top",
            "output",
        ),
        operator_chain=(
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
        ),
        validation_needs=(
            "control_output",
            "chop_export_method_readback",
            "geometry_output_present",
            "render_top_output",
            "top_output_present",
            "cheap_visual_metrics",
        ),
        risk_flags=(
            "atlas-drafted-open-prompt",
            "atlas-chop-export-binding",
            "export-flag-requires-review",
        ),
        description=(
            "Use an official CHOP control branch to export into a docs-grounded SOP "
            "surface parameter, then render the SOP branch to a stable TOP output."
        ),
    ),
    OperatorIntentRoute(
        route_id="network_video_post_fx",
        label="Network video post-FX texture chain",
        terms=("network", "video", "input", "ndi", "post", "effect", "fx", "stable", "output"),
        operator_chain=("ndiinTOP", "levelTOP", "nullTOP"),
        validation_needs=("top_output_present", "cheap_visual_metrics"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description="Use an official NDI TOP source, a simple color/level stage, and a stable TOP output.",
    ),
    OperatorIntentRoute(
        route_id="table_driven_top_switch",
        label="Table-driven TOP switch cue chain",
        terms=("table", "cue", "switcher", "switch", "selector", "scene", "look", "index", "visual"),
        operator_chain=("tableDAT", "selectDAT", "switchTOP", "nullTOP"),
        validation_needs=("render_switch_table_present", "top_output_present", "cheap_visual_metrics"),
        description=(
            "Use an official DAT cue table and selector to control a TOP switch with a stable TOP output."
        ),
    ),
    OperatorIntentRoute(
        route_id="udp_dat_table_ingest",
        label="UDP packet DAT ingest table",
        terms=(
            "udp",
            "packet",
            "packets",
            "network",
            "listen",
            "receive",
            "message",
            "messages",
            "dat",
            "table",
            "stable",
            "output",
        ),
        operator_chain=("udpinDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official UDP In DAT to receive packet messages and a Null DAT as a stable table output."
        ),
    ),
    OperatorIntentRoute(
        route_id="serial_dat_table_ingest",
        label="Serial device DAT ingest table",
        terms=(
            "serial",
            "rs232",
            "rs",
            "sensor",
            "device",
            "message",
            "messages",
            "read",
            "receive",
            "dat",
            "table",
            "stable",
            "output",
        ),
        operator_chain=("serialDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official Serial DAT to read device messages and a Null DAT as a stable table output."
        ),
    ),
    OperatorIntentRoute(
        route_id="osc_dat_table_ingest",
        label="OSC message DAT ingest table",
        terms=(
            "osc",
            "control",
            "address",
            "message",
            "messages",
            "listen",
            "receive",
            "dat",
            "table",
            "stable",
            "output",
        ),
        operator_chain=("oscinDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official OSC In DAT to receive OSC messages and a Null DAT as a stable table output."
        ),
    ),
    OperatorIntentRoute(
        route_id="websocket_dat_table_ingest",
        label="WebSocket message DAT ingest table",
        terms=(
            "websocket",
            "socket",
            "endpoint",
            "connect",
            "message",
            "messages",
            "receive",
            "dat",
            "table",
            "stable",
            "output",
        ),
        operator_chain=("websocketDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official WebSocket DAT to receive endpoint messages and a Null DAT as a stable output."
        ),
    ),
    OperatorIntentRoute(
        route_id="web_client_dat_request_output",
        label="Web Client HTTP request DAT output",
        terms=(
            "http",
            "https",
            "web",
            "api",
            "rest",
            "request",
            "fetch",
            "get",
            "post",
            "endpoint",
            "url",
            "response",
            "json",
            "dat",
            "table",
            "stable",
            "output",
        ),
        operator_chain=("webclientDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official Web Client DAT to issue HTTP requests and a Null DAT as a stable response output."
        ),
    ),
    OperatorIntentRoute(
        route_id="web_server_dat_endpoint",
        label="Web Server HTTP/WebSocket DAT endpoint",
        terms=(
            "server",
            "serve",
            "host",
            "hosting",
            "listener",
            "listen",
            "http",
            "https",
            "websocket",
            "endpoint",
            "request",
            "response",
            "callback",
            "callbacks",
            "dat",
            "stable",
            "output",
        ),
        operator_chain=("webserverDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official Web Server DAT to host HTTP/WebSocket callbacks and expose a stable DAT output."
        ),
    ),
    OperatorIntentRoute(
        route_id="mqtt_dat_table_ingest",
        label="MQTT client DAT ingest table",
        terms=(
            "mqtt",
            "broker",
            "topic",
            "subscribe",
            "payload",
            "message",
            "messages",
            "dat",
            "table",
            "stable",
            "output",
        ),
        operator_chain=("mqttclientDAT", "nullDAT"),
        validation_needs=("protocol_table_output", "output_node_present"),
        risk_flags=("atlas-drafted-open-prompt", "device-source-required"),
        description=(
            "Use the official MQTT Client DAT to subscribe to broker topics and expose a stable DAT output."
        ),
    ),
)


def select_operator_intent_route(
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> OperatorIntentRoute | None:
    """Return the best small operator route for an abstract prompt."""
    scored = [
        route.model_copy(update={"score": score})
        if hasattr(route, "model_copy")
        else _with_score(route, score)
        for route in OPERATOR_INTENT_ROUTES
        if (score := _route_score(route, intent=intent, corpus_evidence=corpus_evidence)) > 0.0
    ]
    if not scored:
        return None
    evidence_ops = {record.op_type for record in corpus_evidence if record.op_type}
    return max(
        scored,
        key=lambda route: (
            route.score,
            _route_primary_term_hits(route, intent),
            len({_operator_family(op_type) for op_type in route.operator_chain}),
            len(set(route.operator_chain).intersection(evidence_ops)),
            len(route.operator_chain),
        ),
    )


def _with_score(route: OperatorIntentRoute, score: float) -> OperatorIntentRoute:
    return OperatorIntentRoute(
        route_id=route.route_id,
        label=route.label,
        terms=route.terms,
        operator_chain=route.operator_chain,
        validation_needs=route.validation_needs,
        risk_flags=route.risk_flags,
        description=route.description,
        score=score,
    )


def _route_score(
    route: OperatorIntentRoute,
    *,
    intent: str,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> float:
    text = _route_match_text(intent)
    tokens = set(_tokens(text))
    if not _route_specific_requirements_met(route, text=text, corpus_evidence=corpus_evidence):
        return 0.0
    term_hits = sum(1 for term in route.terms if _term_matches(term, text, tokens))
    route_ops = set(route.operator_chain)
    evidence_ops = {record.op_type for record in corpus_evidence if record.op_type}
    operator_hits = len(route_ops.intersection(evidence_ops))
    source_operator_hits = len(
        {op_type for op_type in route.operator_chain if not _is_stable_output_op(op_type)}.intersection(
            evidence_ops
        )
    )
    evidence_term_hits = sum(
        1
        for record in corpus_evidence
        for term in route.terms
        if _term_matches(term, _record_text(record), set(_tokens(_record_text(record))))
    )
    if term_hits < 2 or operator_hits < 1 or source_operator_hits < 1:
        return 0.0
    raw = (term_hits * 0.11) + (operator_hits * 0.22) + min(0.2, evidence_term_hits * 0.025)
    return round(min(1.0, raw), 4)


def _route_match_text(intent: str) -> str:
    """Remove fixture-style distractor-card clauses before route scoring."""
    text = intent.lower()
    return re.sub(r"\bwhile\b[^.]*\bdocs?\b[^.]*\bpresent\b", " ", text)


def _route_primary_term_hits(route: OperatorIntentRoute, intent: str) -> int:
    text = _route_match_text(intent)
    tokens = set(_tokens(text))
    return sum(1 for term in route.terms if _term_matches(term, text, tokens))


def _route_specific_requirements_met(
    route: OperatorIntentRoute,
    *,
    text: str,
    corpus_evidence: list[CorpusEvidenceRecord],
) -> bool:
    if route.route_id == "web_client_dat_request_output":
        serverish = any(
            token in text
            for token in (
                "server",
                "serve",
                "host",
                "hosting",
                "listener",
                "listen",
                "listening",
                "callback",
                "callbacks",
            )
        )
        clientish = any(
            token in text for token in ("client", "fetch", "api", "rest", "get", "post", "url", "json")
        )
        if serverish and not clientish:
            return False
    if route.route_id == "web_server_dat_endpoint":
        return any(
            token in text
            for token in (
                "server",
                "serve",
                "host",
                "hosting",
                "listener",
                "listen",
                "listening",
                "websocket",
                "callback",
                "callbacks",
            )
        )
    if route.route_id != "chop_controlled_sop_render_preview":
        return True
    evidence_families = {
        str(record.family or _operator_family(str(record.op_type or ""))).upper()
        for record in corpus_evidence
        if record.op_type
    }
    control_hit = any(
        token in text
        for token in (
            "lfo",
            "oscillator",
            "modulation",
            "control",
            "controlled",
            "drive",
            "driven",
            "export",
            "binding",
            "reactive",
        )
    )
    sop_hit = any(
        token in text for token in ("sop", "terrain", "surface", "mesh", "geometry", "displacement")
    )
    return control_hit and sop_hit and {"CHOP", "SOP"}.issubset(evidence_families)


def _term_matches(term: str, text: str, tokens: set[str]) -> bool:
    term_text = term.lower()
    term_tokens = set(_tokens(term_text))
    return term_text in text or bool(term_tokens and term_tokens.issubset(tokens))


def _record_text(record: CorpusEvidenceRecord) -> str:
    return " ".join(
        [
            str(record.op_type or ""),
            record.display_name,
            record.summary,
            " ".join(record.key_concepts),
            " ".join(record.matched_terms),
        ]
    ).lower()


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]


def _operator_family(op_type: str) -> str:
    for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP"):
        if op_type.endswith(suffix):
            return suffix
    return ""


def _is_stable_output_op(op_type: str) -> bool:
    lowered = op_type.lower()
    return lowered.startswith("null") or lowered in {"outTOP".lower(), "outCHOP".lower(), "outDAT".lower()}
