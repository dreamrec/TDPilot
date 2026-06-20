"""Tests for seed corpus integrity — validates all JSON knowledge cards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CARDS_DIR = Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "knowledge" / "cards"

# Required fields per card_type
REQUIRED_FIELDS = {
    "operator": ["card_type", "op_type", "family", "summary"],
    "palette": ["card_type", "component_name", "summary"],
    "release": ["card_type", "build"],
    "snippet": ["card_type", "snippet_id", "family", "summary"],
    "article": ["card_type", "article_id", "title", "summary", "source_url"],
}


def _load_all_json(subdir: str) -> list[tuple[Path, dict]]:
    """Load all JSON files from a cards subdirectory."""
    directory = CARDS_DIR / subdir
    results = []
    for p in sorted(directory.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        results.append((p, data))
    return results


class TestAllJsonValid:
    """Every .json file in cards/ must parse without error."""

    @pytest.fixture(scope="class")
    def all_json_files(self) -> list[Path]:
        return list(CARDS_DIR.rglob("*.json"))

    def test_at_least_one_json(self, all_json_files: list[Path]) -> None:
        assert len(all_json_files) > 0, "No JSON files found in cards directory"

    def test_all_parse(self, all_json_files: list[Path]) -> None:
        for p in all_json_files:
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                pytest.fail(f"{p.name} is not valid JSON: {exc}")


class TestOperatorCards:
    """Operator cards must have required fields and meet minimums."""

    @pytest.fixture(scope="class")
    def operators(self) -> list[tuple[Path, dict]]:
        return _load_all_json("operators")

    def test_at_least_10_operator_cards(self, operators: list[tuple[Path, dict]]) -> None:
        assert len(operators) >= 10, f"Expected >=10 operator cards, found {len(operators)}"

    def test_required_fields(self, operators: list[tuple[Path, dict]]) -> None:
        for path, card in operators:
            for field in REQUIRED_FIELDS["operator"]:
                assert field in card, f"{path.name} missing required field '{field}'"

    def test_card_type_is_operator(self, operators: list[tuple[Path, dict]]) -> None:
        for path, card in operators:
            assert card["card_type"] == "operator", f"{path.name} card_type != 'operator'"

    def test_family_valid(self, operators: list[tuple[Path, dict]]) -> None:
        valid_families = {"TOP", "CHOP", "SOP", "COMP", "DAT", "MAT", "POP"}
        for path, card in operators:
            assert card["family"] in valid_families, f"{path.name} has invalid family '{card['family']}'"

    def test_panel_chop_card_covers_queue_overlapping_events(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["panelCHOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/Panel_CHOP"
        expected_params = {"component", "select", "rename", "queue", "queuesize"}
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"panelCHOP missing {sorted(expected_params - actual)}"
        assert {"Panel Values", "Panel Components", "PanelCOMP Class", "panel member"}.issubset(
            set(card["key_concepts"])
        )
        assert any(
            "wheel" in note and "key" in note and "instantaneous" in note for note in card["common_gotchas"]
        )
        assert any("last value" in note and "missed" in note for note in card["common_gotchas"])
        assert any("Queue Size" in note and "discarded" in note for note in card["common_gotchas"])

    def test_glsl_top_card_covers_compute_output_buffer_and_compile_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslTOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_TOP"
        expected_params = {
            "glslversion",
            "mode",
            "predat",
            "vertexdat",
            "pixeldat",
            "computedat",
            "compilebehavior",
            "errorbehavior",
            "dispatchsizex",
            "dispatchsizey",
            "dispatchsizez",
            "outputaccess",
            "type",
            "customdepth",
            "autodispatchsize",
            "clearoutputs",
            "inputmapping",
            "nval",
            "numcolorbufs",
            "ac0name",
            "const0name",
            "buffer0pop",
            "buffer0attrclass",
            "buffer0attr",
            "buffer0name",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslTOP missing {sorted(expected_params - actual)}"
        assert {
            "Compute Shader",
            "TDImageStoreOutput()",
            "TDImageLoadOutput()",
            "Read-Write output access",
            "# of Color Buffers",
            "Render Select TOP",
            "Atomic Counters",
            "Specialization Constants",
            "POP Buffers",
        }.issubset(set(card["key_concepts"]))
        assert any("Info DAT" in note and "compile errors" in note for note in card["common_gotchas"])
        assert any("Read-Write" in note and "previous frame" in note for note in card["common_gotchas"])
        assert any(
            "Auto Dispatch Size" in note and "one thread per pixel" in note for note in card["common_gotchas"]
        )
        assert any("Render Select TOP" in note and "color buffers" in note for note in card["common_gotchas"])

    def test_glsl_multi_top_card_covers_multi_input_compute_uniform_and_output_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslmultiTOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_Multi_TOP"
        expected_params = {
            "glslversion",
            "mode",
            "predat",
            "vertexdat",
            "pixeldat",
            "computedat",
            "loaduniformnames",
            "autodispatchsize",
            "dispatchsizex",
            "dispatchsizey",
            "dispatchsizez",
            "outputaccess",
            "type",
            "depth",
            "customdepth",
            "clearoutputs",
            "clearvaluer",
            "clearvalueg",
            "clearvalueb",
            "clearvaluea",
            "inputmapping",
            "nval",
            "inputextenduv",
            "inputextendw",
            "numcolorbufs",
            "vec0name",
            "vec0value",
            "array0name",
            "array0type",
            "array0chop",
            "array0arraytype",
            "matrix0name",
            "matrix0value",
            "ac0name",
            "ac0initvalue",
            "ac0singlevalue",
            "ac0chopvalue",
            "const0name",
            "const0value",
            "outputresolution",
            "resolutionw",
            "resolutionh",
            "resmenu",
            "resmult",
            "outputaspect",
            "aspect1",
            "aspect2",
            "armenu",
            "inputfiltertype",
            "fillmode",
            "filtertype",
            "npasses",
            "chanmask",
            "format",
            "parmcolorspace",
            "parmreferencewhite",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslmultiTOP missing {sorted(expected_params - actual)}"
        assert {
            "more than 3 inputs",
            "GLSL TOP parity",
            "multi input",
            "Compute Shader",
            "Auto Dispatch Size",
            "Dispatch Size",
            "Read-Write output access",
            "2D Texture Array",
            "3D Texture",
            "Input Mapping",
            "N inputs per Slice",
            "Input Extend Mode UV",
            "Input Extend Mode W",
            "# of Color Buffers",
            "Render Select TOP",
            "TD_NUM_2D_INPUTS",
            "sTD2DInputs[]",
            "nonuniformEXT()",
            "uTD2DInfos",
            "TDImageStoreOutput()",
            "sTDComputeOutputs[]",
            "Vector uniforms",
            "CHOP Uniform arrays",
            "Texture Buffer arrays",
            "Atomic Counters",
            "Specialization Constants",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any("more than 3 inputs" in note and "GLSL TOP" in note for note in card["common_gotchas"])
        assert any("nonuniformEXT" in note and "sampler" in note for note in card["common_gotchas"])
        assert any("Read-Write" in note and "previous" in note for note in card["common_gotchas"])
        assert any("N inputs per Slice" in note and "loops" in note for note in card["common_gotchas"])
        assert any("Render Select TOP" in note and "color buffers" in note for note in card["common_gotchas"])

    def test_glsl_comp_card_covers_panel_shader_layout_interaction_and_component_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslCOMP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_COMP"
        expected_params = {
            "vertexdat",
            "pixeldat",
            "sampler0name",
            "sampler0top",
            "sampler0extendu",
            "sampler0extendv",
            "sampler0extendw",
            "sampler0filter",
            "sampler0anisotropy",
            "vec0name",
            "vec0value",
            "const0name",
            "const0value",
            "x",
            "y",
            "w",
            "h",
            "fixedaspect",
            "aspect",
            "layer",
            "hmode",
            "leftanchor",
            "rightanchor",
            "vmode",
            "bottomanchor",
            "topanchor",
            "alignallow",
            "alignorder",
            "postoffsetx",
            "postoffsety",
            "sizefromwindow",
            "display",
            "enable",
            "helpdat",
            "cursor",
            "multitouch",
            "constraincursor",
            "clickthrough",
            "mousewheel",
            "mouserel",
            "resize",
            "reposition",
            "anchordrag",
            "scrolloverlay",
            "bgcolorr",
            "bgcolorg",
            "bgcolorb",
            "bgalpha",
            "top",
            "topfill",
            "topsmoothness",
            "composite",
            "opacity",
            "align",
            "spacing",
            "alignmax",
            "marginl",
            "marginr",
            "marginb",
            "margint",
            "justifymethod",
            "justifyh",
            "justifyv",
            "fit",
            "crop",
            "phscrollbar",
            "pvscrollbar",
            "scrollbarthickness",
            "drag",
            "dragscript",
            "drop",
            "dropscript",
            "dragdropcallbacks",
            "reinitextensions",
            "ext0object",
            "ext0name",
            "ext0promote",
            "parentshortcut",
            "opshortcut",
            "iop0shortcut",
            "iop0op",
            "nodeview",
            "opviewer",
            "enablecloning",
            "clone",
            "loadondemand",
            "externaltox",
            "reloadcustom",
            "reloadbuiltin",
            "relpath",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslCOMP missing {sorted(expected_params - actual)}"
        assert {
            "pixel accurate UI",
            "DPI scaling",
            "Panel variables",
            "Panel Component",
            "sampler dimensions",
            "Texture Sampling Parameters",
            "Vector uniforms",
            "Specialization Constants",
            "Layout Page",
            "Fixed Aspect",
            "Anchors",
            "Depth Layer",
            "Panel Page",
            "Display",
            "Enable",
            "Multi-Touch",
            "Click Through",
            "Look Page",
            "Background TOP",
            "Composite",
            "Opacity",
            "Children Page",
            "Crop",
            "Drag-and-Drop",
            "Extensions",
            "Parent Shortcut",
            "Global OP Shortcut",
            "Internal Operators",
            "Node Viewer",
            "clone",
            "external .tox",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any(
            "sampler" in note and "sampler2D" in note and "sampler3D" in note
            for note in card["common_gotchas"]
        )
        assert any("Display" in note and "opacity" in note for note in card["common_gotchas"])
        assert any("Enable" in note and "interaction" in note for note in card["common_gotchas"])
        assert any("Multi-Touch" in note and "Multi Touch In DAT" in note for note in card["common_gotchas"])
        assert any("anchors" in note and "normalized" in note for note in card["common_gotchas"])
        assert any(
            "external .tox" in note and "built-in parameters" in note for note in card["common_gotchas"]
        )

    def test_point_generator_pop_card_covers_shape_distribution_transform_and_attributes(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["pointgeneratorPOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/Point_Generator_POP"
        expected_params = {
            "shape",
            "createpointprim",
            "numpoints",
            "distribution",
            "random",
            "seed",
            "orient",
            "size",
            "sizex",
            "sizey",
            "sizez",
            "radius",
            "radiusx",
            "radiusy",
            "radiusz",
            "height",
            "pointa",
            "pointax",
            "pointay",
            "pointaz",
            "pointb",
            "pointbx",
            "pointby",
            "pointbz",
            "normal",
            "normaldirection",
            "dotangent",
            "xord",
            "rord",
            "t",
            "tx",
            "ty",
            "tz",
            "r",
            "rx",
            "ry",
            "rz",
            "s",
            "sx",
            "sy",
            "sz",
            "p",
            "px",
            "py",
            "pz",
            "bypass",
            "freeextragpumem",
            "delinputattrs",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), (
            f"pointgeneratorPOP missing {sorted(expected_params - actual)}"
        )
        assert {
            "Generator Operator",
            "mathematical shape",
            "Sphere",
            "Box",
            "Torus",
            "Tube",
            "Rectangle",
            "Circle",
            "Line",
            "point primitives",
            "surface distribution",
            "volume distribution",
            "closed shape",
            "patterned distribution",
            "random distribution",
            "orientation axis",
            "line segment",
            "Normal attribute",
            "N float3",
            "Tangent attribute",
            "T float4",
            "Transform Page",
            "Transform Order",
            "Rotate Order",
            "Pivot",
            "Delete Input Attributes",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any("closed" in note and "holes" in note for note in card["common_gotchas"])
        assert any(
            "uniform per unit surface area" in note and "triangles" in note for note in card["common_gotchas"]
        )
        assert any("Random" in note and "patterned" in note for note in card["common_gotchas"])
        assert any(
            "Line" in note and "Point A" in note and "Point B" in note for note in card["common_gotchas"]
        )
        assert any("N" in note and "T" in note and "attribute" in note for note in card["common_gotchas"])

    def test_trace_pop_card_covers_top_threshold_line_strip_surface_and_gpu_limits(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["tracePOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/Trace_POP"
        expected_params = {
            "inputattrscope",
            "posattrib",
            "top",
            "channel",
            "resmult",
            "threshold",
            "inside",
            "extend",
            "twodimensions",
            "uniquepoints",
            "winding",
            "smooth",
            "filterdist",
            "rerangep",
            "tolow",
            "tolow0",
            "tolow1",
            "tohigh",
            "tohigh0",
            "tohigh1",
            "normal",
            "normaldirection",
            "texture",
            "allocfract",
            "setmaxnumls",
            "maxnumls",
            "setmaxnumvertsperls",
            "maxnumvertsperls",
            "cpureadback",
            "bypass",
            "freeextragpumem",
            "delinputattrs",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"tracePOP missing {sorted(expected_params - actual)}"
        assert {
            "TOP image tracing",
            "brightness threshold",
            "Channel menu",
            "Luminance",
            "contour lines",
            "contour line strips",
            "surface triangles",
            "Resolution Multiplier",
            "Smooth Edge Distance",
            "Line Smooth POP",
            "Extend border handling",
            "open line strips",
            "Winding",
            "holes",
            "P(0) -0.5 to 0.5",
            "ReRange P",
            "Normal attribute",
            "Texture Coordinates",
            "GPU preallocation",
            "Max Num Line Strips",
            "Max Num Verts per Line Strip",
            "Copy Topology Info Back to CPU",
            "Info CHOP",
            "Polygonize POP",
            "Triangulate POP",
            "Extrude POP",
        }.issubset(set(card["key_concepts"]))
        assert any(
            "Max Num Line Strips" in note and "GPU" in note and "overflows" in note
            for note in card["common_gotchas"]
        )
        assert any(
            "Fraction of Max Allocation" in note and "missing" in note for note in card["common_gotchas"]
        )
        assert any(
            "Copy Topology Info Back to CPU" in note and "stall" in note for note in card["common_gotchas"]
        )
        assert any(
            "Extend" in note and "border" in note and "open line strips" in note
            for note in card["common_gotchas"]
        )
        assert any("Winding" in note and "holes" in note for note in card["common_gotchas"])
        assert any(
            "Output" in note and "2-point lines" in note and "surface" in note
            for note in card["common_gotchas"]
        )

    def test_top_to_pop_card_covers_rgba_attribute_dimension_depth_and_filtering(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["toptoPOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/TOP_to_POP"
        expected_params = {
            "rgba",
            "maxpointsenable",
            "maxpoints",
            "input0top",
            "input0chanscope",
            "input0attrscope",
            "input0filter",
            "attr0name",
            "attr0customname",
            "attr0type",
            "attr0numcomps",
            "attr0defaultval0",
            "attr0defaultval1",
            "attr0defaultval2",
            "attr0defaultval3",
            "surftype",
            "linex",
            "liney",
            "linez",
            "planex",
            "planey",
            "planez",
            "uniquepoints",
            "tx",
            "ty",
            "tz",
            "overridesizex",
            "overridesizey",
            "overridesizez",
            "sizex",
            "sizey",
            "sizez",
            "overrideresx",
            "overrideresy",
            "overrideresz",
            "resx",
            "resy",
            "resz",
            "pixelsamplingloc",
            "texture",
            "dimension",
            "rerangefromlow",
            "rerangefromhigh",
            "rerangetolow",
            "rerangetohigh",
            "camera",
            "overridecamera",
            "viewanglemethod",
            "fov",
            "focallengthsx",
            "focallengthsy",
            "centerx",
            "centery",
            "deletenear",
            "depthnear",
            "deletefar",
            "depthfar",
            "linestripbehavior",
            "dispscale",
            "bypass",
            "freeextragpumem",
            "delinputattrs",
            "parmcolorspace",
            "parmreferencewhite",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"toptoPOP missing {sorted(expected_params - actual)}"
        assert {
            "TOP pixels to POP points",
            "First RGBA Contains",
            "Color (RGBA)",
            "Position and Active (RGBA)",
            "Position (RGB)",
            "Depth maps",
            "Height maps",
            "Custom attribute mapping",
            "P attribute",
            "Color attribute",
            "active pixels",
            "unused fit-to-square pixels",
            "Use Dimension",
            "Channel Scope",
            "Attribute Scope",
            "TOP pixel filtering",
            "Nearest Pixel",
            "Interpolate Pixels",
            "High Quality Resize",
            "New Attribute block",
            "Connectivity",
            "Point Primitives",
            "Line Strips",
            "Triangles",
            "Quadrilaterals",
            "Line X/Y/Z",
            "Plane XY/YZ/ZX",
            "Unique Points",
            "Pixel Sampling Location",
            "Texture Coordinates",
            "Append Dimension",
            "Camera projection",
            "Focal Lengths",
            "Optical Center",
            "Delete Near Points",
            "Delete Far Points",
            "Line Strip Behavior",
            "Height displacement",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any(
            "Use Dimension" in note and "all pixels" in note and "unused" in note
            for note in card["common_gotchas"]
        )
        assert any(
            "Custom" in note and "4" in note and "attribute components" in note
            for note in card["common_gotchas"]
        )
        assert any(
            "Nearest Pixel" in note and "Interpolate" in note and "data textures" in note
            for note in card["common_gotchas"]
        )
        assert any(
            "Depth" in note and "Camera" in note and "near/far" in note for note in card["common_gotchas"]
        )
        assert any(
            "Connectivity" in note and "Point Primitives" in note and "Line Strips" in note
            for note in card["common_gotchas"]
        )

    def test_merge_and_null_sop_cards_cover_reference_endpoint_and_batching_tradeoffs(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        merge = operator_cards["mergeSOP"]
        assert merge["docs_url"] == "https://docs.derivative.ca/Merge_SOP"
        merge_params = {param["name"] for param in merge["key_params"]}
        assert {"sops"}.issubset(merge_params), f"mergeSOP missing {sorted({'sops'} - merge_params)}"
        assert {
            "multiple SOP inputs",
            "SOPs parameter",
            "wildcard Pattern Matching",
            "unified geometry output",
            "separate primitives",
            "Info CHOP",
            "num_points",
            "num_prims",
            "last_vbo_update_time",
            "Geometry Batches",
            "single draw command",
            "SOP cook time",
            "Object Merge SOP",
            "Select SOP",
        }.issubset(set(merge.get("key_concepts", [])))
        assert any("wildcard" in note and "SOPs parameter" in note for note in merge["common_gotchas"])
        assert any("does not fuse" in note and "Fuse SOP" in note for note in merge["common_gotchas"])
        assert any("batch" in note and "same material" in note for note in merge["common_gotchas"])
        assert any("cook every frame" in note and "cost more" in note for note in merge["common_gotchas"])

        null = operator_cards["nullSOP"]
        assert null["docs_url"] == "https://docs.derivative.ca/Null_SOP"
        assert null["key_params"] == []
        assert {
            "No parameters",
            "no effect on geometry",
            "instance of input SOP",
            "stable reference endpoint",
            "upstream edits without reference updates",
            "Geometry COMP",
            "Select SOP",
            "Object Merge SOP",
            "Info CHOP",
            "num_points",
            "num_prims",
            "last_vbo_update_time",
        }.issubset(set(null.get("key_concepts", [])))
        assert any("No parameters" in note and "intentionally" in note for note in null["common_gotchas"])
        assert any("Geometry COMPs" in note and "Null SOP" in note for note in null["common_gotchas"])
        assert any("Select SOP" in note and "Object Merge SOP" in note for note in null["common_gotchas"])

    def test_null_chop_top_pop_cards_cover_family_specific_endpoint_behavior(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        null_chop = operator_cards["nullCHOP"]
        assert null_chop["docs_url"] == "https://docs.derivative.ca/Null_CHOP"
        null_chop_params = {param["name"] for param in null_chop["key_params"]}
        assert {
            "cooktype",
            "checkvalues",
            "checknames",
            "checkrange",
            "timeslice",
            "scope",
            "srselect",
            "exportmethod",
            "autoexportroot",
            "exporttable",
            "commonrenamefrom",
            "commonrenameto",
        }.issubset(null_chop_params)
        assert {
            "place-holder",
            "does not alter CHOP data",
            "stable CHOP export endpoint",
            "Export channels to parameters",
            "Cook Type",
            "Automatic",
            "Always",
            "Selective",
            "Check Values",
            "Check Names",
            "Check Range",
            "Time Slice",
            "Scope",
            "Sample Rate Match",
            "Export Method",
            "Info CHOP",
            "start",
            "length",
            "sample_rate",
            "num_channels",
            "time_slice",
            "export_sernum",
        }.issubset(set(null_chop.get("key_concepts", [])))
        assert any(
            "Selective" in note and "static" in note and "upstream" in note
            for note in null_chop["common_gotchas"]
        )
        assert any(
            "Export Method" in note and "channel names" in note for note in null_chop["common_gotchas"]
        )
        assert any("export_sernum" in note and "Info CHOP" in note for note in null_chop["common_gotchas"])

        null_top = operator_cards["nullTOP"]
        assert null_top["docs_url"] == "https://docs.derivative.ca/Null_TOP"
        null_top_params = {param["name"] for param in null_top["key_params"]}
        assert "cook" not in null_top_params
        assert {
            "outputresolution",
            "resolution",
            "resmenu",
            "resmult",
            "outputaspect",
            "aspect",
            "armenu",
            "inputfiltertype",
            "fillmode",
            "filtertype",
            "npasses",
            "chanmask",
            "format",
        }.issubset(null_top_params)
        assert {
            "no effect on image",
            "instance of input TOP",
            "stable TOP reference endpoint",
            "No Null-page parameters",
            "Output Resolution",
            "Input Smoothness",
            "Pixel Format",
            "Info CHOP",
            "resx",
            "resy",
            "aspectx",
            "aspecty",
            "depth",
            "gpu_memory_used",
        }.issubset(set(null_top.get("key_concepts", [])))
        assert any(
            "No Null-page parameters" in note and "Common page" in note for note in null_top["common_gotchas"]
        )
        assert any(
            "Use Input" in note and "resolution" in note and "aspect" in note
            for note in null_top["common_gotchas"]
        )
        assert any("gpu_memory_used" in note and "Info CHOP" in note for note in null_top["common_gotchas"])

        null_pop = operator_cards["nullPOP"]
        assert null_pop["docs_url"] == "https://docs.derivative.ca/Null_POP"
        null_pop_params = {param["name"] for param in null_pop["key_params"]}
        assert null_pop_params == {"bypass"}
        assert {
            "does nothing",
            "passes input unchanged",
            "no CPU or GPU memory",
            "stable POP reference endpoint",
            "meaningful Null POP name",
            "unchanged attributes are references",
            "middle-click popup info",
            "(r) reference marker",
            "Bypass",
            "Info CHOP",
        }.issubset(set(null_pop.get("key_concepts", [])))
        assert {"POP_snippets", "POP_attribute_ontology"}.issubset(set(null_pop["related_snippets"]))
        assert any("CPU or GPU memory" in note and "unchanged" in note for note in null_pop["common_gotchas"])
        assert any(
            "attribute" in note and "(r)" in note and "middle-click" in note
            for note in null_pop["common_gotchas"]
        )
        assert any("meaningful" in note and "downstream" in note for note in null_pop["common_gotchas"])

    def test_select_and_switch_cards_cover_routing_patterns_indices_and_info_channels(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        top_common_params = {
            "outputresolution",
            "resolution",
            "resmenu",
            "resmult",
            "outputaspect",
            "aspect",
            "armenu",
            "inputfiltertype",
            "fillmode",
            "filtertype",
            "npasses",
            "chanmask",
            "format",
        }
        top_info_concepts = {"Info CHOP", "resx", "resy", "aspectx", "aspecty", "depth", "gpu_memory_used"}

        select_top = operator_cards["selectTOP"]
        assert select_top["docs_url"] == "https://docs.derivative.ca/Select_TOP"
        select_top_params = {param["name"] for param in select_top["key_params"]}
        assert {"top"}.union(top_common_params).issubset(select_top_params)
        assert {
            "reference a TOP from any other location",
            "save graphics memory",
            "instance of referenced TOP",
            "TOP path",
            "drag and drop TOP target",
            "stable cross-network texture reference",
            "Output Resolution",
            "Pixel Format",
        }.union(top_info_concepts).issubset(set(select_top.get("key_concepts", [])))
        assert any("graphics memory" in note and "instance" in note for note in select_top["common_gotchas"])
        assert any(
            "Use Input" in note and "resolution" in note and "pixel format" in note
            for note in select_top["common_gotchas"]
        )
        assert any("path" in note and "renamed" in note for note in select_top["common_gotchas"])

        select_chop = operator_cards["selectCHOP"]
        assert select_chop["docs_url"] == "https://docs.derivative.ca/Select_CHOP"
        select_chop_params = {param["name"] for param in select_chop["key_params"]}
        assert {
            "chop",
            "channames",
            "renamefrom",
            "renameto",
            "filterbydigits",
            "digits",
            "stripdigits",
            "align",
            "autoprefix",
            "timeslice",
            "scope",
            "srselect",
            "exportmethod",
            "autoexportroot",
            "exporttable",
        }.issubset(select_chop_params)
        assert {
            "selects and renames CHOP channels",
            "one or more CHOPs",
            "specified output order",
            "duplicate channel selections",
            "CHOP and Channel Name parameters",
            "wired input",
            "Pattern Matching",
            "Pattern Replacement",
            "Pattern Expansion",
            "Channel Naming Patterns",
            "Rename CHOP",
            "Filter by Digits",
            "Align",
            "Automatic Prefix",
            "Info CHOP",
            "start",
            "length",
            "sample_rate",
            "num_channels",
            "time_slice",
            "export_sernum",
        }.issubset(set(select_chop.get("key_concepts", [])))
        assert any("order" in note and "multiple times" in note for note in select_chop["common_gotchas"])
        assert any(
            "Rename" in note and "CHOP and Channel Name" in note and "wired input" in note
            for note in select_chop["common_gotchas"]
        )
        assert any(
            "Automatic Prefix" in note and "duplicate" in note for note in select_chop["common_gotchas"]
        )

        switch_top = operator_cards["switchTOP"]
        assert switch_top["docs_url"] == "https://docs.derivative.ca/Switch_TOP"
        switch_top_params = {param["name"] for param in switch_top["key_params"]}
        assert {"index", "blend", "extend"}.union(top_common_params).issubset(switch_top_params)
        assert {
            "multi-input TOP switch",
            "Index parameter",
            "first input is 0",
            "Blend between Inputs",
            "floating point index",
            "Extend",
            "out-of-range index",
            "negative indices",
            "Clamp",
            "Loop",
            "ZigZag",
            "Output Resolution",
            "Pixel Format",
        }.union(top_info_concepts).issubset(set(switch_top.get("key_concepts", [])))
        assert any("0-based" in note and "first input" in note for note in switch_top["common_gotchas"])
        assert any("Blend" in note and "floating point" in note for note in switch_top["common_gotchas"])
        assert any(
            "Extend" in note and "negative" in note and "out of range" in note
            for note in switch_top["common_gotchas"]
        )

        switch_sop = operator_cards["switchSOP"]
        assert switch_sop["docs_url"] == "https://docs.derivative.ca/Switch_SOP"
        switch_sop_params = {param["name"] for param in switch_sop["key_params"]}
        assert {"input", "extend"}.issubset(switch_sop_params)
        assert {
            "up to 9999 possible inputs",
            "Select Input field",
            "expression-driven switching",
            "first source is 0",
            "Extend",
            "out-of-range index",
            "negative indices",
            "Clamp",
            "Loop",
            "ZigZag",
            "me.time.frame - 1",
            "me.time.frame > 5",
            "Info CHOP",
            "num_points",
            "num_prims",
            "num_particles",
            "last_vbo_update_time",
            "last_meta_vbo_update_time",
        }.issubset(set(switch_sop.get("key_concepts", [])))
        assert any("9999" in note and "inputs" in note for note in switch_sop["common_gotchas"])
        assert any("expression" in note and "topology" in note for note in switch_sop["common_gotchas"])
        assert any(
            "Extend" in note and "negative" in note and "out of range" in note
            for note in switch_sop["common_gotchas"]
        )

    def test_core_render_pipeline_cards_cover_component_roles_instancing_and_render_targets(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        comp_extension_params = {
            "reinitextensions",
            "initextonstart",
            "ext",
            "ext0object",
            "ext0name",
            "ext0promote",
        }
        comp_common_params = {
            "parentshortcut",
            "opshortcut",
            "iop",
            "iop0shortcut",
            "iop0op",
            "opviewer",
            "enablecloning",
            "enablecloningpulse",
            "clone",
            "loadondemand",
            "enableexternaltox",
            "enableexternaltoxpulse",
            "externaltox",
            "reloadcustom",
            "reloadbuiltin",
            "savebackup",
            "subcompname",
            "relpath",
        }
        object_xform_params = {
            "xord",
            "rord",
            "t",
            "r",
            "s",
            "p",
            "scale",
            "parentxformsrc",
            "parentobject",
            "lookat",
            "forwarddir",
            "lookup",
            "pathsop",
            "roll",
            "pos",
            "pathorient",
            "up",
            "bank",
        }
        object_render_params = {"material", "render", "drawpriority", "pickpriority", "wcolor", "lightmask"}
        comp_info_concepts = {"Info CHOP", "num_children"}

        base = operator_cards["baseCOMP"]
        assert base["docs_url"] == "https://docs.derivative.ca/Base_COMP"
        base_params = {param["name"] for param in base["key_params"]}
        assert comp_extension_params.union(comp_common_params).issubset(base_params)
        assert {
            "no panel parameters",
            "no 3D object parameters",
            "component with no panel associated",
            "Extensions page",
            "Re-Init Extensions",
            "Init Extensions On Start",
            ".ext member",
            "Parent Shortcut",
            "Global OP Shortcut",
            "Internal OP",
            "Operator Viewer",
            "cloning",
            "Clone Master",
            "Load on Demand",
            "external .tox",
            "Relative File Path Behavior",
        }.union(comp_info_concepts).issubset(set(base.get("key_concepts", [])))
        assert any(
            "Base COMP" in note and "no panel" in note and "no 3D" in note for note in base["common_gotchas"]
        )
        assert any(".ext" in note and "Promote" in note for note in base["common_gotchas"])
        assert any("External .tox" in note and ".toe" in note for note in base["common_gotchas"])
        assert any("Load on Demand" in note and "memory" in note for note in base["common_gotchas"])

        camera = operator_cards["cameraCOMP"]
        assert camera["docs_url"] == "https://docs.derivative.ca/Camera_COMP"
        camera_params = {param["name"] for param in camera["key_params"]}
        assert object_xform_params.union(
            {
                "projection",
                "projectionblend",
                "orthowidth",
                "viewanglemethod",
                "fov",
                "focal",
                "aperture",
                "near",
                "far",
                "winrollpivot",
                "win",
                "winsize",
                "winroll",
                "ipdshift",
                "projmatrixop",
                "customproj",
                "quadreprojsop",
                "quadreprojpts",
                "bgcolor",
                "premultrgbbyalpha",
                "fog",
                "fogdensity",
                "fognear",
                "fogfar",
                "fogcolor",
                "fogalpha",
                "fogmap",
                "camlightmask",
            },
            object_render_params,
            comp_extension_params,
        ).issubset(camera_params)
        assert {
            "3D object",
            "real-world camera",
            "Render TOP",
            "Geometry Viewer",
            "cameraViewport",
            "3D hierarchy",
            "Transform Order",
            "Rotate Order",
            "Parent Transform Source",
            "Look At",
            "Null Component center of interest",
            "Perspective",
            "Orthographic",
            "Custom Projection Matrix",
            "FOV Angle",
            "Near/Far clipping planes",
            "z-depth artifacts",
            "Camera Light Mask",
            "Render flag logical AND",
            "Draw Priority",
            "Pick Priority",
        }.union(comp_info_concepts).issubset(set(camera.get("key_concepts", [])))
        assert any(
            "Scaling a camera" in note and "not generally recommended" in note
            for note in camera["common_gotchas"]
        )
        assert any(
            "Near" in note and "Far" in note and "z-depth" in note for note in camera["common_gotchas"]
        )
        assert any("Look At" in note and "Null Component" in note for note in camera["common_gotchas"])
        assert any("Camera Light Mask" in note and "Render TOP" in note for note in camera["common_gotchas"])

        geometry = operator_cards["geometryCOMP"]
        assert geometry["docs_url"] == "https://docs.derivative.ca/Geometry_COMP"
        geometry_params = {param["name"] for param in geometry["key_params"]}
        assert object_xform_params.union(
            {
                "instancing",
                "instancecountmode",
                "numinstances",
                "instanceop",
                "instancefirstrow",
                "instxord",
                "instrord",
                "instancetop",
                "instanceactive",
                "instancetx",
                "instancety",
                "instancetz",
                "instancerop",
                "instancerx",
                "instancery",
                "instancerz",
                "instancesop",
                "instancesx",
                "instancesy",
                "instancesz",
                "instancepop",
                "instancepx",
                "instancepy",
                "instancepz",
                "instancerottoorder",
                "instancerottoforward",
                "instancerottoop",
                "instancerottox",
                "instancerottoy",
                "instancerottoz",
                "instancerotupop",
                "instancerotupx",
                "instancerotupy",
                "instancerotupz",
                "instanceorder",
                "instancetexmode",
                "instancetexcoordop",
                "instanceu",
                "instancev",
                "instancew",
                "instancecolormode",
                "instancecolorop",
                "instancer",
                "instanceg",
                "instanceb",
                "instancea",
                "instancetexs",
                "instancetexindexop",
                "instancetexindex",
                "instance",
                "instance0customop",
                "instance0customx",
                "instance0customy",
                "instance0customz",
                "instance0customw",
            },
            object_render_params,
            comp_extension_params,
        ).issubset(geometry_params)
        assert {
            "3D surface",
            "3D Object",
            "Render TOP",
            "Lights and Cameras affect scene",
            "POP network",
            "Render Flag",
            "Display Flag",
            "Geometry Viewer",
            "Texture Map POP",
            "Material MAT",
            "hardware instances",
            "instance ID",
            "Render Pick CHOP",
            "TOP RGBA channels",
            "CHOP channels",
            "DAT rows",
            "SOP attributes",
            "Instance Count Mode",
            "Instance OP(s) Length",
            "Instance Textures",
            "Texture Index",
            "Custom Instance",
            "TDInstanceCustomAttrib0()",
            "GLSL MAT",
            "Render flag logical AND",
            "Draw Priority",
            "Pick Priority",
            "Light Mask",
        }.union(comp_info_concepts).issubset(set(geometry.get("key_concepts", [])))
        assert any("Render Flag" in note and "Display Flag" in note for note in geometry["common_gotchas"])
        assert any("Every Geometry" in note and "Material" in note for note in geometry["common_gotchas"])
        assert any("Light Mask" in note and "Render TOP" in note for note in geometry["common_gotchas"])
        assert any(
            "TOP" in note and "CHOP" in note and "DAT" in note and "SOP" in note
            for note in geometry["common_gotchas"]
        )
        assert any(
            "custom attributes" in note and "GLSL MAT" in note and "PBR MAT" in note
            for note in geometry["common_gotchas"]
        )

        render_top = operator_cards["renderTOP"]
        assert render_top["docs_url"] == "https://docs.derivative.ca/Render_TOP"
        render_top_params = {param["name"] for param in render_top["key_params"]}
        assert {
            "camera",
            "multicamerahint",
            "geometry",
            "lights",
            "antialias",
            "bgcolor",
            "premultrgbbyalpha",
            "rendermode",
            "posside",
            "negside",
            "uvunwrapcoord",
            "uvunwrapcoordattrib",
            "transparency",
            "depthpeel",
            "transpeellayers",
            "render",
            "renderpulse",
            "dither",
            "coloroutputneeded",
            "drawdepthonly",
            "numcolorbufs",
            "allowbufblending",
            "depthformat",
            "cullface",
            "overridemat",
            "polygonoffset",
            "polygonoffsetfactor",
            "polygonoffsetunits",
            "overdraw",
            "overdrawlimit",
            "cropleft",
            "cropleftunit",
            "cropright",
            "croprightunit",
            "cropbottom",
            "cropbottomunit",
            "croptop",
            "croptopunit",
            "vec",
            "vec0name",
            "vec0value",
            "sampler",
            "sampler0name",
            "sampler0top",
            "sampler0extendu",
            "sampler0extendv",
            "sampler0extendw",
            "sampler0filter",
            "sampler0anisotropy",
            "image",
            "image0name",
            "image0arraylength",
            "image0res",
            "image0format",
            "image0type",
            "image0depth",
            "image0access",
            "outputresolution",
            "resolution",
            "resmenu",
            "resmult",
            "outputaspect",
            "aspect",
            "armenu",
            "inputfiltertype",
            "fillmode",
            "filtertype",
            "npasses",
            "chanmask",
            "format",
            "parmcolorspace",
            "parmreferencewhite",
        }.issubset(render_top_params)
        assert {
            "render all 3D scenes",
            "Camera object",
            "Geometry object",
            "Material MAT",
            "Phong MAT",
            "GLSL shaders",
            "TOP textures",
            "RGBA and single-channel formats",
            "Multi-Pass Depth Peeling",
            "Order Independent Transparency",
            "Multiple Cameras",
            "Render Select TOP",
            "Multi-Camera Rendering",
            "Images page",
            "Pattern Matching",
            "Camera Light Mask",
            "Depth Peeling disables Multi-Camera rendering",
            "Anti-Alias memory",
            "Render Mode",
            "Cube Map",
            "Fish-Eye",
            "UV Unwrap",
            "Depth TOP",
            "Color Output Needed",
            "Draw Depth Only",
            "# of Color Buffers",
            "Allow Blending for Extra Buffers",
            "Depth Buffer Format",
            "Override Material",
            "Polygon Depth Offset",
            "Display Overdraw",
            "Crop projection matrix",
            "GLSL MAT vectors",
            "GLSL MAT samplers",
            "TDImageStore_Name()",
            "TDImageLoad_Name()",
            "image outputs",
            "Output Resolution",
            "Pixel Format",
            "Info CHOP",
            "resx",
            "resy",
            "gpu_memory_used",
        }.issubset(set(render_top.get("key_concepts", [])))
        assert any(
            "Camera" in note and "Geometry" in note and "Material" in note
            for note in render_top["common_gotchas"]
        )
        assert any("Pattern Matching" in note and "^" in note for note in render_top["common_gotchas"])
        assert any(
            "Multi-Camera" in note and "Camera Light Mask" in note for note in render_top["common_gotchas"]
        )
        assert any(
            "Depth Peeling" in note and "Multi-Camera" in note for note in render_top["common_gotchas"]
        )
        assert any("crop" in note.lower() and "aspect" in note for note in render_top["common_gotchas"])
        assert any(
            "Images page" in note and "Render Select TOP" in note for note in render_top["common_gotchas"]
        )

    def test_feedback_source_and_control_cards_cover_top_chop_dat_runtime_metadata(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        top_common_params = {
            "outputresolution",
            "resolution",
            "resmenu",
            "resmult",
            "outputaspect",
            "aspect",
            "armenu",
            "inputfiltertype",
            "fillmode",
            "filtertype",
            "npasses",
            "chanmask",
            "format",
        }
        top_info_concepts = {"Info CHOP", "resx", "resy", "aspectx", "aspecty", "depth", "gpu_memory_used"}

        feedback = operator_cards["feedbackTOP"]
        assert feedback["docs_url"] == "https://docs.derivative.ca/Feedback_TOP"
        feedback_params = {param["name"] for param in feedback["key_params"]}
        assert {"top", "reset", "resetpulse"}.union(top_common_params).issubset(feedback_params)
        assert {
            "feedback effects",
            "fake motion blur",
            "not clearing the color buffer",
            "Bypass Feedback",
            "Target TOP",
            "downstream in the feedback network",
            "filter TOPs between Feedback TOP and Target TOP",
            "OP Snippets",
            "3D Textures",
            "2D Texture Arrays",
            "Output Resolution",
            "Pixel Format",
        }.union(top_info_concepts).issubset(set(feedback.get("key_concepts", [])))
        assert any("Target TOP" in note and "downstream" in note for note in feedback["common_gotchas"])
        assert any("Reset" in note and "passes through" in note for note in feedback["common_gotchas"])
        assert any("Reset Pulse" in note and "single frame" in note for note in feedback["common_gotchas"])

        composite = operator_cards["compositeTOP"]
        assert composite["docs_url"] == "https://docs.derivative.ca/Composite_TOP"
        composite_params = {param["name"] for param in composite["key_params"]}
        assert {
            "top",
            "previewgrid",
            "selectinput",
            "inputindex",
            "operand",
            "swaporder",
            "size",
            "prefit",
            "justifyh",
            "justifyv",
            "extend",
            "r",
            "t",
            "tunit",
            "s",
            "p",
            "punit",
            "tstep",
            "tstepunit",
            "legacyxform",
        }.union(top_common_params).issubset(composite_params)
        assert {
            "multi-input TOP",
            "composite operation for each input",
            "Operation parameter",
            "blendModes Palette component",
            "OP Snippets",
            "3D Textures",
            "2D Texture Arrays",
            "TOPs field",
            "Pattern Matching",
            "Preview Grid",
            "Select Input",
            "Input Index",
            "Swap Operation Order",
            "Fixed Layer",
            "Overlay layer",
            "final resolution and aspect ratio",
            "Pre-Fit Overlay",
            "Native Resolution",
            "pixel accurate composites",
        }.union(top_info_concepts).issubset(set(composite.get("key_concepts", [])))
        assert any("Swap Operation Order" in note and "Over" in note for note in composite["common_gotchas"])
        assert any(
            "Fixed Layer" in note and "does not change" in note and "order" in note
            for note in composite["common_gotchas"]
        )
        assert any(
            "Native Resolution" in note and "pixel accurate" in note for note in composite["common_gotchas"]
        )
        assert any(
            "TOPs field" in note and "Pattern Matching" in note for note in composite["common_gotchas"]
        )

        constant_top = operator_cards["constantTOP"]
        assert constant_top["docs_url"] == "https://docs.derivative.ca/Constant_TOP"
        constant_top_params = {param["name"] for param in constant_top["key_params"]}
        assert {
            "color",
            "colorr",
            "colorg",
            "colorb",
            "alpha",
            "multrgbbyalpha",
            "rgbaunit",
            "compoverinput",
            "operand",
            "swaporder",
            "type",
            "slices",
        }.union(top_common_params).issubset(constant_top_params)
        assert {
            "solid color TOP image",
            "red, green, blue, and alpha channels",
            "RGB and HSV color picker",
            "Multiply RGB by Alpha",
            "RGBA Units",
            "data values always use 0-1",
            "Comp Over Input",
            "Operation",
            "Output Type",
            "2D Texture",
            "3D Texture",
            "2D Texture Array",
            "Slices",
            "3D Textures",
            "2D Texture Arrays",
        }.union(top_info_concepts).issubset(set(constant_top.get("key_concepts", [])))
        assert any(
            "RGBA Units" in note and "data values" in note and "0-1" in note
            for note in constant_top["common_gotchas"]
        )
        assert any("Output Type" in note and "no inputs" in note for note in constant_top["common_gotchas"])
        assert any(
            "Multiply RGB by Alpha" in note and "premultipl" in note
            for note in constant_top["common_gotchas"]
        )

        constant_chop = operator_cards["constantCHOP"]
        assert constant_chop["docs_url"] == "https://docs.derivative.ca/Constant_CHOP"
        constant_chop_params = {param["name"] for param in constant_chop["key_params"]}
        assert {
            "const",
            "const0name",
            "const0value",
            "snap",
            "first",
            "current",
            "single",
            "start",
            "startunit",
            "end",
            "endunit",
            "rate",
            "left",
            "right",
            "defval",
            "timeslice",
            "scope",
            "srselect",
            "exportmethod",
            "autoexportroot",
            "exporttable",
        }.issubset(constant_chop_params)
        assert {
            "constant-value channels",
            "name/value pairs",
            "Name field creates channels",
            "Pattern Expansion",
            "one sample long by default",
            "CHOP interval",
            "Snapshot Input",
            "Parameter CHOP",
            "par.snap.pulse()",
            "First Channel",
            "40 channels",
            "Active input",
            "Active Needs Current",
            "Mouse In CHOP",
            "MIDI In CHOP",
            "Single Sample",
            "Sample Rate",
            "Extend Left",
            "Extend Right",
            "Default Value",
            "Time Slice",
            "Export Method",
            "Info CHOP",
            "start",
            "length",
            "sample_rate",
            "num_channels",
            "time_slice",
            "export_sernum",
        }.issubset(set(constant_chop.get("key_concepts", [])))
        assert any(
            "Name field" in note and "creates" in note and "channel" in note
            for note in constant_chop["common_gotchas"]
        )
        assert any(
            "one sample" in note and "Channel page" in note for note in constant_chop["common_gotchas"]
        )
        assert any(
            "Snapshot Input" in note and "Parameter CHOP" in note for note in constant_chop["common_gotchas"]
        )
        assert any(
            "Active input" in note and "greater than zero" in note for note in constant_chop["common_gotchas"]
        )

        level = operator_cards["levelTOP"]
        assert level["docs_url"] == "https://docs.derivative.ca/Level_TOP"
        level_params = {param["name"] for param in level["key_params"]}
        assert {
            "clampinput",
            "invert",
            "blacklevel",
            "brightness1",
            "gamma1",
            "contrast",
            "inlow",
            "inhigh",
            "outlow",
            "outhigh",
            "lowr",
            "highr",
            "lowg",
            "highg",
            "lowb",
            "highb",
            "lowa",
            "higha",
            "stepping",
            "stepsize",
            "threshold",
            "clamplow",
            "clamphigh",
            "soften",
            "gamma2",
            "opacity",
            "brightness2",
            "clamp",
            "clamplow2",
            "clamphigh2",
            "premultrgbbyalpha",
        }.union(top_common_params).issubset(level_params)
        assert {
            "contrast",
            "brightness",
            "gamma",
            "black level",
            "color range",
            "quantization",
            "opacity",
            "Luma Level TOP",
            "single pass",
            "lookup table on the CPU",
            "Clamp Input",
            "floating pixel formats",
            "Invert",
            "Range Page",
            "RGBA Page",
            "Step Page",
            "posterizing",
            "Post Page",
            "Pre-Multiply RGB by Alpha",
            "3D Textures",
            "2D Texture Arrays",
        }.union(top_info_concepts).issubset(set(level.get("key_concepts", [])))
        assert any(
            "animating" in note and "lookup table" in note and "performance" in note
            for note in level["common_gotchas"]
        )
        assert any("Clamp Input" in note and "floating" in note for note in level["common_gotchas"])
        assert any("opacity" in note and "feedback" in note for note in level["common_gotchas"])
        assert any(
            "Luma Level TOP" in note and "hue" in note and "slower" in note
            for note in level["common_gotchas"]
        )

        noise = operator_cards["noiseTOP"]
        assert noise["docs_url"] == "https://docs.derivative.ca/Noise_TOP"
        noise_params = {param["name"] for param in noise["key_params"]}
        assert {
            "type",
            "seed",
            "period",
            "harmon",
            "spread",
            "gain",
            "rough",
            "exp",
            "amp",
            "offset",
            "mono",
            "aspectcorrect",
            "xord",
            "rord",
            "t",
            "r",
            "s",
            "p",
            "t4d",
            "s4d",
            "rgb",
            "inputscale",
            "noisescale",
            "alpha",
            "dither",
            "gradient",
            "mode",
        }.union(top_common_params).issubset(noise_params)
        assert {
            "Perlin noise",
            "Simplex noise",
            "Sparse Convolution",
            "Random (GPU)",
            "Alligator",
            "Seed",
            "Period",
            "Harmonics",
            "Roughness",
            "Monochrome",
            "Aspect Correct",
            "sampling plane",
            "noise space",
            "Translate 4D",
            "Scale 4D",
            "Noise Coordinate Map",
            "3D Texture",
            "Texture 3D TOP",
            "GLSL TOP",
            "Input * Noise",
            "Alpha",
            "Gradient",
            "Performance mode",
            "Quality mode",
        }.union(top_info_concepts).issubset(set(noise.get("key_concepts", [])))
        assert any(
            "Period" in note and "opposite" in note and "frequency" in note
            for note in noise["common_gotchas"]
        )
        assert any(
            "second input" in note and "RGBA" in note and "coordinates" in note
            for note in noise["common_gotchas"]
        )
        assert any("3D Texture" in note and "Texture 3D TOP" in note for note in noise["common_gotchas"])
        assert any(
            "Gradient" in note and "Simplex" in note and "Perlin" in note for note in noise["common_gotchas"]
        )
        assert any("Quality" in note and "speed" in note for note in noise["common_gotchas"])

        text = operator_cards["textDAT"]
        assert text["docs_url"] == "https://docs.derivative.ca/Text_DAT"
        text_params = {param["name"] for param in text["key_params"]}
        assert {
            "edit",
            "file",
            "syncfile",
            "loadonstart",
            "loadonstartpulse",
            "write",
            "writepulse",
            "language",
            "extension",
            "customext",
            "wordwrap",
        }.issubset(text_params)
        assert {
            "free-form multi-line ASCII text",
            "scripts",
            "GLSL shaders",
            "notes",
            "XML",
            "free-form text",
            "Table DAT",
            "Viewer Active",
            "external text editor",
            "file on disk",
            "file on the web",
            "http://",
            "Execute DATs",
            "Web DAT",
            ".txt and .dat files",
            "Sync to File",
            "Load on Start",
            "Write on Toe Save",
            "Language",
            "Edit/View Extension",
            "Custom Extension",
            "Word Wrap",
            "Info CHOP",
            "num_rows",
            "num_cols",
        }.issubset(set(text.get("key_concepts", [])))
        assert any("Text DAT" in note and "does not execute" in note for note in text["common_gotchas"])
        assert any(
            "Sync to File" in note and "immediately" in note and "monitored" in note
            for note in text["common_gotchas"]
        )
        assert any("file is removed" in note and "retain" in note for note in text["common_gotchas"])
        assert any("http://" in note and "Web DAT" in note for note in text["common_gotchas"])

    def test_profile_ui_audio_and_pop_cards_cover_runtime_control_and_attribute_semantics(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        comp_panel_params = {
            "x",
            "y",
            "w",
            "h",
            "fixedaspect",
            "aspect",
            "layer",
            "hmode",
            "vmode",
            "alignallow",
            "alignorder",
            "display",
            "enable",
            "cursor",
            "multitouch",
            "clickthrough",
            "opacity",
        }
        comp_panel_concepts = {
            "Panel Component",
            "Panel Values",
            "Layout Page",
            "Panel Page",
            "Look Page",
            "Children Page",
            "Drag/Drop Page",
            "Extensions Page",
            "Info CHOP",
            "num_children",
        }
        chop_common_params = {
            "timeslice",
            "scope",
            "srselect",
            "exportmethod",
            "autoexportroot",
            "exporttable",
            "commonrenamefrom",
            "commonrenameto",
        }
        chop_info_concepts = {
            "Info CHOP",
            "start",
            "length",
            "sample_rate",
            "num_channels",
            "time_slice",
            "export_sernum",
        }
        top_common_params = {
            "outputresolution",
            "resolution",
            "resmenu",
            "resmult",
            "outputaspect",
            "aspect",
            "armenu",
            "inputfiltertype",
            "fillmode",
            "filtertype",
            "npasses",
            "chanmask",
            "format",
        }
        top_info_concepts = {
            "Info CHOP",
            "resx",
            "resy",
            "aspectx",
            "aspecty",
            "depth",
            "gpu_memory_used",
        }
        pop_common_params = {"bypass", "freeextragpumem", "delinputattrs"}
        pop_runtime_concepts = {
            "POP attributes",
            "Point List",
            "Primitive List",
            "Vertex List",
            "P attribute",
            "point attributes",
            "vertex attributes",
            "primitive attributes",
            "groups",
            "Info CHOP",
            "cook_time",
        }

        button = operator_cards["buttonCOMP"]
        assert button["docs_url"] == "https://docs.derivative.ca/Button_COMP"
        button_params = {param["name"] for param in button["key_params"]}
        assert {
            "label",
            "value0",
            "buttontype",
            "buttongroup",
            "buttongroupdat",
            "scaletofit",
            "fontsize",
            "textpadding",
            "color",
            "colorr",
            "colorg",
            "colorb",
        }.union(comp_panel_params).issubset(button_params)
        assert "toggle" not in button_params
        assert {
            "interactive on/off buttons",
            "momentary buttons",
            "toggle buttons",
            "radio buttons",
            "exclusive buttons",
            "Button Group Label",
            "Button Group DAT",
            "Table DAT",
            "Pattern Matching",
            "Panel CHOP",
        }.union(comp_panel_concepts).issubset(set(button.get("key_concepts", [])))
        assert any(
            "Button Type" in note and "momentary" in note and "radio" in note
            for note in button["common_gotchas"]
        )
        assert any(
            "Button Group Label" in note and "same component" in note for note in button["common_gotchas"]
        )
        assert any("Button Group DAT" in note and "scattered" in note for note in button["common_gotchas"])

        slider = operator_cards["sliderCOMP"]
        assert slider["docs_url"] == "https://docs.derivative.ca/Slider_COMP"
        slider_params = {param["name"] for param in slider["key_params"]}
        assert {
            "label",
            "slidertype",
            "value0",
            "value1",
            "zonel",
            "zoner",
            "zoneb",
            "zonet",
            "clampul",
            "clampuh",
            "clampvl",
            "clampvh",
        }.union(comp_panel_params).issubset(slider_params)
        assert "rangemin" not in slider_params
        assert "rangemax" not in slider_params
        assert {
            "X slider",
            "Y slider",
            "XY slider",
            "Panel CHOP placed in the Slider component",
            "one or two channels",
            "Panel Value",
            "u Panel Value",
            "v Panel Value",
            "Zone Left",
            "Zone Right",
            "Clamp U Low",
            "Clamp V High",
        }.union(comp_panel_concepts).issubset(set(slider.get("key_concepts", [])))
        assert any("Panel CHOP" in note and "Slider component" in note for note in slider["common_gotchas"])
        assert any("Slider UV" in note and "value1" in note for note in slider["common_gotchas"])
        assert any(
            "Zone" in note and "outside" in note and "0-1" in note for note in slider["common_gotchas"]
        )

        container = operator_cards["containerCOMP"]
        assert container["docs_url"] == "https://docs.derivative.ca/Container_COMP"
        container_params = {param["name"] for param in container["key_params"]}
        assert {
            "bgcolor",
            "bgcolorr",
            "bgcolorg",
            "bgcolorb",
            "bgalpha",
            "top",
            "topfill",
            "topsmoothness",
            "composite",
            "align",
            "spacing",
            "alignmax",
            "margin",
            "justifyh",
            "justifyv",
            "fit",
            "scale",
            "offset",
            "crop",
            "phscrollbar",
            "pvscrollbar",
            "scrollbarthickness",
        }.union(comp_panel_params).issubset(container_params)
        assert {
            "groups Panel Components",
            "control panel",
            "sliders",
            "buttons",
            "viewer panels",
            "parent alignment",
            "child alignment",
            "Grid Rows",
            "Grid Columns",
            "Match Network Nodes",
            "scrollbars",
            "Crop",
            "Drag-and-Drop",
        }.union(comp_panel_concepts).issubset(set(container.get("key_concepts", [])))
        assert any(
            "Display" in note and "opacity" in note and "layout" in note
            for note in container["common_gotchas"]
        )
        assert any("Align Order" in note and "children" in note for note in container["common_gotchas"])
        assert any("Margin" in note and "absolute pixels" in note for note in container["common_gotchas"])

        math = operator_cards["mathCHOP"]
        assert math["docs_url"] == "https://docs.derivative.ca/Math_CHOP"
        math_params = {param["name"] for param in math["key_params"]}
        assert {
            "preop",
            "chanop",
            "chopop",
            "postop",
            "match",
            "align",
            "interppars",
            "integer",
            "preoff",
            "gain",
            "postoff",
            "fromrange",
            "fromrange1",
            "fromrange2",
            "torange",
            "torange1",
            "torange2",
        }.union(chop_common_params).issubset(math_params)
        assert {
            "arithmetic operations on channels",
            "Channel Pre OP",
            "Combine Channels",
            "Combine CHOPs",
            "Channel Post OP",
            "Match by",
            "Align",
            "Interp Pars per Sample",
            "Mult-Add Page",
            "Pre-Add",
            "Multiply",
            "Post-Add",
            "Range Page",
            "linear scaling",
            "Integer",
            "Logic CHOP",
        }.union(chop_info_concepts).issubset(set(math.get("key_concepts", [])))
        assert any("Logic CHOP" in note and "logic operations" in note for note in math["common_gotchas"])
        assert any(
            "Interp Pars per Sample" in note and "audio" in note and "pops" in note
            for note in math["common_gotchas"]
        )
        assert any(
            "Match by" in note and "Align" in note and "multiple inputs" in note
            for note in math["common_gotchas"]
        )

        analyze = operator_cards["analyzeCHOP"]
        assert analyze["docs_url"] == "https://docs.derivative.ca/Analyze_CHOP"
        analyze_params = {param["name"] for param in analyze["key_params"]}
        assert {
            "function",
            "allowstart",
            "allowend",
            "nopeakvalue",
            "valleys",
        }.union(chop_common_params).issubset(analyze_params)
        assert {
            "single-number result",
            "one sample long",
            "Average",
            "Maximum",
            "Minimum",
            "Sum",
            "RMS Power",
            "peak value",
            "peak index",
            "first sample is 0",
            "No Peak Value",
            "Analyze Valleys vs Peaks",
            "Math CHOP",
        }.union(chop_info_concepts).issubset(set(analyze.get("key_concepts", [])))
        assert any("one sample" in note and "collapse" in note for note in analyze["common_gotchas"])
        assert any("Peak Index" in note and "0" in note for note in analyze["common_gotchas"])
        assert any("No Peak Value" in note and "-1" in note for note in analyze["common_gotchas"])

        audio = operator_cards["audiofileinCHOP"]
        assert audio["docs_url"] == "https://docs.derivative.ca/Audio_File_In_CHOP"
        audio_params = {param["name"] for param in audio["key_params"]}
        assert {
            "file",
            "reloadpulse",
            "play",
            "playmode",
            "speed",
            "cue",
            "cuepulse",
            "cuepoint",
            "cuepointunit",
            "index",
            "indexunit",
            "timecodeop",
            "repeat",
            "trim",
            "trimstart",
            "trimstartunit",
            "trimend",
            "trimendunit",
            "prereadlength",
            "prereadlengthunit",
            "opentimeout",
            "mono",
            "volume",
        }.union(chop_common_params).issubset(audio_params)
        assert {
            "files on disk",
            "http:// addresses",
            "always outputs time sliced audio data",
            "Record CHOP",
            "Movie File Out TOP",
            "Audio Movie CHOP",
            "streams files from disk",
            "copies http locations to local disk first",
            "few seconds in memory",
            ".mp3",
            ".aif",
            ".aiff",
            ".au",
            ".wav",
            "Locked to Timeline",
            "Specify Index",
            "Sequential",
            "Timecode Object/CHOP/DAT",
            "Open Timeout",
        }.union(chop_info_concepts).issubset(set(audio.get("key_concepts", [])))
        assert any(
            "Locked to Timeline" in note and "Play" in note and "Speed" in note
            for note in audio["common_gotchas"]
        )
        assert any(
            "negative" in note and "Speed" in note and "backwards" in note for note in audio["common_gotchas"]
        )
        assert any("Open Timeout" in note and "silence" in note for note in audio["common_gotchas"])

        render_simple = operator_cards["rendersimpleTOP"]
        assert render_simple["docs_url"] == "https://docs.derivative.ca/Render_Simple_TOP"
        render_params = {param["name"] for param in render_simple["key_params"]}
        assert {
            "ortho",
            "fov",
            "orthowidth",
            "camdistance",
            "normalizegeo",
            "bgcolor",
            "bgcolorr",
            "bgcolorg",
            "bgcolorb",
            "bgcolora",
            "pop",
            "geotranslate",
            "georotate",
            "geoscale",
            "lighttranslate",
            "materialsource",
            "wireframe",
            "constant",
            "diffuse",
            "colormap",
            "mat",
        }.union(top_common_params).issubset(render_params)
        assert {
            "single POP",
            "basic transform",
            "single point light",
            "optional texture map",
            "internal Phong",
            "MAT node",
            "orthographic",
            "perspective",
            "camera along the Z-axis",
            "Normalize Geo",
            "box of size 2",
            "POP render/display flags are ignored",
            "Camera COMP",
            "Geometry COMP",
            "Light COMP",
            "Render TOP",
            "premultiplied background alpha",
        }.union(top_info_concepts).issubset(set(render_simple.get("key_concepts", [])))
        assert any(
            "POP" in note and "render/display flags" in note and "ignored" in note
            for note in render_simple["common_gotchas"]
        )
        assert any(
            "Background" in note and "premultiplied" in note and "alpha" in note
            for note in render_simple["common_gotchas"]
        )
        assert any("single POP" in note and "Render TOP" in note for note in render_simple["common_gotchas"])

        circle = operator_cards["circlePOP"]
        assert circle["docs_url"] == "https://docs.derivative.ca/Circle_POP"
        circle_params = {param["name"] for param in circle["key_params"]}
        assert {
            "connectivity",
            "orient",
            "modifybounds",
            "rad",
            "radx",
            "rady",
            "divs",
            "closed",
            "angle",
            "beginangle",
            "endangle",
            "anchoru",
            "anchorv",
            "t",
            "r",
            "scale",
            "normal",
            "normaldirection",
            "tangent",
            "tangentdirection",
            "texture",
        }.union(pop_common_params).issubset(circle_params)
        assert not {"radius", "divisions", "orientation"}.intersection(circle_params)
        assert {
            "circle",
            "ellipse",
            "arc",
            "Line Strip",
            "Surface",
            "Lines",
            "Point Primitives",
            "Closed",
            "texture coordinate attributes",
            "normal attributes",
            "tangent attributes",
            "XY plane",
            "YZ plane",
            "ZX plane",
            "input bounding box",
            "Modify Bounds",
        }.union(pop_runtime_concepts).issubset(set(circle.get("key_concepts", [])))
        assert any(
            "Closed" in note and "last" in note and "first" in note for note in circle["common_gotchas"]
        )
        assert any(
            "Modify Bounds" in note and "input" in note and "bounding box" in note
            for note in circle["common_gotchas"]
        )
        assert any(
            "normal" in note and "tangent" in note and "attribute" in note
            for note in circle["common_gotchas"]
        )

        noise_pop = operator_cards["noisePOP"]
        assert noise_pop["docs_url"] == "https://docs.derivative.ca/Noise_POP"
        noise_params = {param["name"] for param in noise_pop["key_params"]}
        assert {
            "noiselookupattrib",
            "type",
            "noisesize",
            "seed",
            "period",
            "harmon",
            "spread",
            "gain",
            "parsize",
            "amp",
            "exp",
            "offset",
            "attrclass",
            "group",
            "xord",
            "rord",
            "t",
            "r",
            "s",
            "p",
            "t4d",
            "noise",
            "noiseoutputattscope",
            "gradient",
            "gradientoutputattrscope",
            "curl3d",
            "curl3doutputattscope",
            "curl2d",
            "curl2doutputattscope",
            "combineop",
            "combineentity",
            "combineattrscope",
            "outputattrscope",
            "overrideautoattr",
            "attrtype",
            "attrnumcomps",
            "attrdefaultval",
            "computenormals",
            "mode",
            "map",
            "map0op",
            "map0element",
            "map0parm",
            "map0combineop",
        }.union(pop_common_params).issubset(noise_params)
        assert "amplitude" not in noise_params
        assert {
            "noise field",
            "P attribute",
            "Simplex",
            "Perlin",
            "2-4 dimensions",
            "Harmonics",
            "Transform page",
            "Noise attribute",
            "NoiseGradient",
            "NoiseCurl",
            "NoiseCurl2",
            "Combine Operation",
            "Combine Attribute Scope",
            "Translate 4D",
            "Map page",
            "Mapping POP Attributes to Parameters",
            "Parameter Size",
        }.union(pop_runtime_concepts).issubset(set(noise_pop.get("key_concepts", [])))
        assert any("By default" in note and "P attribute" in note for note in noise_pop["common_gotchas"])
        assert any("Translate" in note and "absTime.seconds" in note for note in noise_pop["common_gotchas"])
        assert any("Map page" in note and "per-point" in note for note in noise_pop["common_gotchas"])

        math_mix = operator_cards["mathmixPOP"]
        assert math_mix["docs_url"] == "https://docs.derivative.ca/Math_Mix_POP"
        mathmix_params = {param["name"] for param in math_mix["key_params"]}
        assert {
            "lengthmismatchnotif",
            "lengthmismatchaction",
            "group",
            "angleunit",
            "input",
            "input0pop",
            "attrclass",
            "vec",
            "vec0name",
            "vec0type",
            "vec0value",
            "premultcolor",
            "color",
            "color0name",
            "color0rgb",
            "color0alpha",
            "comb",
            "comb0oper",
            "comb0scopea",
            "comb0scopeb",
            "comb0scopec",
            "comb0result",
            "delattrs",
            "delnewattrs",
            "parmcolorspace",
        }.union(pop_common_params).issubset(mathmix_params)
        assert not {"scopea", "scopeb", "scopec", "resultscope"}.intersection(mathmix_params)
        assert {
            "series of math operations in one node",
            "simpler version of Math Combine POP",
            "Combine page",
            "Scope A",
            "Scope B",
            "Scope C",
            "Result Scope",
            "auto-named",
            "in1_",
            "single-point inputs",
            "length mismatch",
            "Angle Units",
            "Uniforms page",
            "temporary attributes",
            "middle-click pseudocode",
            "Info DAT",
            "raw GLSL code",
            "first input primitives and vertices",
        }.union(pop_runtime_concepts).issubset(set(math_mix.get("key_concepts", [])))
        assert any("auto-named" in note and "in1_" in note for note in math_mix["common_gotchas"])
        assert any("single-point" in note and "constant" in note for note in math_mix["common_gotchas"])
        assert any(
            "primitives and vertices" in note and "first input" in note for note in math_mix["common_gotchas"]
        )
        assert any("Info DAT" in note and "GLSL" in note for note in math_mix["common_gotchas"])

    def test_glsl_mat_card_covers_shader_attribute_sampler_deform_and_render_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslMAT"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_MAT"
        expected_params = {
            "glslversion",
            "predat",
            "vdat",
            "pdat",
            "gdat",
            "inherit",
            "lightingspace",
            "inprim",
            "outprim",
            "numout",
            "twocolor",
            "attr0name",
            "attr0type",
            "attr0size",
            "sampler0name",
            "sampler0top",
            "sampler0extendu",
            "sampler0extendv",
            "sampler0extendw",
            "sampler0filter",
            "sampler0anisotropy",
            "vec0name",
            "vec0value",
            "matrix0name",
            "matrix0value",
            "rel0name",
            "rel0from",
            "rel0to",
            "const0name",
            "const0value",
            "dodeform",
            "deformdata",
            "targetsop",
            "pcaptpath",
            "pcaptdata",
            "skelrootpath",
            "mat",
            "blending",
            "depthtest",
            "depthwriting",
            "alphatest",
            "alphathreshold",
            "wireframe",
            "cullface",
            "polygonoffset",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslMAT missing {sorted(expected_params - actual)}"
        assert {
            "TDAttrib_<attribName>()",
            "POP based workflows",
            "Sampler Page",
            "Texture Sampling Parameters",
            "Specialization Constants",
            "Deform Page",
            "pCaptPath",
            "pCaptData",
            "Blending",
            "Depth Test",
            "Alpha Test",
            "Wire Frame",
            "Cull Face",
            "Polygon Depth Offset",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any("checkerboard" in note and "compile" in note for note in card["common_gotchas"])
        assert any("Attributes page" in note and "TDAttrib_" in note for note in card["common_gotchas"])
        assert any(
            "sampler" in note and "sampler2D" in note and "sampler3D" in note
            for note in card["common_gotchas"]
        )
        assert any("pCaptPath" in note and "bone group" in note for note in card["common_gotchas"])
        assert any("Depth Test" in note and "Depth-Buffer" in note for note in card["common_gotchas"])

    def test_glsl_pop_card_covers_thread_output_attribute_uniform_and_collision_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslPOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_POP"
        expected_params = {
            "computedat",
            "attrclass",
            "numthreadsmode",
            "threadsinput",
            "numelems",
            "numelemspop",
            "numelemsclass",
            "numelemsattr",
            "workgroupsizex",
            "workgroupsizey",
            "workgroupsizez",
            "dispatchsizex",
            "dispatchsizey",
            "dispatchsizez",
            "outputattrs",
            "outputaccess",
            "initoutputattrs",
            "prevpassoutput",
            "npasses",
            "input0pops",
            "simplexnoise",
            "attr0name",
            "attr0customname",
            "attr0type",
            "attr0numcomps",
            "attr0isarray",
            "attr0arraysize",
            "attr0value",
            "matattr0name",
            "matattr0numrows",
            "matattr0numcols",
            "matattr0isarray",
            "matattr0arraysize",
            "matattr0qualifier",
            "premultcolor",
            "color0name",
            "color0rgb",
            "color0alpha",
            "vec0name",
            "vec0type",
            "vec0value",
            "sampler0name",
            "sampler0top",
            "sampler0extendu",
            "sampler0extendv",
            "sampler0extendw",
            "sampler0filter",
            "array0name",
            "array0type",
            "array0chop",
            "array0arraytype",
            "matrix0name",
            "matrix0value",
            "tempbuffer0name",
            "tempbuffer0initval",
            "const0name",
            "const0value",
            "asname",
            "colpop",
            "buildflag",
            "opaquecolgeo",
            "freeextragpumem",
            "delinputattrs",
            "parmcolorspace",
            "parmreferencewhite",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslPOP missing {sorted(expected_params - actual)}"
        assert {
            "TDIndex()",
            "TDNumElements()",
            "TDInputNumElements()",
            "TDInputPointIndex()",
            "TDIn_AttribName()",
            "TDInPoint_AttribName()",
            "TDInCache_AttribName()",
            "Output Attributes",
            "Initialize Output Attributes",
            "Read-Write output access",
            "writeonly SSBO",
            "atomic operations",
            "multi-pass GLSL POP",
            "Create Attributes Page",
            "Matrix Attribute",
            "Texture Buffer arrays",
            "Temp Buffers",
            "Specialization Constants",
            "collision acceleration structure",
            "Delete Input Attributes",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any(
            "Manual" in note and "TDIndex" in note and "compile" in note for note in card["common_gotchas"]
        )
        assert any("Output Attributes" in note and "P[id]" in note for note in card["common_gotchas"])
        assert any("uninitialized" in note and "crashes" in note for note in card["common_gotchas"])
        assert any("Read-Write" in note and "atomic" in note for note in card["common_gotchas"])

    def test_glsl_advanced_pop_card_covers_output_topology_and_extra_output_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glsladvancedPOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_Advanced_POP"
        expected_params = {
            "computedat",
            "shaderdispatchmode",
            "numelems",
            "numelemspop",
            "numelemsclass",
            "numelemsattr",
            "workgroupsizex",
            "workgroupsizey",
            "workgroupsizez",
            "dispatchsizex",
            "dispatchsizey",
            "dispatchsizez",
            "numthreadsbatchmode",
            "ptoutputattrs",
            "primoutputattrs",
            "vertoutputattrs",
            "outputaccess",
            "initoutputattrs",
            "prevpassoutput",
            "npasses",
            "input0pops",
            "simplexnoise",
            "numthreadsmode",
            "render",
            "maxpointsmode",
            "maxpoints",
            "pointcountinfo",
            "pointcountmode",
            "pointcountpop",
            "pointcountclass",
            "pointcountattr",
            "maxtrianglesmode",
            "maxtriangles",
            "maxquadsmode",
            "maxquads",
            "maxlinestripsmode",
            "maxlinestrips",
            "maxlsvertsmode",
            "maxlsverts",
            "maxlinesmode",
            "maxlines",
            "maxpointprimsmode",
            "maxpointprims",
            "lsinfoupdate",
            "lsinfopop",
            "lsinfoclass",
            "lsinfoattr",
            "lsindexpop",
            "lsindexclass",
            "lsindexattr",
            "lsmaxvertsoverride",
            "lsmaxverts",
            "initoutputprims",
            "topoinfo",
            "topoinfopop",
            "topoinfoclass",
            "trianglecountmode",
            "trianglecountattr",
            "quadcountmode",
            "quadcountattr",
            "linestripcountmode",
            "linestripcountattr",
            "lsvertcountmode",
            "lsvertcountattr",
            "linecountmode",
            "linecountattr",
            "pointprimcountmode",
            "pointprimcountattr",
            "extraout0name",
            "extraout0pop",
            "extraout0ptattrs",
            "extraout0primattrs",
            "extraout0vertattrs",
            "extraout0outputaccess",
            "extraout0prevpassoutput",
            "extraout0copyinputattrs",
            "attr0class",
            "attr0name",
            "attr0customname",
            "attr0type",
            "attr0numcomps",
            "attr0isarray",
            "attr0arraysize",
            "attr0value",
            "matattr0class",
            "matattr0name",
            "matattr0numrows",
            "matattr0numcols",
            "matattr0isarray",
            "matattr0arraysize",
            "matattr0qualifier",
            "premultcolor",
            "color0name",
            "color0rgb",
            "color0alpha",
            "vec0name",
            "vec0type",
            "vec0value",
            "sampler0name",
            "sampler0top",
            "sampler0extendu",
            "sampler0extendv",
            "sampler0extendw",
            "sampler0filter",
            "array0name",
            "array0type",
            "array0chop",
            "array0arraytype",
            "matrix0name",
            "matrix0value",
            "tempbuffer0name",
            "tempbuffer0initval",
            "const0name",
            "const0value",
            "freeextragpumem",
            "delinputattrs",
            "parmcolorspace",
            "parmreferencewhite",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glsladvancedPOP missing {sorted(expected_params - actual)}"
        assert {
            "Single Shader Dispatch",
            "Per Primitive Batch",
            "point output attributes",
            "primitive output attributes",
            "vertex output attributes",
            "Max Points",
            "Topology Info",
            "Line Strip Info",
            "Initialize Output Primitives",
            "Extra Outputs",
            "GLSL Select POP",
            "oTDPoint_AttribName[]",
            "oTDPrim_AttribName[]",
            "oTDVert_AttribName[]",
            "I[] index buffer",
            "output counts",
            "TDInputNumVertsPerPrim()",
            "TDInputPrimType()",
            "TDInputPrimVertsStartIndex()",
            "TDPrimsStartIndex()",
            "TDNumPrimsBatch()",
            "TDNumVertsBatch()",
            "Create Attribs Page",
            "Texture Buffer arrays",
            "Specialization Constants",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any("output counts" in note and "Max" in note for note in card["common_gotchas"])
        assert any("I[]" in note and "Max Primitives" in note for note in card["common_gotchas"])
        assert any("Extra Outputs" in note and "GLSL Select" in note for note in card["common_gotchas"])
        assert any("Per Primitive Batch" in note and "batch" in note for note in card["common_gotchas"])

    def test_glsl_copy_pop_card_covers_template_stage_uniform_and_pop_buffer_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslcopyPOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_Copy_POP"
        expected_params = {
            "ncy",
            "ptcomputedat",
            "ptoutputattrs",
            "vertcomputemethod",
            "vertcomputedat",
            "vertoutputattrs",
            "primcomputemethod",
            "primcomputedat",
            "primoutputattrs",
            "dimension",
            "simplexnoise",
            "attr0class",
            "attr0name",
            "attr0customname",
            "attr0type",
            "attr0numcomps",
            "attr0isarray",
            "attr0arraysize",
            "matattr0class",
            "matattr0name",
            "matattr0numrows",
            "matattr0numcols",
            "matattr0isarray",
            "matattr0arraysize",
            "matattr0qualifier",
            "premultcolor",
            "color0name",
            "color0rgb",
            "color0alpha",
            "vec0name",
            "vec0type",
            "vec0value",
            "sampler0name",
            "sampler0top",
            "sampler0extendu",
            "sampler0extendv",
            "sampler0extendw",
            "sampler0filter",
            "array0name",
            "array0type",
            "array0chop",
            "array0arraytype",
            "matrix0name",
            "matrix0value",
            "tempbuffer0name",
            "tempbuffer0initval",
            "const0name",
            "const0value",
            "buffer0pop",
            "buffer0attrclass",
            "buffer0attr",
            "buffer0name",
            "freeextragpumem",
            "delinputattrs",
            "parmcolorspace",
            "parmreferencewhite",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslcopyPOP missing {sorted(expected_params - actual)}"
        assert {
            "template input",
            "Number of Copies",
            "point compute shader required",
            "optional vertex shader",
            "optional primitive shader",
            "Append Dimension",
            "Output Attributes",
            "TDNumPoints()",
            "TDInputNumPoints()",
            "TDNumVertsBatch()",
            "TDInputNumVertsBatch()",
            "TDVertIndex()",
            "TDNumPrimsBatch()",
            "TDPrimIndex()",
            "TDInputIndex()",
            "TDCopyIndex()",
            "TDTemplateNumPoints()",
            "TDIn_AttribName()",
            "TDTemplate_AttribName()",
            "cTDTemplateArraySize_Attrib",
            "TDBuffer()",
            "AttribName[]",
            "TDUpdatePointGroups()",
            "TDUpdateTopology()",
            "TDUpdateLineStripsInfo()",
            "TDUpdatePrimGroups()",
            "cTDPrimIndexRestart",
            "POP Buffers",
            "Texture Buffer arrays",
            "Specialization Constants",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert any("point compute shader" in note and "required" in note for note in card["common_gotchas"])
        assert any("template input" in note and "Number of Copies" in note for note in card["common_gotchas"])
        assert any("TDUpdateTopology" in note and "vertex" in note for note in card["common_gotchas"])
        assert any("TDBuffer" in note and "other POP" in note for note in card["common_gotchas"])

    def test_glsl_select_pop_card_covers_extra_output_selection_controls(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["glslselectPOP"]
        assert card["docs_url"] == "https://docs.derivative.ca/GLSL_Select_POP"
        expected_params = {
            "pop",
            "name",
            "bypass",
            "freeextragpumem",
            "delinputattrs",
        }
        actual = {param["name"] for param in card["key_params"]}
        assert expected_params.issubset(actual), f"glslselectPOP missing {sorted(expected_params - actual)}"
        assert {
            "GLSL Advanced POP",
            "Extra Outputs",
            "extra output POP",
            "Output Name",
            "named extra output",
            "branchable outputs",
            "extraout0name",
            "extraout0pop",
            "extraout0ptattrs",
            "extraout0primattrs",
            "extraout0vertattrs",
            "GLSL Select POP",
            "Delete Input Attributes",
            "Free Extra GPU Memory",
            "Info CHOP",
        }.issubset(set(card["key_concepts"]))
        assert {"GLSL_snippets", "POP_snippets", "POP_attribute_ontology"}.issubset(
            set(card["related_snippets"])
        )
        assert any("Output Name" in note and "Extra Output" in note for note in card["common_gotchas"])
        assert any("does not create" in note and "selects" in note for note in card["common_gotchas"])
        assert any(
            "Delete Input Attributes" in note and "selected output" in note for note in card["common_gotchas"]
        )

    def test_execute_and_parameter_dat_cards_use_atomic_parameter_names(self) -> None:
        expected_params = {
            "chopexecuteDAT": {
                "active",
                "executeloc",
                "fromop",
                "chop",
                "channel",
                "offtoon",
                "whileon",
                "ontooff",
                "whileoff",
                "valuechange",
                "freq",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
            },
            "panelexecuteDAT": {
                "active",
                "executeloc",
                "fromop",
                "panels",
                "panelvalue",
                "offtoon",
                "whileon",
                "ontooff",
                "whileoff",
                "valuechange",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
            },
            "opexecuteDAT": {
                "active",
                "executeloc",
                "fromop",
                "op",
                "precook",
                "postcook",
                "opdelete",
                "flagchange",
                "wirechange",
                "namechange",
                "pathchange",
                "uichange",
                "numchildrenchange",
                "childrename",
                "currentchildchange",
                "extensionchange",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
            },
            "parameterDAT": {
                "ops",
                "parameters",
                "includeopname",
                "renamefrom",
                "renameto",
                "custom",
                "builtin",
                "header",
                "name",
                "value",
                "eval",
                "constant",
                "expression",
                "export",
                "mode",
                "style",
                "tupletname",
                "size",
                "path",
                "menuindex",
                "minmax",
                "clampminmax",
                "normminmax",
                "default",
                "enabled",
                "readonly",
                "section",
                "menunames",
                "menulabels",
            },
            "parameterexecuteDAT": {
                "active",
                "executeloc",
                "fromop",
                "op",
                "pars",
                "valuechange",
                "valueschanged",
                "onpulse",
                "expressionchange",
                "exportchange",
                "enablechange",
                "modechange",
                "custom",
                "builtin",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
            },
            "pargroupexecuteDAT": {
                "active",
                "op",
                "pars",
                "callbackmode",
                "valuechange",
                "onpulse",
                "expressionchange",
                "exportchange",
                "enablechange",
                "modechange",
                "custom",
                "builtin",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_dat_event_and_io_cards_use_atomic_parameter_names(self) -> None:
        expected_params = {
            "audiodevicesDAT": {
                "driver",
                "alldrivers",
                "input",
                "output",
                "callbacks",
                "language",
                "extension",
                "customext",
            },
            "clipDAT": {
                "edit",
                "file",
                "reload",
                "executeloc",
                "component",
                "clip",
                "framefirst",
                "frameloop",
                "exit",
                "printstate",
                "language",
                "extension",
                "customext",
            },
            "executeDAT": {
                "active",
                "executeloc",
                "fromop",
                "start",
                "create",
                "exit",
                "framestart",
                "frameend",
                "playstatechange",
                "devicechange",
                "edit",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
                "language",
                "extension",
                "customext",
            },
            "datexecuteDAT": {
                "active",
                "dat",
                "tablechange",
                "rowchange",
                "colchange",
                "cellchange",
                "sizechange",
                "execute",
                "executeloc",
                "fromop",
                "edit",
                "file",
                "syncfile",
                "loadonstart",
                "loadonstartpulse",
                "write",
                "writepulse",
                "language",
                "extension",
                "customext",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_dat_diagnostics_and_search_cards_use_atomic_parameter_names(self) -> None:
        expected_params = {
            "errorDAT": {
                "active",
                "severity",
                "type",
                "source",
                "message",
                "logcurrent",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
            },
            "folderDAT": {
                "active",
                "rootfolder",
                "refresh",
                "refreshpulse",
                "async",
                "nameformat",
                "dateformat",
                "type",
                "folders",
                "names",
                "allextensions",
                "imageextensions",
                "movieextensions",
                "audioextensions",
                "extensions",
                "subfolders",
                "mindepth",
                "limitdepth",
                "maxdepth",
                "namecol",
                "basenamecol",
                "extensioncol",
                "typecol",
                "sizecol",
                "depthcol",
                "foldercol",
                "pathcol",
                "relpathcol",
                "datecreatedcol",
                "datemodifiedcol",
                "dateaccessedcol",
            },
            "opfindDAT": {
                "activecook",
                "cookpulse",
                "component",
                "includecomponent",
                "includewired",
                "mindepth",
                "limitmaxdepth",
                "maxdepth",
                "limitmaxops",
                "maxops",
                "objects",
                "panels",
                "other",
                "tops",
                "chops",
                "sops",
                "mats",
                "dats",
                "casesensitive",
                "combinefilters",
                "callbacks",
            },
            "performDAT": {
                "active",
                "activepulse",
                "triggermode",
                "triggerthreshold",
                "logcook",
                "logexport",
                "logviewport",
                "logmovie",
                "logdrawchannels",
                "logobjectview",
                "logcustompanel",
                "logmidi",
                "loggraphics",
                "logframelength",
                "logmisc",
                "logscript",
                "logrender",
                "callbacks",
                "clear",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_protocol_dat_cards_use_atomic_parameter_names(self) -> None:
        expected_params = {
            "mqttclientDAT": {
                "active",
                "netaddress",
                "specifyid",
                "usercid",
                "keepalive",
                "maxinflight",
                "cleansession",
                "verifycert",
                "username",
                "password",
                "reconnect",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "serialDAT": {
                "active",
                "format",
                "port",
                "baudrate",
                "databits",
                "parity",
                "stopbits",
                "dtr",
                "rts",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "midiinDAT": {
                "active",
                "device",
                "id",
                "value14",
                "skipsense",
                "skiptiming",
                "filter",
                "message",
                "channel",
                "index",
                "value",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "midieventDAT": {
                "active",
                "skipsense",
                "skiptiming",
                "filter",
                "message",
                "channel",
                "index",
                "value",
                "dir",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "oscinDAT": {
                "active",
                "protocol",
                "address",
                "port",
                "localaddress",
                "shared",
                "addscope",
                "typetag",
                "splitbundle",
                "splitmessage",
                "bundletimestamp",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "oscoutDAT": {
                "active",
                "protocol",
                "address",
                "port",
                "localaddress",
                "shared",
                "addscope",
                "typetag",
                "splitbundle",
                "splitmessage",
                "bundletimestamp",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_network_dat_cards_use_atomic_received_message_parameter_names(self) -> None:
        expected_params = {
            "tcp/ipDAT": {
                "mode",
                "address",
                "port",
                "shared",
                "format",
                "active",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "socketioDAT": {
                "active",
                "reset",
                "url",
                "verifycert",
                "delay",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "bytes",
            },
            "fifoDAT": {
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
                "firstrow",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_common_dat_cards_use_atomic_editor_and_reload_parameter_names(self) -> None:
        expected_params = {
            "art-netDAT": {
                "callbacks",
                "columns",
                "poll",
                "language",
                "extension",
                "customext",
                "wordwrap",
            },
            "etherdreamDAT": {
                "callbacks",
                "columns",
                "poll",
                "language",
                "extension",
                "customext",
                "wordwrap",
            },
            "nullDAT": {
                "language",
                "extension",
                "customext",
                "wordwrap",
            },
            "outDAT": {
                "label",
                "language",
                "extension",
                "customext",
            },
            "scriptDAT": {
                "callbacks",
                "setuppars",
                "language",
                "extension",
                "customext",
            },
            "cplusplusDAT": {
                "plugin",
                "reinit",
                "reinitpulse",
                "unloadplugin",
                "language",
                "extension",
                "customext",
                "wordwrap",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_table_transform_dat_cards_use_atomic_scope_filter_parameter_names(self) -> None:
        expected_params = {
            "dmxmapDAT": {
                "active",
                "updateval",
                "updatevalpulse",
                "dmxpop",
                "netfilter",
                "subnetfilter",
                "universefilter",
                "netaddressfilter",
                "excludeunused",
            },
            "evaluateDAT": {
                "dat",
                "datexpr",
                "output",
                "expr",
                "outputsize",
                "dependency",
                "xfirstrow",
                "xfirstcol",
                "extractrows",
                "extractcols",
            },
            "examineDAT": {
                "op",
                "source",
                "subkey",
                "expression",
                "level",
                "key",
                "type",
                "value",
                "expandclasses",
                "maxlevels",
            },
            "insertDAT": {
                "insert",
                "at",
                "index",
                "contents",
                "includenames",
                "replaceduplicate",
                "replace",
            },
            "mpcdiDAT": {
                "file",
                "reloadpulse",
                "outputby",
                "bufferid",
                "regionid",
                "near",
                "far",
            },
            "multitouchinDAT": {
                "active",
                "outputtype",
                "panel",
                "relativeid",
                "relativepos",
                "occlusion",
                "occbydepth",
                "occdepthlayer",
                "mouse",
                "callbacks",
                "executeloc",
                "fromop",
                "clamp",
                "maxlines",
                "clear",
            },
            "reorderDAT": {
                "reorder",
                "method",
                "before",
                "after",
                "order",
                "delete",
            },
            "sortDAT": {
                "sortmethod",
                "name",
                "index",
                "order",
                "seed",
                "ignorecase",
                "preservefirst",
                "unique",
                "reverse",
            },
            "substituteDAT": {
                "before",
                "after",
                "match",
                "case",
                "expand",
                "expandto",
                "first",
                "xfirstrow",
                "xfirstcol",
                "extractrows",
                "extractcols",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_table_dat_uses_atomic_load_and_fill_parameter_names(self) -> None:
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        card = operator_cards["tableDAT"]
        actual = {param["name"] for param in card["key_params"]}
        combined = sorted(name for name in actual if "/" in name or " " in name)
        expected = {
            "edit",
            "file",
            "syncfile",
            "defaultreadencoding",
            "loadonstart",
            "write",
            "removeblank",
            "fill",
            "rows",
            "cols",
            "cellexpr",
        }
        assert not combined, f"tableDAT has combined key_params: {combined}"
        assert expected.issubset(actual), f"tableDAT missing {sorted(expected - actual)}"

    def test_sop_cards_use_atomic_grouped_parameter_names(self) -> None:
        expected_params = {
            "limitSOP": {
                "chanx",
                "chany",
                "chanz",
                "chanrx",
                "chanry",
                "chanrz",
                "chanr",
                "chang",
                "chanb",
                "chanalpha",
            },
            "lsystemSOP": {"stampa", "stampb", "stampc"},
            "magnetSOP": {"position", "color", "nml", "velocity"},
            "metaballSOP": {"expxy", "expz"},
            "pointSOP": {"normalf", "edgef", "radialf"},
            "polyloftSOP": {"closeu", "closev"},
            "polypatchSOP": {
                "closeu",
                "closev",
                "firstuclamp",
                "lastuclamp",
                "firstvclamp",
                "lastvclamp",
            },
            "primitiveSOP": {
                "xord",
                "rord",
                "t",
                "r",
                "s",
                "closeu",
                "closev",
                "vtxsort",
                "vtxuoff",
                "vtxvoff",
            },
            "profileSOP": {"keepsurf", "delprof", "urange", "vrange"},
            "projectSOP": {"axis", "vector", "rtolerance", "ftolerance"},
            "railsSOP": {"usevtx", "vertex", "noflip", "usedir", "dir"},
            "raySOP": {"newgrp", "hitgrp"},
            "rectangleSOP": {"texture", "normals"},
            "refineSOP": {
                "firstu",
                "secondu",
                "domainu1",
                "domainu2",
                "firstv",
                "secondv",
                "domainv1",
                "domainv2",
                "refineu",
                "refinev",
                "unrefineu",
                "unrefinev",
                "tolu",
                "tolv",
            },
            "resampleSOP": {"dolength", "length", "dosegs", "segs"},
            "skinSOP": {"force", "orderv"},
            "sortSOP": {"partreverse", "partoffset"},
            "springSOP": {
                "external",
                "wind",
                "turb",
                "period",
                "seed",
                "limitpos",
                "limitneg",
                "hit",
                "gaintan",
                "gainnorm",
            },
            "stitchSOP": {"dostitch", "dotangent", "sharp"},
            "subdivideSOP": {"outputcrease", "outcreasegroup"},
            "superquadSOP": {"rows", "cols", "expxy", "expz", "texture", "normals"},
            "surfsectSOP": {
                "tol3d",
                "tol2d",
                "insidea",
                "insideb",
                "outsidea",
                "outsideb",
                "creategroupa",
                "creategroupb",
            },
            "sweepSOP": {
                "xgrp",
                "pathgrp",
                "refgrp",
                "angle",
                "noflip",
                "usevtx",
                "vertex",
                "scale",
                "twist",
                "roll",
            },
            "textSOP": {
                "font",
                "fontfile",
                "fontsizex",
                "fontsizey",
                "keepfontratio",
                "language",
                "readingdirection",
                "kerning",
                "linespacing",
                "wordwrap",
                "wordwrapsize",
            },
            "torusSOP": {
                "rows",
                "cols",
                "angleu",
                "anglev",
                "closeu",
                "closev",
                "capu",
                "capv",
            },
            "traceSOP": {
                "delborder",
                "bordwidth",
                "doresample",
                "step",
                "dosmooth",
                "corner",
                "fitcurve",
                "error",
                "convpoly",
                "lod",
                "hole",
            },
            "trailSOP": {"surftype", "close", "reset", "resetpulse"},
            "tubeSOP": {
                "orientbounds",
                "modifybounds",
                "rows",
                "cols",
                "cap",
                "texture",
                "normals",
            },
            "twistSOP": {"paxis", "saxis"},
            "vertexSOP": {
                "doclr",
                "diff",
                "alpha",
                "douvw",
                "map",
                "docrease",
                "crease",
            },
            "zedSOP": {
                "reset",
                "resetpulse",
                "normals",
                "texture",
                "filter",
                "consolidatepts",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_viewer_and_window_cards_use_atomic_parameter_names(self) -> None:
        expected_params = {
            "windowCOMP": {
                "winop",
                "title",
                "justifyoffsetto",
                "ignoretaskbar",
                "display",
                "justifyh",
                "justifyv",
                "winoffsetx",
                "winoffsety",
                "single",
                "dpiscaling",
                "size",
                "winw",
                "winh",
                "update",
                "borders",
                "bordersinsize",
                "alwaysontop",
                "cursorvisible",
                "constraincursor",
                "cursordisplay",
                "interact",
                "allowminimize",
                "windowpixelformat",
                "vsyncmode",
                "drawwindow",
                "hwframelock",
                "performance",
                "winopen",
                "winclose",
                "setperform",
                "opendialog",
                "includedialog",
                "blocksleep",
                "closeescape",
            },
            "opviewerTOP": {
                "opviewer",
                "allowpanel",
                "preservealpha",
                "outputresolution",
                "resolutionw",
                "resolutionh",
                "resmenu",
                "resmult",
                "outputaspect",
                "aspect1",
                "aspect2",
                "armenu",
                "inputfiltertype",
                "fillmode",
                "filtertype",
            },
        }

        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type, expected in expected_params.items():
            card = operator_cards[op_type]
            actual = {param["name"] for param in card["key_params"]}
            combined = sorted(name for name in actual if "/" in name or " " in name)
            assert not combined, f"{op_type} has combined key_params: {combined}"
            assert expected.issubset(actual), f"{op_type} missing {sorted(expected - actual)}"

    def test_glsl_adjacent_operator_cards_reference_existing_glsl_snippet_card(self) -> None:
        snippet_ids = {card["snippet_id"] for _, card in _load_all_json("snippets")}
        operator_cards = {card["op_type"]: card for _, card in _load_all_json("operators")}

        for op_type in ("glslmultiTOP", "textDAT"):
            related = operator_cards[op_type]["related_snippets"]
            assert "glsl_shader" not in related, op_type
            assert "GLSL_snippets" in related, op_type
            assert set(related).issubset(snippet_ids), op_type


class TestPaletteCards:
    """Palette cards must have required fields."""

    @pytest.fixture(scope="class")
    def palettes(self) -> list[tuple[Path, dict]]:
        return _load_all_json("palette")

    def test_required_fields(self, palettes: list[tuple[Path, dict]]) -> None:
        for path, card in palettes:
            for field in REQUIRED_FIELDS["palette"]:
                assert field in card, f"{path.name} missing required field '{field}'"


class TestReleaseCards:
    """Release cards must exist and have required fields."""

    def test_release_2025_32460_exists(self) -> None:
        path = CARDS_DIR / "release" / "2025.32460.json"
        assert path.exists(), "Release card 2025.32460.json not found"

    def test_required_fields(self) -> None:
        path = CARDS_DIR / "release" / "2025.32460.json"
        card = json.loads(path.read_text(encoding="utf-8"))
        for field in REQUIRED_FIELDS["release"]:
            assert field in card, f"Release card missing required field '{field}'"


class TestSnippetCards:
    """Snippet cards must have required fields."""

    @pytest.fixture(scope="class")
    def snippets(self) -> list[tuple[Path, dict]]:
        return _load_all_json("snippets")

    def test_required_fields(self, snippets: list[tuple[Path, dict]]) -> None:
        for path, card in snippets:
            for field in REQUIRED_FIELDS["snippet"]:
                assert field in card, f"{path.name} missing required field '{field}'"

    def test_glsl_shader_template_snippets_cover_td_idioms(self) -> None:
        path = CARDS_DIR / "snippets" / "GLSL_snippets.json"

        assert path.exists(), "GLSL_snippets.json is required for shader template guidance"
        card = json.loads(path.read_text(encoding="utf-8"))

        templates = {template["id"]: template for template in card.get("templates", [])}
        expected = {
            "glsl_top_pixel_template",
            "glsl_top_compute_output_template",
            "glsl_top_nonuniform_sampler_template",
            "glsl_top_multi_buffer_vertex_template",
            "glsl_mat_basic_template",
            "glsl_mat_world_space_lighting_template",
            "glsl_mat_instance_texture_picking_template",
            "glsl_pop_attribute_template",
            "glsl_advanced_pop_template",
        }

        assert expected.issubset(templates)
        assert card["source_docs"]
        assert all(url.startswith("https://docs.derivative.ca/") for url in card["source_docs"])

        top_code = templates["glsl_top_pixel_template"]["code"]
        top_compute_code = templates["glsl_top_compute_output_template"]["code"]
        top_sampler_code = templates["glsl_top_nonuniform_sampler_template"]["code"]
        top_multi_buffer_code = templates["glsl_top_multi_buffer_vertex_template"]["code"]
        mat_code = templates["glsl_mat_basic_template"]["code"]
        mat_lighting_code = templates["glsl_mat_world_space_lighting_template"]["code"]
        mat_instance_code = templates["glsl_mat_instance_texture_picking_template"]["code"]
        pop_code = templates["glsl_pop_attribute_template"]["code"]
        advanced_code = templates["glsl_advanced_pop_template"]["code"]

        assert "TDOutputSwizzle" in top_code
        assert "layout(location = 0) out vec4" in top_code
        assert "gl_GlobalInvocationID" in top_compute_code
        assert "uTDOutputInfo.res.zw" in top_compute_code
        assert "TDImageLoadOutput" in top_compute_code
        assert "TDImageStoreOutput" in top_compute_code
        assert "TDOutputSwizzle" not in top_compute_code
        assert "TD_NUM_2D_INPUTS" in top_sampler_code
        assert "nonuniformEXT" in top_sampler_code
        assert "uTD2DInfos" in top_sampler_code
        assert "textureOffset" in top_sampler_code
        assert "layout(location = 1) out vec4" in top_multi_buffer_code
        assert "TDDither" in top_multi_buffer_code
        assert "TDSOPToProj" in top_multi_buffer_code
        assert "uv[0]" in top_multi_buffer_code
        assert "TDWorldToProj" in mat_code
        assert "TDDeform(TDPos())" in mat_code
        assert "TDAttrib_" in mat_code
        assert "TDOutputSwizzle" in mat_code
        assert "TDDeformNorm(TDNormal())" in mat_lighting_code
        assert "TDLightingPBR" in mat_lighting_code
        assert "TDCheckOrderIndTrans()" in mat_lighting_code
        assert "TDFog" in mat_lighting_code
        assert "TDDither" in mat_lighting_code
        assert "layout(constant_id = 0)" in mat_lighting_code
        assert "flat out int vInstanceID" in mat_instance_code
        assert "flat out uint vInstanceTexIndex" in mat_instance_code
        assert "TDInstanceTextureIndex()" in mat_instance_code
        assert "TDInstanceTexture(" in mat_instance_code
        assert "TD_PICKING_ACTIVE" in mat_instance_code
        assert "TDWritePickingValues()" in mat_instance_code
        for code in (pop_code, advanced_code):
            assert "TDIndex()" in code
            assert "TDNumElements()" in code
            assert "if (id >= TDNumElements())" in code
        assert "TDIn_P" in pop_code
        assert "P[id]" in pop_code
        assert "TDInPoint_P" in advanced_code
        assert "oTDPoint_P" in advanced_code

        for op_type in ("glslTOP", "glslMAT", "glslPOP", "glsladvancedPOP"):
            operator_path = CARDS_DIR / "operators" / f"{op_type}.json"
            operator_card = json.loads(operator_path.read_text(encoding="utf-8"))
            assert "GLSL_snippets" in operator_card["related_snippets"], op_type

    def test_pop_attribute_ontology_covers_particle_group_dimension_and_array_idioms(self) -> None:
        path = CARDS_DIR / "snippets" / "POP_attribute_ontology.json"

        assert path.exists(), "POP_attribute_ontology.json is required for POP attribute guidance"
        card = json.loads(path.read_text(encoding="utf-8"))

        assert card["card_type"] == "snippet"
        assert card["snippet_id"] == "POP_attribute_ontology"
        assert card["family"] == "POP"
        assert card["source_docs"]
        assert all(url.startswith("https://docs.derivative.ca/") for url in card["source_docs"])

        classes = {item["name"]: item for item in card["attribute_classes"]}
        assert {"point", "primitive", "vertex"}.issubset(classes)

        attrs = card["attributes"]
        required_attrs = {
            "P",
            "N",
            "Color",
            "Tex",
            "PartVel",
            "PartForce",
            "PartMass",
            "PartDrag",
            "PartLife",
            "PartLifeSpan",
            "PartId",
            "PartDeath",
        }
        assert required_attrs.issubset(attrs)

        assert attrs["P"]["class"] == "point"
        assert attrs["P"]["type"] == "float3"
        assert "position" in attrs["P"]["role"].lower()
        assert "TDIn_P" in attrs["P"]["glsl_read"]
        assert "P[id]" in attrs["P"]["glsl_write"]
        assert {"x", "y", "z"}.issubset(set(attrs["P"]["components"]))
        assert "P.xy" in attrs["P"]["swizzle_examples"]

        assert attrs["Color"]["type"] == "float4"
        assert "Color.rgb" in attrs["Color"]["swizzle_examples"]
        assert "Color.a" in attrs["Color"]["swizzle_examples"]
        assert attrs["Tex"]["type"] == "float3"
        assert attrs["PartVel"]["type"] == "vec3"
        assert attrs["PartForce"]["type"] == "vec3"
        assert attrs["PartMass"]["type"] == "float"
        assert attrs["PartDrag"]["type"] == "float"
        assert attrs["PartLifeSpan"]["canonical_attribute"] == "PartLife"
        assert "Particle POP" in attrs["PartLifeSpan"]["source_context"]
        assert attrs["PartId"]["type"] == "uint"
        assert "Attribute page" in attrs["PartId"]["doc_conflict"]
        assert attrs["PartDeath"]["optional"] is True

        access_patterns = card["glsl_access_patterns"]
        for token in (
            "TDIndex()",
            "TDNumElements()",
            "TDInPoint_",
            "TDInPrim_",
            "TDInVert_",
            "TDUpdatePointGroups()",
            "TDUpdatePrimGroups()",
        ):
            assert token in access_patterns

        dimensions = card["dimensions"]
        for token in (
            "cTDDimSize",
            "TDDimension()",
            "TDDimCoords(uint pointIndex)",
            "TDDimPointIndex(coords)",
        ):
            assert token in dimensions["helpers"]

        arrays = card["array_attributes"]
        assert "MyArrayAttribute[3]" in arrays["naming_examples"]
        assert "arrayIndex" in arrays["glsl_input_access"]
        assert "cTDArraySize_" in arrays["glsl_array_size_constant"]

        groups = card["groups"]
        assert {"point", "primitive"}.issubset(set(groups["entity_classes"]))
        assert {"attribute", "thin", "pattern", "group", "bounding"}.issubset(
            set(groups["selection_methods"])
        )
        assert "Group parameter" in groups["downstream_scope"]

        assert card["attribute_precedence"] == ["vertex", "point", "primitive"]
        assert {"P(0)", "P.y", "P.i2", "Color.a"}.issubset(set(card["component_syntax"]))
        mat_access = card["glsl_mat_pop_access"]
        for token in ("TDAttrib_AttribName()", "TDBuffer_AttribName(elementIndex, arrayIndex)"):
            assert token in mat_access

    def test_op_snippets_metadata_covers_pop_and_glsl_examples(self) -> None:
        pop_path = CARDS_DIR / "snippets" / "POP_snippets.json"
        glsl_path = CARDS_DIR / "snippets" / "GLSL_snippets.json"

        pop_card = json.loads(pop_path.read_text(encoding="utf-8"))
        glsl_card = json.loads(glsl_path.read_text(encoding="utf-8"))

        for card in (pop_card, glsl_card):
            examples = card.get("official_examples")
            assert isinstance(examples, list) and examples, card["snippet_id"]
            for example in examples:
                assert example["example_id"].strip()
                assert example["display_name"].strip()
                assert example["family"] in {"POP", "TOP", "MAT", "GLSL"}
                assert example["source_url"].startswith("https://docs.derivative.ca/")
                assert "Help > Operator Snippets" in example["access_path"]
                assert isinstance(example["operators"], list) and example["operators"]
                assert isinstance(example["topics"], list) and example["topics"]
                assert example["source_context"].strip()

        pop_ids = {example["example_id"] for example in pop_card["official_examples"]}
        glsl_ids = {example["example_id"] for example in glsl_card["official_examples"]}

        assert {
            "op_snippets_pop_concepts",
            "pop_concepts_array_attributes_math",
            "op_snippets_particle_pop_feedback",
            "op_snippets_force_radial_pop",
        }.issubset(pop_ids)
        assert {
            "op_snippets_glsl_pop_attribute_compute",
            "op_snippets_glsl_advanced_pop_compute",
        }.issubset(glsl_ids)


class TestArticleCards:
    """Article cards cover official learning pages that are not createable operators."""

    @pytest.fixture(scope="class")
    def articles(self) -> list[tuple[Path, dict]]:
        return _load_all_json("articles")

    def test_required_fields(self, articles: list[tuple[Path, dict]]) -> None:
        assert articles, "Expected at least one article card"
        for path, card in articles:
            for field in REQUIRED_FIELDS["article"]:
                assert field in card, f"{path.name} missing required field '{field}'"
            assert card["card_type"] == "article"
            assert card["source_url"].startswith("https://docs.derivative.ca/")

    def test_glsl_and_pop_articles_cover_official_learning_pages(self) -> None:
        expected_ids = {
            "write_a_glsl_top",
            "write_a_glsl_mat",
            "write_a_glsl_pop",
            "learning_about_pops",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        glsl_pop = article_cards["write_a_glsl_pop"]
        assert glsl_pop["source_url"] == "https://docs.derivative.ca/Write_a_GLSL_POP"
        assert {"glslPOP", "glsladvancedPOP"}.issubset(glsl_pop["covered_operators"])
        assert "TDIndex" in glsl_pop["key_concepts"]
        assert "TDNumElements" in glsl_pop["key_concepts"]
        assert {
            "Initialize Output Attributes",
            "Output Access",
            "Read-Write",
            "writeonly SSBO",
            "atomic operations",
            "TDInputNumPoints()",
            "TDInputNumPrims()",
            "TDInputNumVerts()",
            "TDInputPointIndex()",
            "cTDArraySize_Attrib",
            "cTDArraySizePoint_Attrib",
            "TDInputNumPoints_OutputName()",
            "oTDPoint_OutputName_AttribName[]",
            "TDCopyIndex()",
            "TDTemplate_Attrib()",
            "TDUpdatePointGroups()",
        }.issubset(set(glsl_pop["key_concepts"]))
        assert any("Output Attributes" in note for note in glsl_pop["guidance"])
        assert any("uninitialized" in note and "crashes" in note for note in glsl_pop["guidance"])
        assert any("Manual" in note and "undefined" in note for note in glsl_pop["guidance"])
        assert any("atomic" in note and "Read-Write" in note for note in glsl_pop["guidance"])

        glsl_top = article_cards["write_a_glsl_top"]
        assert glsl_top["source_url"] == "https://docs.derivative.ca/Write_a_GLSL_TOP"
        assert "TDOutputSwizzle" in glsl_top["key_concepts"]
        assert "TDImageStoreOutput" in glsl_top["key_concepts"]
        assert {"glslTOP"}.issubset(glsl_top["covered_operators"])
        assert {"glslTOP", "glslmultiTOP", "renderselectTOP", "texture3dTOP"}.issubset(
            set(glsl_top["covered_operators"])
        )
        assert {
            "TD_NUM_2D_INPUTS",
            "TD_NUM_3D_INPUTS",
            "TD_NUM_2D_ARRAY_INPUTS",
            "TD_NUM_CUBE_INPUTS",
            "sTD3DInputs",
            "sTD2DArrayInputs",
            "sTDCubeInputs",
            "nonuniformEXT()",
            "sTDNoiseMap",
            "sTDSineLookup",
            "TDBufferLength_AttribName()",
            "cTDBufferArraySize_AttribName",
            "uTD2DInfos",
            "uTD3DInfos",
            "uTD2DArrayInfos",
            "uTDCubeInfos",
            "uTDCurrentDepth",
            "uTDPass",
            "atomic_uint",
            "atomicCounterIncrement()",
            "Specialization Constants",
            "layout(constant_id = 0)",
            "TDDither()",
            "textureOffset()",
            "# of Color Buffers",
            "Render Select TOP",
            "sTDComputeOutputs[]",
            "TDSOPToProj",
            "P",
            "uv[0]",
        }.issubset(set(glsl_top["key_concepts"]))
        assert any("nonuniformEXT" in note and "dynamic" in note for note in glsl_top["guidance"])
        assert any("uTDCurrentDepth" in note and "3D Texture" in note for note in glsl_top["guidance"])
        assert any("atomic" in note and "Atomic Counters" in note for note in glsl_top["guidance"])
        assert any("Render Select TOP" in note and "undefined" in note for note in glsl_top["guidance"])
        assert any(
            "vertex shader" in note and "vUV" in note and "TDSOPToProj" in note
            for note in glsl_top["guidance"]
        )

        glsl_mat = article_cards["write_a_glsl_mat"]
        assert glsl_mat["source_url"] == "https://docs.derivative.ca/Write_a_GLSL_MAT"
        assert "TDWorldToProj" in glsl_mat["key_concepts"]
        assert "TDAttrib_*" in glsl_mat["key_concepts"]
        assert {"glslMAT"}.issubset(glsl_mat["covered_operators"])
        assert {
            "GLSL 3.30+",
            "Vertex Shader",
            "Pixel Shader",
            "Geometry Shader",
            "TD_NUM_LIGHTS",
            "TD_NUM_ENV_LIGHTS",
            "TD_NUM_CAMERAS",
            "TD_VERTEX_SHADER",
            "TD_PIXEL_SHADER",
            "TD_COMPUTE_SHADER",
            "TDTexAttrib_AttribName()",
            "TDBufferLength_AttribName()",
            "cTDBufferArraySize_AttribName",
            "TDTrueCameraIndex()",
            "TDCheckDiscard()",
            "TDPointCoord()",
            "gl_PointCoord",
            "TD_NUM_COLOR_BUFFERS",
            "TDImageStore_Name()",
            "TDImageLoad_Name()",
            "TD_RENDER_TOP",
        }.issubset(set(glsl_mat["key_concepts"]))
        assert any("TDInstanceID()" in note and "gl_InstanceID" in note for note in glsl_mat["guidance"])
        assert any("TDPointCoord" in note and "gl_PointCoord" in note for note in glsl_mat["guidance"])
        assert any("TD_RENDER_TOP" in note and "TDImageStore_Name" in note for note in glsl_mat["guidance"])
        assert {
            "cameraCOMP",
            "lightCOMP",
            "phongMAT",
            "renderpickCHOP",
            "renderpickDAT",
            "texture3dTOP",
            "attributecreateSOP",
            "geotextCOMP",
        }.issubset(set(glsl_mat["covered_operators"]))
        assert {
            "TDNormal()",
            "TDTexCoord(uint coordLayer)",
            "TDPointColor()",
            "TDPixelColor(vec4 c)",
            "TDFrontFacing()",
            "TDFog()",
            "TDDither()",
            "TDCheckOrderIndTrans()",
            "TDLightingPBR()",
            "TDEnvLightingPBR()",
            "TDLighting()",
            "TDHardShadow()",
            "TDSoftShadow()",
            "TDProjMap()",
            "TDCompareShadowTexture()",
            "TDShadowTexture()",
            "TDProjTexture()",
            "TDConeLookup()",
            "TDAttenuateLight()",
            "TDDeformNorm()",
            "TDSkinnedDeform()",
            "TDSkinnedDeformVec()",
            "TDBoneMat()",
            "pCapt",
            "pCaptPath",
            "pCaptData",
            "BoneIndices",
            "BoneWeights",
            "TDInstanceMat()",
            "TDInstanceTexCoord()",
            "TDInstanceColor()",
            "TDInstanceCustomAttrib0()",
            "TDInstanceTextureIndex()",
            "TDInstanceTexture()",
            "flat out int vInstanceID",
            "flat uint",
            "TD_PICKING_ACTIVE",
            "TDWritePickingValues()",
            "vTDPickVert",
            "vTDCustomPickVert",
            "Specialization Constants",
            "layout(constant_id = 0)",
            "#include",
        }.issubset(set(glsl_mat["key_concepts"]))
        assert any(
            "TDLighting" in note and "shadow" in note and "projection" in note
            for note in glsl_mat["guidance"]
        )
        assert any(
            "TDDeformNorm" in note and "TDNormal" in note and "World space" in note
            for note in glsl_mat["guidance"]
        )
        assert any("TDInstanceTextureIndex" in note and "flat" in note for note in glsl_mat["guidance"])
        assert any(
            "TDWritePickingValues" in note and "TD_PICKING_ACTIVE" in note for note in glsl_mat["guidance"]
        )
        assert any(
            "Specialization" in note and "constantly changing" in note for note in glsl_mat["guidance"]
        )

        pop_learning = article_cards["learning_about_pops"]
        assert pop_learning["source_url"] == "https://docs.derivative.ca/Learning_About_POPs"
        assert "POP Concepts" in pop_learning["key_concepts"]
        assert "Overview.toe" in pop_learning["key_concepts"]
        assert {"POP"}.issubset(pop_learning["families"])

    def test_pop_foundation_articles_cover_dimensions_attributes_and_common_pages(self) -> None:
        expected_ids = {
            "pop",
            "pop_dimension",
            "points,_vertices_and_primitives_in_pops",
            "mapping_pop_attributes_to_parameters",
            "pop_generator_common_page",
            "pop_filter_common_page",
            "pop_info_channels_common_page",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        pop = article_cards["pop"]
        assert pop["source_url"] == "https://docs.derivative.ca/POP"
        assert {
            "Point Operators",
            "3D geometry",
            "general numeric data",
            "GPU-accelerated",
            "Render TOP",
            "DMX lighting",
            "LED arrays",
            "lasers",
            "OP Snippets",
            "POP Class",
        }.issubset(set(pop["key_concepts"]))
        assert {"POP", "GPU"}.issubset(pop["families"])

        dimension = article_cards["pop_dimension"]
        assert dimension["source_url"] == "https://docs.derivative.ca/POP_Dimension"
        assert {
            "Dimension",
            "metadata",
            "cols/rows/slices",
            "replaces meshes in SOPs",
            "POP to TOP",
            "TOP to POP",
            "_NumDim",
            "_DimSize[0]",
            "_DimI[1]",
            "_DimU[0]",
            "_DimCy[0]",
            "OP.dimension",
        }.issubset(set(dimension["key_concepts"]))
        assert any("product" in note for note in dimension["guidance"])

        primitives = article_cards["points,_vertices_and_primitives_in_pops"]
        assert (
            primitives["source_url"] == "https://docs.derivative.ca/Points,_Vertices_and_Primitives_in_POPs"
        )
        assert {
            "Points",
            "Primitives",
            "Vertices",
            "Triangle Primitive",
            "Quadrelateral (quad) Primitive",
            "Line Primitive",
            "Linestrip Primitive",
            "Point Primitive",
            "Meshes - NOT IMPLEMENTED IN POPS ATM",
            "point list with no primitives",
        }.issubset(set(primitives["key_concepts"]))
        assert any("not implemented" in note for note in primitives["guidance"])

        mapping = article_cards["mapping_pop_attributes_to_parameters"]
        assert mapping["source_url"] == "https://docs.derivative.ca/Mapping_POP_Attributes_to_Parameters"
        assert {
            "Map page",
            "Transform POP",
            "Attributes",
            "Combine Operation",
            "Add",
            "Multiply",
            "Set",
            "Sequential Blocks",
            "_in0",
        }.issubset(set(mapping["key_concepts"]))
        assert {"transformPOP", "blendPOP", "noisePOP"}.issubset(mapping["covered_operators"])

        generator_common = article_cards["pop_generator_common_page"]
        assert generator_common["source_url"] == "https://docs.derivative.ca/POP_Generator_Common_Page"
        assert {"bypass", "freeextragpumem", "delinputattrs", "first input", "isolate attributes"}.issubset(
            set(generator_common["key_concepts"])
        )
        assert {"POP", "PARAMETER"}.issubset(generator_common["families"])

        filter_common = article_cards["pop_filter_common_page"]
        assert filter_common["source_url"] == "https://docs.derivative.ca/POP_Filter_Common_Page"
        assert {
            "bypass",
            "freeextragpumem",
            "delinputattrs",
            "GPU memory",
            "Delete Input Attributes",
        }.issubset(set(filter_common["key_concepts"]))
        assert any("first input" in note for note in filter_common["guidance"])

        info_common = article_cards["pop_info_channels_common_page"]
        assert info_common["source_url"] == "https://docs.derivative.ca/POP_Info_Channels_Common_Page"
        assert {"Common POP Info Channels", "Info CHOP", "POP", "GPU", "Render TOP"}.issubset(
            set(info_common["key_concepts"])
        )
        assert any("operator-specific" in note for note in info_common["guidance"])

    def test_rendering_and_mat_articles_cover_render_material_and_shadow_workflows(self) -> None:
        expected_ids = {
            "rendering",
            "mat",
            "comp_render_page",
            "mat_common_page",
            "mat_deform_page",
            "mat_filter_common_page",
            "mat_generator_common_page",
            "mat_info_channels_common_page",
            "rendering_shadows",
            "why_is_my_render_black",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        rendering = article_cards["rendering"]
        assert rendering["source_url"] == "https://docs.derivative.ca/Rendering"
        assert {
            "Render TOP",
            "Render Pass TOP",
            "GLSL",
            "Camera COMP",
            "Geometry COMP",
            "Render Flag",
            "Light COMP",
            "MATs",
            "off-screen buffer",
            "Depth Buffer",
            "linear fashion",
        }.issubset(set(rendering["key_concepts"]))
        assert {"TOP", "COMP", "MAT", "GLSL"}.issubset(rendering["families"])

        mat = article_cards["mat"]
        assert mat["source_url"] == "https://docs.derivative.ca/MAT"
        assert {
            "Shader",
            "SOP",
            "3D Geometry Object",
            "Material parameter",
            "Object Components",
            "Phong MAT",
            "GLSL MAT",
            "TOPs",
            "GLSL",
            "normals",
            "Texture Coordinates",
            "PBR MAT",
            "Environment Light COMP",
            "Point Sprite MAT",
        }.issubset(set(mat["key_concepts"]))
        assert {"phongMAT", "glslMAT", "pbrMAT", "constantMAT"}.issubset(mat["covered_operators"])

        comp_render = article_cards["comp_render_page"]
        assert comp_render["source_url"] == "https://docs.derivative.ca/COMP_Render_Page"
        assert {
            "material",
            "render",
            "Render TOP",
            "Render Flag",
            "drawpriority",
            "pickpriority",
            "Render Pick CHOP",
            "Render Pick DAT",
            "lightmask",
        }.issubset(set(comp_render["key_concepts"]))
        assert any("logical AND" in note for note in comp_render["guidance"])

        mat_common = article_cards["mat_common_page"]
        assert mat_common["source_url"] == "https://docs.derivative.ca/MAT_Common_Page"
        assert {
            "Blending",
            "Depth Test",
            "Alpha Test",
            "Wire Frame",
            "Cull Face",
            "Polygon Depth Offset",
            "blending",
            "srcblend",
            "destblend",
            "depthtest",
            "depthwriting",
            "alphatest",
            "wireframe",
            "cullface",
            "polygonoffset",
        }.issubset(set(mat_common["key_concepts"]))
        assert {"MAT", "PARAMETER"}.issubset(mat_common["families"])

        mat_deform = article_cards["mat_deform_page"]
        assert mat_deform["source_url"] == "https://docs.derivative.ca/MAT_Deform_Page"
        assert {
            "dodeform",
            "deformdata",
            "sop",
            "mat",
            "deformin",
            "targetsop",
            "pcaptpath",
            "pcaptdata",
            "skelrootpath",
            "Bone Group SOP",
        }.issubset(set(mat_deform["key_concepts"]))

        mat_filter_common = article_cards["mat_filter_common_page"]
        assert mat_filter_common["source_url"] == "https://docs.derivative.ca/MAT_Filter_Common_Page"
        assert {
            "Parameters - Common Page",
            "Blending",
            "Depth Test",
            "Alpha Test",
            "Wire Frame",
            "Cull Face",
            "Polygon Depth Offset",
            "srcblend",
            "destblend",
            "depthfunc",
            "alphathreshold",
            "wirewidth",
            "backfaces",
            "frontfaces",
        }.issubset(set(mat_filter_common["key_concepts"]))

        mat_generator_common = article_cards["mat_generator_common_page"]
        assert mat_generator_common["source_url"] == "https://docs.derivative.ca/MAT_Generator_Common_Page"
        assert {
            "Parameters - Common Page",
            "Blending",
            "Depth Test",
            "Alpha Test",
            "Wire Frame",
            "Cull Face",
            "Polygon Depth Offset",
            "blendop",
            "blendopa",
            "constantcol",
            "omconstantcol",
            "constanta",
            "omconstanta",
        }.issubset(set(mat_generator_common["key_concepts"]))

        mat_info = article_cards["mat_info_channels_common_page"]
        assert mat_info["source_url"] == "https://docs.derivative.ca/MAT_Info_Channels_Common_Page"
        assert {"Common MAT Info Channels", "Info CHOP", "MAT", "operator-specific info channels"}.issubset(
            set(mat_info["key_concepts"])
        )
        assert any("operator-specific" in note for note in mat_info["guidance"])

        shadows = article_cards["rendering_shadows"]
        assert shadows["source_url"] == "https://docs.derivative.ca/Rendering_Shadows"
        assert {
            "Hard, 2D Mapped",
            "Shadow Casters",
            "Polygon Offset Factor",
            "Focal Length",
            "Aperture",
            "Depth TOP",
            "Near",
            "Shadow Strength",
            "Shadow Color",
            "Custom Shadow Map",
            "TDShadowTexture",
            "Polygon Depth Offset",
        }.issubset(set(shadows["key_concepts"]))
        assert {"lightCOMP", "phongMAT", "depthTOP", "renderTOP", "glslMAT"}.issubset(
            shadows["covered_operators"]
        )

        black_render = article_cards["why_is_my_render_black"]
        assert black_render["source_url"] == "https://docs.derivative.ca/Why_is_My_Render_Black"
        assert {
            "checkerboard",
            "not lit",
            "Constant MAT",
            "Cube Map",
            "Near and Far",
            "Geometry parameter",
            "Render flag",
            "Render parameter",
            "SOP Render flag",
            "bounding box",
            "alpha",
            "normals",
            "SOP to DAT",
            "Light display flag",
            "Base COMPs",
        }.issubset(set(black_render["key_concepts"]))
        assert any("checkerboard" in note for note in black_render["guidance"])

    def test_object_comp_transform_instancing_and_render_optimization_articles_are_structured(self) -> None:
        expected_ids = {
            "object_component",
            "comp_xform_page",
            "comp_pre-xform_page",
            "comp_geometry_common_page",
            "comp_instance_page",
            "comp_instance_2_page",
            "comp_instance_3_page",
            "optimize_geometry_for_rendering",
            "render_flag",
            "multi-camera_rendering",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        object_component = article_cards["object_component"]
        assert object_component["source_url"] == "https://docs.derivative.ca/Object_Component"
        assert {
            "Object Components",
            "3D scenes",
            "Objects",
            "Ambient Light COMP",
            "Blend COMP",
            "Bone COMP",
            "Camera COMP",
            "Environment Light COMP",
            "Geometry COMP",
            "Light COMP",
            "Null COMP",
            "Shared Mem Out COMP",
            "Shared Mem In COMP",
            "USD COMP",
            "ObjectCOMP Class",
        }.issubset(set(object_component["key_concepts"]))
        assert {"COMP", "RENDERING"}.issubset(object_component["families"])

        xform = article_cards["comp_xform_page"]
        assert xform["source_url"] == "https://docs.derivative.ca/COMP_Xform_Page"
        assert {
            "world space",
            "xord",
            "rord",
            "t",
            "r",
            "s",
            "p",
            "scale",
            "T * R * S * Position",
            "parentxformsrc",
            "parentobject",
            "lookat",
            "forwarddir",
            "lookup",
            "pathsop",
            "roll",
            "pos",
            "pathorient",
            "up",
            "bank",
        }.issubset(set(xform["key_concepts"]))
        assert any("Look At" in note for note in xform["guidance"])

        pre_xform = article_cards["comp_pre-xform_page"]
        assert pre_xform["source_url"] == "https://docs.derivative.ca/COMP_Pre-Xform_Page"
        assert {
            "preXForm * xform * Position",
            "pxform",
            "pxord",
            "prord",
            "pt",
            "pr",
            "ps",
            "pp",
            "pscale",
            "preset",
            "pcommit",
            "xformmatrixop",
            "Matrix Parameters",
        }.issubset(set(pre_xform["key_concepts"]))
        assert any("left of the Xform" in note for note in pre_xform["guidance"])

        common = article_cards["comp_geometry_common_page"]
        assert common["source_url"] == "https://docs.derivative.ca/COMP_Geometry_Common_Page"
        assert {
            "parentshortcut",
            "opshortcut",
            "iop",
            "iop0shortcut",
            "iop0op",
            "nodeview",
            "opviewer",
            "enablecloning",
            "enablecloningpulse",
            "clone",
            "loadondemand",
            "enableexternaltox",
            "enableexternaltoxpulse",
            "externaltox",
            "reloadcustom",
            "reloadbuiltin",
            "savebackup",
            "subcompname",
            "relpath",
            ".tox",
        }.issubset(set(common["key_concepts"]))
        assert any("shared common page" in note for note in common["guidance"])

        instance = article_cards["comp_instance_page"]
        assert instance["source_url"] == "https://docs.derivative.ca/COMP_Instance_Page"
        assert {
            "hardware instances",
            "instance ID",
            "MAT shader",
            "Render Pick CHOP",
            "TOP RGBA",
            "CHOP samples",
            "SOP attributes",
            "DAT columns",
            "instancing",
            "instancecountmode",
            "manual",
            "oplength",
            "numinstances",
            "instanceop",
            "instancefirstrow",
            "instxord",
            "instrord",
            "instanceactive",
            "instancetx",
            "instancery",
            "instancesz",
            "instancepx",
        }.issubset(set(instance["key_concepts"]))
        assert {"geometryCOMP", "renderpickCHOP", "glslMAT"}.issubset(instance["covered_operators"])

        instance_2 = article_cards["comp_instance_2_page"]
        assert instance_2["source_url"] == "https://docs.derivative.ca/COMP_Instance_2_Page"
        assert {
            "Rotate to Vector",
            "instancerottoorder",
            "default",
            "prerot",
            "postrot",
            "instancerottoforward",
            "instancerottoop",
            "instancerottox",
            "instancerotupop",
            "instanceorder",
            "instanceworld",
            "worldinstance",
            "instancetexmode",
            "instanceu",
            "instancev",
            "instancew",
            "instancecolormode",
            "Cd",
            "instancetexs",
        }.issubset(set(instance_2["key_concepts"]))
        assert any("Instance 2" in note for note in instance_2["guidance"])

        instance_3 = article_cards["comp_instance_3_page"]
        assert instance_3["source_url"] == "https://docs.derivative.ca/COMP_Instance_3_Page"
        assert {
            "Custom attributes",
            "GLSL MAT",
            "TDInstanceCustomAttrib0()",
            "TDInstanceCustomAttrib1()",
            "PBR MAT",
            "instance",
            "instance0customop",
            "instance0customx",
            "instance0customy",
            "instance0customz",
            "instance0customw",
            "GPU maximum",
        }.issubset(set(instance_3["key_concepts"]))
        assert any("ignored in other materials" in note for note in instance_3["guidance"])

        optimize = article_cards["optimize_geometry_for_rendering"]
        assert optimize["source_url"] == "https://docs.derivative.ca/Optimize_Geometry_for_Rendering"
        assert {
            "Render TOPs",
            "Primitive type and primitive count",
            "Vertex count",
            "SOP count",
            "3 vertex polygons",
            "triangle strips",
            "Geometry Batches",
            "VBO",
            "Waiting For VBO Update",
            "Performance Monitor",
            "single draw command",
            "Merge SOP",
            "Vulkan",
            "Triangle Strip Stitching",
            "non-batched primitive",
            "SOP cook time",
        }.issubset(set(optimize["key_concepts"]))
        assert any("static geometry" in note for note in optimize["guidance"])

        render_flag = article_cards["render_flag"]
        assert render_flag["source_url"] == "https://docs.derivative.ca/Render_Flag"
        assert {
            "Render Flag",
            "SOP nodes",
            "Geometry components",
            "Render TOP",
            "SOP Render flag",
            "Geometry component Render flag",
            "Geometry parameter",
            "Render Pass TOP",
            "purple flag",
        }.issubset(set(render_flag["key_concepts"]))
        assert any("all three" in note for note in render_flag["guidance"])

        multi_camera = article_cards["multi-camera_rendering"]
        assert multi_camera["source_url"] == "https://docs.derivative.ca/Multi-Camera_Rendering"
        assert {
            "multiple cameras",
            "single rendering pass",
            "scene-graph",
            "graphics driver",
            "Nvidia Pascal",
            "AMD Polaris",
            "VR rendering",
            "Cube Map",
            "different light masks",
            "Cameras parameter",
            "Multi-Camera Hint",
            "Render Select TOP",
            "Simultaneous Multi-Projection",
        }.issubset(set(multi_camera["key_concepts"]))
        assert {"renderTOP", "renderselectTOP", "cameraCOMP"}.issubset(multi_camera["covered_operators"])

    def test_cplusplus_and_chop_articles_cover_official_learning_pages(self) -> None:
        expected_ids = {
            "write_a_cplusplus_plugin",
            "write_a_cplusplus_pop",
            "write_a_cplusplus_top",
            "write_a_cplusplus_chop",
            "anatomy_of_a_chop",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        plugin = article_cards["write_a_cplusplus_plugin"]
        assert plugin["source_url"] == "https://docs.derivative.ca/Write_a_CPlusPlus_Plugin"
        assert {"cplusplusCHOP", "cplusplusTOP", "cplusplusPOP", "cplusplusSOP", "cplusplusDAT"}.issubset(
            plugin["covered_operators"]
        )
        assert "setupParameters()" in plugin["key_concepts"]
        assert "pulsePressed()" in plugin["key_concepts"]
        assert "Custom Operator" in plugin["key_concepts"]
        assert any("Python only works" in note for note in plugin["guidance"])

        cplusplus_pop = article_cards["write_a_cplusplus_pop"]
        assert cplusplus_pop["source_url"] == "https://docs.derivative.ca/Write_a_CPlusPlus_POP"
        assert {"cplusplusPOP", "renderTOP"}.issubset(cplusplus_pop["covered_operators"])
        assert "POP_Context::createBuffer()" in cplusplus_pop["key_concepts"]
        assert "POP_Output::setAttribute()" in cplusplus_pop["key_concepts"]
        assert "POP_TopologyInfo" in cplusplus_pop["key_concepts"]
        assert any("primitive restart index" in note for note in cplusplus_pop["guidance"])

        cplusplus_top = article_cards["write_a_cplusplus_top"]
        assert cplusplus_top["source_url"] == "https://docs.derivative.ca/Write_a_CPlusPlus_TOP"
        assert {"cplusplusTOP"}.issubset(cplusplus_top["covered_operators"])
        assert "TOP_ExecuteMode::CPUMem" in cplusplus_top["key_concepts"]
        assert "TOP_ExecuteMode::CUDA" in cplusplus_top["key_concepts"]
        assert "OP_Context::beginCUDAOperations()" in cplusplus_top["key_concepts"]

        cplusplus_chop = article_cards["write_a_cplusplus_chop"]
        assert cplusplus_chop["source_url"] == "https://docs.derivative.ca/Write_a_CPlusPlus_CHOP"
        assert {"cplusplusCHOP"}.issubset(cplusplus_chop["covered_operators"])
        assert "getOutputInfo()" in cplusplus_chop["key_concepts"]
        assert "Time Slice" in cplusplus_chop["key_concepts"]
        assert any("sample rate" in note for note in cplusplus_chop["guidance"])

        anatomy = article_cards["anatomy_of_a_chop"]
        assert anatomy["source_url"] == "https://docs.derivative.ca/Anatomy_of_a_CHOP"
        assert {"CHOP"}.issubset(anatomy["families"])
        assert "raw samples" in anatomy["key_concepts"]
        assert "Export flag" in anatomy["key_concepts"]
        assert "chop()" in anatomy["key_concepts"]
        assert "chopi()" in anatomy["key_concepts"]
        assert any("non-time-dependent" in note for note in anatomy["guidance"])

    def test_parameter_reference_articles_cover_official_control_workflows(self) -> None:
        expected_ids = {
            "parameter",
            "parameter_mode",
            "custom_parameters",
            "par_class",
            "page_class",
            "pargroup_class",
            "binding",
            "export",
            "parameter_reference",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        parameter = article_cards["parameter"]
        assert parameter["source_url"] == "https://docs.derivative.ca/Parameter"
        assert "Constant Mode" in parameter["key_concepts"]
        assert "Expression Mode" in parameter["key_concepts"]
        assert "Export Mode" in parameter["key_concepts"]
        assert "Bind Mode" in parameter["key_concepts"]
        assert any(".eval()" in note for note in parameter["guidance"])

        parameter_mode = article_cards["parameter_mode"]
        assert parameter_mode["source_url"] == "https://docs.derivative.ca/Parameter_Mode"
        assert {"Constant Mode", "Expression Mode", "Export Mode", "Bind Mode"}.issubset(
            set(parameter_mode["key_concepts"])
        )
        assert any("Export mode can only be selected" in note for note in parameter_mode["guidance"])

        custom_parameters = article_cards["custom_parameters"]
        assert custom_parameters["source_url"] == "https://docs.derivative.ca/Custom_Parameters"
        assert {"appendCustomPage()", "setupParameters()", "styleCloneImmune"}.issubset(
            set(custom_parameters["key_concepts"])
        )
        assert any("uppercase first letter" in note for note in custom_parameters["guidance"])

        par_class = article_cards["par_class"]
        assert par_class["source_url"] == "https://docs.derivative.ca/Par_Class"
        assert {"val", "expr", "mode", "menuNames", "menuLabels", "menuIndex", "eval()"}.issubset(
            set(par_class["key_concepts"])
        )
        assert any("menuIndex" in note for note in par_class["guidance"])

        page_class = article_cards["page_class"]
        assert page_class["source_url"] == "https://docs.derivative.ca/Page_Class"
        assert {"appendOP()", "appendFloat()", "appendMenu()", "appendRGB()", "replace"}.issubset(
            set(page_class["key_concepts"])
        )
        assert any("ParGroup" in note for note in page_class["guidance"])

        pargroup_class = article_cards["pargroup_class"]
        assert pargroup_class["source_url"] == "https://docs.derivative.ca/ParGroup_Class"
        assert {"bindExpr", "defaultMode", "enableExpr", "expr", "eval()"}.issubset(
            set(pargroup_class["key_concepts"])
        )
        assert any("tuple" in note for note in pargroup_class["guidance"])

        binding = article_cards["binding"]
        assert binding["source_url"] == "https://docs.derivative.ca/Binding"
        assert {"bind master", "bind reference", "bind chain", "menuSource", "bind tuple"}.issubset(
            set(binding["key_concepts"])
        )
        assert any("master to the reference" in note for note in binding["guidance"])

        export = article_cards["export"]
        assert export["source_url"] == "https://docs.derivative.ca/Export"
        assert {"CHOP Exporting", "DAT Exporting", "Export Flag", "Channel Name is Path:Parameter"}.issubset(
            set(export["key_concepts"])
        )
        assert any("text strings" in note for note in export["guidance"])

        parameter_reference = article_cards["parameter_reference"]
        assert parameter_reference["source_url"] == "https://docs.derivative.ca/Parameter_Reference"
        assert {"Yank Parameter", "Put Yanked References", "op('pattern1').par.phase"}.issubset(
            set(parameter_reference["key_concepts"])
        )
        assert any("expression" in note for note in parameter_reference["guidance"])

    def test_python_operator_class_articles_cover_core_family_api_pages(self) -> None:
        expected_ids = {
            "op_class",
            "comp_class",
            "top_class",
            "chop_class",
            "dat_class",
            "sop_class",
            "pop_class",
            "mat_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        op_class = article_cards["op_class"]
        assert op_class["source_url"] == "https://docs.derivative.ca/OP_Class"
        assert {"op()", "opex", "par", "parGroup", "storage", "tags", "errors()"}.issubset(
            set(op_class["key_concepts"])
        )
        assert any("opex" in note for note in op_class["guidance"])

        comp_class = article_cards["comp_class"]
        assert comp_class["source_url"] == "https://docs.derivative.ca/COMP_Class"
        assert {"create()", "copy()", "children", "layout()", "findChildren()"}.issubset(
            set(comp_class["key_concepts"])
        )
        assert {"COMP", "PYTHON"}.issubset(comp_class["families"])

        top_class = article_cards["top_class"]
        assert top_class["source_url"] == "https://docs.derivative.ca/TOP_Class"
        assert {"width", "height", "aspect", "numpyArray()", "save()"}.issubset(
            set(top_class["key_concepts"])
        )
        assert {"TOP", "PYTHON", "GPU"}.issubset(top_class["families"])

        chop_class = article_cards["chop_class"]
        assert chop_class["source_url"] == "https://docs.derivative.ca/CHOP_Class"
        assert {"numChans", "numSamples", "rate", "chan()", "chans()"}.issubset(
            set(chop_class["key_concepts"])
        )
        assert any("rate" in note for note in chop_class["guidance"])

        dat_class = article_cards["dat_class"]
        assert dat_class["source_url"] == "https://docs.derivative.ca/DAT_Class"
        assert {"module", "numRows", "numCols", "cell()", "findCell()", "setSize()"}.issubset(
            set(dat_class["key_concepts"])
        )
        assert any("module" in note for note in dat_class["guidance"])

        sop_class = article_cards["sop_class"]
        assert sop_class["source_url"] == "https://docs.derivative.ca/SOP_Class"
        assert {"points", "prims", "numPoints", "numVertices", "pointAttribs", "bounds()"}.issubset(
            set(sop_class["key_concepts"])
        )
        assert {"SOP", "PYTHON"}.issubset(sop_class["families"])

        pop_class = article_cards["pop_class"]
        assert pop_class["source_url"] == "https://docs.derivative.ca/POP_Class"
        assert {"dimension", "pointAttributes", "primAttributes", "vertAttributes"}.issubset(
            set(pop_class["key_concepts"])
        )
        assert {"POP", "PYTHON"}.issubset(pop_class["families"])

        mat_class = article_cards["mat_class"]
        assert mat_class["source_url"] == "https://docs.derivative.ca/MAT_Class"
        assert {"OP Class", "op()", "opex", "par", "No operator specific methods"}.issubset(
            set(mat_class["key_concepts"])
        )
        assert {"MAT", "PYTHON"}.issubset(mat_class["families"])

    def test_pop_and_sop_python_geometry_articles_cover_attribute_and_point_apis(self) -> None:
        expected_ids = {
            "attribute_class",
            "attributes_class",
            "attributedata_class",
            "inputpoint_class",
            "point_class",
            "points_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        attribute_class = article_cards["attribute_class"]
        assert attribute_class["source_url"] == "https://docs.derivative.ca/Attribute_Class"
        assert {
            "owner",
            "name",
            "size",
            "type",
            "default",
            "isArray",
            "arraySize",
            "numMatCols",
            "numMatRows",
            "destroy()",
            "vals(delayed=False)",
        }.issubset(set(attribute_class["key_concepts"]))
        assert {"PYTHON", "GEOMETRY"}.issubset(attribute_class["families"])
        assert any("GPU" in note for note in attribute_class["guidance"])

        attributes_class = article_cards["attributes_class"]
        assert attributes_class["source_url"] == "https://docs.derivative.ca/Attributes_Class"
        assert {
            "[name]",
            "create(name, default)",
            "N",
            "uv",
            "T",
            "v",
            "Cd",
        }.issubset(set(attributes_class["key_concepts"]))
        assert any("standard attributes" in note for note in attributes_class["guidance"])

        attributedata_class = article_cards["attributedata_class"]
        assert attributedata_class["source_url"] == "https://docs.derivative.ca/AttributeData_Class"
        assert {"val", "float", "int", "str", "tuple", "TDU.Position", "TDU.Vector"}.issubset(
            set(attributedata_class["key_concepts"])
        )
        assert any("Normal" in note for note in attributedata_class["guidance"])

        inputpoint_class = article_cards["inputpoint_class"]
        assert inputpoint_class["source_url"] == "https://docs.derivative.ca/InputPoint_Class"
        assert {"color", "normal", "sopCenter", "Point SOP"}.issubset(set(inputpoint_class["key_concepts"]))
        assert any("Point SOP" in note for note in inputpoint_class["guidance"])

        point_class = article_cards["point_class"]
        assert point_class["source_url"] == "https://docs.derivative.ca/Point_Class"
        assert {"index", "P", "x", "y", "z", "normP", "destroy()"}.issubset(set(point_class["key_concepts"]))
        assert any("SOP.points" in note for note in point_class["guidance"])

        points_class = article_cards["points_class"]
        assert points_class["source_url"] == "https://docs.derivative.ca/Points_Class"
        assert {"len(Points)", "[index]", "Iterator", "td.Point"}.issubset(set(points_class["key_concepts"]))
        assert any("iterate" in note.lower() for note in points_class["guidance"])

    def test_component_authoring_articles_cover_comp_extension_and_timing_workflows(self) -> None:
        expected_ids = {
            "extensions",
            "comp_extensions_page",
            "component",
            "component_variables",
            "component_time",
            "component_timeline",
            "component_editor_dialog",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        extensions = article_cards["extensions"]
        assert extensions["source_url"] == "https://docs.derivative.ca/Extensions"
        assert {
            "ownerComp",
            "TDF.createProperty()",
            "StorageManager",
            "Promoted Extensions",
            "ext",
            "extensions",
            "extensionsReady",
            "onInitTD",
            "onDestroyTD",
        }.issubset(set(extensions["key_concepts"]))
        assert {"COMP", "PYTHON"}.issubset(extensions["families"])
        assert any("extensionsReady" in note for note in extensions["guidance"])

        comp_extensions_page = article_cards["comp_extensions_page"]
        assert comp_extensions_page["source_url"] == "https://docs.derivative.ca/COMP_Extensions_Page"
        assert {
            "reinitextensions",
            "initextonstart",
            "ext",
            "ext0object",
            "ext0name",
            "ext0promote",
            ".ext",
        }.issubset(set(comp_extensions_page["key_concepts"]))
        assert {"COMP", "PARAMETER"}.issubset(comp_extensions_page["families"])

        component = article_cards["component"]
        assert component["source_url"] == "https://docs.derivative.ca/Component"
        assert {
            "Object Components",
            "Panel Components",
            "Component Inputs and Outputs",
            "In TOP",
            "Out CHOP",
            "Save Component",
            ".tox",
        }.issubset(set(component["key_concepts"]))
        assert {"COMP"}.issubset(component["families"])

        component_variables = article_cards["component_variables"]
        assert component_variables["source_url"] == "https://docs.derivative.ca/Component_Variables"
        assert {
            "var('VARNAME')",
            "cvar",
            "hierarchical lookup",
            "local",
            "variables",
            "set_variables",
        }.issubset(set(component_variables["key_concepts"]))
        assert any("Extensions" in note for note in component_variables["guidance"])

        component_time = article_cards["component_time"]
        assert component_time["source_url"] == "https://docs.derivative.ca/Component_Time"
        assert {
            "local/time",
            "Time COMP",
            "rate",
            "start",
            "end",
            "range",
            "Timepath",
            "Add Component Time",
        }.issubset(set(component_time["key_concepts"]))
        assert {"timeCOMP"}.issubset(component_time["covered_operators"])

        component_timeline = article_cards["component_timeline"]
        assert component_timeline["source_url"] == "https://docs.derivative.ca/Component_Timeline"
        assert {"Component Time", "Run Independently", "Scope", "Timeline", "root time"}.issubset(
            set(component_timeline["key_concepts"])
        )
        assert any("Scope" in note for note in component_timeline["guidance"])

        component_editor = article_cards["component_editor_dialog"]
        assert component_editor["source_url"] == "https://docs.derivative.ca/Component_Editor_Dialog"
        assert {
            "Customize Component",
            "Custom Parameters",
            "Extension Code",
            "Shortcuts and Tags",
            "Storage",
            "human readable JSON",
            "Bind",
        }.issubset(set(component_editor["key_concepts"]))
        assert any("Component Editor" in note for note in component_editor["guidance"])

    def test_comp_panel_and_common_articles_cover_shared_comp_parameter_pages(self) -> None:
        expected_ids = {
            "comp",
            "comp_panel_page",
            "comp_panel_common_page",
            "comp_children_page",
            "comp_layout_page",
            "comp_look_page",
            "comp_drag_page",
            "comp_shortcuts_page",
            "comp_generator_common_page",
            "comp_generator_shortcuts_page",
            "comp_other_common_page",
            "comp_info_channels_common_page",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        comp = article_cards["comp"]
        assert comp["source_url"] == "https://docs.derivative.ca/COMP"
        assert {"COMP", "COMP Class", "COMPs"}.issubset(set(comp["key_concepts"]))
        assert any("summary/link-out" in note for note in comp["guidance"])

        panel_page = article_cards["comp_panel_page"]
        assert panel_page["source_url"] == "https://docs.derivative.ca/COMP_Panel_Page"
        assert {
            "Panel parameter page",
            "display",
            "enable",
            "helpdat",
            "cursor",
            "multitouch",
            "mtouchparent",
            "mtouchyes",
            "mtouchno",
            "constraincursor",
            "clickthrough",
            "mousewheel",
            "uvbuttons",
            "mouserel",
            "resize",
            "resizew",
            "resizeh",
            "reposition",
            "repocomp",
            "anchordrag",
            "scrolloverlay",
        }.issubset(set(panel_page["key_concepts"]))
        assert any("opacity" in note for note in panel_page["guidance"])
        assert any("Multi Touch In DAT" in note for note in panel_page["guidance"])

        panel_common = article_cards["comp_panel_common_page"]
        assert panel_common["source_url"] == "https://docs.derivative.ca/COMP_Panel_Common_Page"
        assert {
            "Panel Common Page",
            "node viewer",
            "clone relationships",
            "parentshortcut",
            "opshortcut",
            "iop",
            "iop0shortcut",
            "iop0op",
            "nodeview",
            "opviewer",
            "keepmemory",
            "enablecloning",
            "enablecloningpulse",
            "clone",
            "loadondemand",
            "enableexternaltox",
            "enableexternaltoxpulse",
            "externaltox",
            "reloadcustom",
            "reloadbuiltin",
            "savebackup",
            "subcompname",
            "relpath",
            ".tox",
            ".toe",
        }.issubset(set(panel_common["key_concepts"]))
        assert any("top-level" in note for note in panel_common["guidance"])

        children = article_cards["comp_children_page"]
        assert children["source_url"] == "https://docs.derivative.ca/COMP_Children_Page"
        assert {
            "Children parameter page",
            "align",
            "Grid Rows",
            "Grid Columns",
            "Match Network Nodes",
            "spacing",
            "alignmax",
            "margin",
            "absolute pixels",
            "justifymethod",
            "justifyh",
            "justifyv",
            "fit",
            "scale",
            "offset",
            "crop",
            "phscrollbar",
            "pvscrollbar",
            "scrollbarthickness",
        }.issubset(set(children["key_concepts"]))
        assert any("Align Order" in note for note in children["guidance"])
        assert any("Fit" in note and "Justify" in note for note in children["guidance"])

        layout = article_cards["comp_layout_page"]
        assert layout["source_url"] == "https://docs.derivative.ca/COMP_Layout_Page"
        assert {
            "Layout parameter page",
            "x",
            "y",
            "w",
            "h",
            "fixedaspect",
            "aspect",
            "layer",
            "hmode",
            "fill",
            "anchors",
            "leftanchor",
            "rightanchor",
            "horigin",
            "hfillweight",
            "vmode",
            "bottomanchor",
            "topanchor",
            "vorigin",
            "vfillweight",
            "alignallow",
            "alignorder",
            "postoffset",
            "sizefromwindow",
        }.issubset(set(layout["key_concepts"]))
        assert any("Depth Layer" in note for note in layout["guidance"])
        assert any("normalized anchors" in note for note in layout["guidance"])

        look = article_cards["comp_look_page"]
        assert look["source_url"] == "https://docs.derivative.ca/COMP_Look_Page"
        assert {
            "Look Page",
            "bgcolor",
            "bgalpha",
            "top",
            "topfill",
            "topsmoothness",
            "nearest",
            "linear",
            "mipmap",
            "bordera",
            "borderaalpha",
            "borderb",
            "borderbalpha",
            "leftborder",
            "rightborder",
            "bottomborder",
            "topborder",
            "borderover",
            "dodisablecolor",
            "disablecolor",
            "disablealpha",
            "multrgb",
            "composite",
            "opacity",
        }.issubset(set(look["key_concepts"]))
        assert {"TOP", "PANEL", "PARAMETER"}.issubset(look["families"])
        assert any("32-bit float" in note for note in look["guidance"])

        drag = article_cards["comp_drag_page"]
        assert drag["source_url"] == "https://docs.derivative.ca/COMP_Drag_Page"
        assert {
            "Drag/Drop Page",
            "Drag-and-Drop",
            "drag",
            "dragparent",
            "legacy",
            "dragno",
            "usecallbacks",
            "dragscript",
            "droptypescript",
            "dropdestscript",
            "paneldragop",
            "drop",
            "dropparent",
            "dropno",
            "dropscript",
            "temporary network",
            "Drop Types",
            "Table DAT",
        }.issubset(set(drag["key_concepts"]))
        assert any("alternative operator" in note for note in drag["guidance"])

        shortcuts = article_cards["comp_shortcuts_page"]
        assert shortcuts["source_url"] == "https://docs.derivative.ca/COMP_Shortcuts_Page"
        assert {
            "Shortcuts Page",
            "parentshortcut",
            "opshortcut",
            "iopshortcut1",
            "iop1",
            "parent.Name",
            "parent.Effect.width",
            "Parent Shortcuts",
            "Global OP Shortcuts",
            "Internal Operators",
        }.issubset(set(shortcuts["key_concepts"]))
        assert any("inside the component" in note for note in shortcuts["guidance"])

        generator_common = article_cards["comp_generator_common_page"]
        assert generator_common["source_url"] == "https://docs.derivative.ca/COMP_Generator_Common_Page"
        assert {
            "Generator Common Page",
            "node viewer",
            "clone relationships",
            "parentshortcut",
            "opshortcut",
            "iop0shortcut",
            "iop0op",
            "nodeview",
            "opviewer",
            "keepmemory",
            "enablecloning",
            "enablecloningpulse",
            "clone",
            "loadondemand",
            "externaltox",
            "reloadtoxonstart",
            "reloadcustom",
            "reloadbuiltin",
            "savebackup",
            "subcompname",
            "reinitnet",
            ".tox",
            ".toe",
        }.issubset(set(generator_common["key_concepts"]))
        assert any("reloadtoxonstart" in note for note in generator_common["guidance"])

        generator_shortcuts = article_cards["comp_generator_shortcuts_page"]
        assert generator_shortcuts["source_url"] == "https://docs.derivative.ca/COMP_Generator_Shortcuts_Page"
        assert {
            "Generator Shortcuts Page",
            "parentshortcut",
            "opshortcut",
            "iopshortcut1",
            "iop1",
            "Parent Shortcut",
            "Global OP Shortcut",
            "Internal OP",
        }.issubset(set(generator_shortcuts["key_concepts"]))
        assert any("same shortcut contract" in note for note in generator_shortcuts["guidance"])

        other_common = article_cards["comp_other_common_page"]
        assert other_common["source_url"] == "https://docs.derivative.ca/COMP_Other_Common_Page"
        assert {
            "Other Common Page",
            "parentshortcut",
            "opshortcut",
            "iop",
            "iop0shortcut",
            "iop0op",
            "opviewer",
            "enablecloning",
            "enablecloningpulse",
            "clone",
            "loadondemand",
            "enableexternaltox",
            "enableexternaltoxpulse",
            "externaltox",
            "reloadcustom",
            "reloadbuiltin",
            "savebackup",
            "subcompname",
            "relpath",
        }.issubset(set(other_common["key_concepts"]))
        assert any(".toe" in note and ".tox" in note for note in other_common["guidance"])

        info = article_cards["comp_info_channels_common_page"]
        assert info["source_url"] == "https://docs.derivative.ca/COMP_Info_Channels_Common_Page"
        assert {
            "Common COMP Info Channels",
            "Info CHOP",
            "num_children",
            "COMP",
            "Object Component",
            "Panel Component",
        }.issubset(set(info["key_concepts"]))
        assert any("only common channel" in note for note in info["guidance"])

    def test_panel_foundation_articles_cover_values_and_panelcomp_api(self) -> None:
        expected_ids = {
            "panel",
            "panel_component",
            "panel_value",
            "panelcomp_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        panel = article_cards["panel"]
        assert panel["source_url"] == "https://docs.derivative.ca/Panel"
        assert {
            "Control Panel",
            "custom graphical user interface",
            "Panel Component",
            "Text COMPs",
            "TOPs",
            "Panel Execute DAT",
            "Extensions",
            "panelCOMP Class",
            "Panel Values",
            "Panel CHOP",
            "Window COMP",
            "Pane type",
            "Open Viewer",
        }.issubset(set(panel["key_concepts"]))
        assert {"textCOMP", "panelCHOP", "panelexecuteDAT", "windowCOMP"}.issubset(panel["covered_operators"])
        assert any("Window COMP" in note for note in panel["guidance"])

        panel_component = article_cards["panel_component"]
        assert panel_component["source_url"] == "https://docs.derivative.ca/Panel_Component"
        assert {
            "custom interactive 2D control panels",
            "OP Create dialog",
            "OP Snippets",
            "Container COMP",
            "Widget COMP",
            "Text COMP",
            "Slider COMP",
            "Button COMP",
            "List COMP",
            "OP Viewer COMP",
            "Parameter COMP",
            "Select COMP",
            "Table COMP",
            "Panels within Panels",
            "Parenting",
            "3D Parenting",
            "Scripting with Panels",
            "PanelCOMP Class",
        }.issubset(set(panel_component["key_concepts"]))
        assert {
            "containerCOMP",
            "widgetCOMP",
            "textCOMP",
            "sliderCOMP",
            "buttonCOMP",
            "listCOMP",
            "opviewerCOMP",
            "parameterCOMP",
            "selectCOMP",
            "tableCOMP",
        }.issubset(panel_component["covered_operators"])
        assert any("Container COMP" in note for note in panel_component["guidance"])

        panel_value = article_cards["panel_value"]
        assert panel_value["source_url"] == "https://docs.derivative.ca/Panel_Value"
        assert {
            "Panel Values",
            "Panel Components",
            "Panel CHOP",
            "PanelValue Class",
            "panel() expression",
            "Panel Execute DAT",
            "click() calls",
            "instant",
            "string",
            "select",
            "u",
            "v",
            "trueu",
            "truev",
            "rollover",
            "inside",
            "children",
            "display",
            "enable",
            "readonly",
            "key",
            "focusselect",
            "PanelCOMP.setFocus",
            "screenw",
            "screenh",
            "Node Viewers",
            "drag",
            "drop",
            "scrollu",
            "scrollv",
            "stateu",
            "statev",
            "state",
            "picked",
            "radio",
            "radioname",
            "field",
            "fieldediting",
            "celloverid",
        }.issubset(set(panel_value["key_concepts"]))
        assert {"panelCHOP", "panelexecuteDAT", "buttonCOMP", "sliderCOMP", "tableCOMP"}.issubset(
            panel_value["covered_operators"]
        )
        assert any("string values" in note and "instant" in note for note in panel_value["guidance"])
        assert any("Node Viewers" in note for note in panel_value["guidance"])
        assert any("stateu" in note and "obsolete" in note for note in panel_value["guidance"])

        panelcomp_class = article_cards["panelcomp_class"]
        assert panelcomp_class["source_url"] == "https://docs.derivative.ca/PanelCOMP_Class"
        assert {
            "PanelCOMP Class",
            "Panel Component",
            "Panel Values",
            "COMP Class",
            "panel",
            "PanelValue Class",
            "panelRoot",
            "panelChildren",
            "x",
            "y",
            "width",
            "height",
            "marginX",
            "marginY",
            "marginWidth",
            "marginHeight",
            "dropReady",
            "panelParent(n)",
            "interactMouse()",
            "interactTouch()",
            "interactClear()",
            "interactStatus()",
            "locateMouse()",
            "locateMouseUV()",
            "setFocus()",
            "inside",
            "insideu",
            "insidev",
            "state",
            "u",
            "v",
            "pixels",
            "screen",
            "quiet",
            "aux",
            "focusselect",
        }.issubset(set(panelcomp_class["key_concepts"]))
        assert {"containerCOMP", "buttonCOMP", "sliderCOMP"}.issubset(panelcomp_class["covered_operators"])
        assert any("first primary" in note for note in panelcomp_class["guidance"])
        assert any("normalized" in note and "pixel" in note for note in panelcomp_class["guidance"])

    def test_panel_python_class_articles_cover_panelvalue_and_core_panel_comp_click_apis(self) -> None:
        expected_ids = {
            "panelvalue_class",
            "buttoncomp_class",
            "slidercomp_class",
            "containercomp_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        panelvalue = article_cards["panelvalue_class"]
        assert panelvalue["source_url"] == "https://docs.derivative.ca/PanelValue_Class"
        assert {
            "PanelValue Class",
            "Panel Value",
            "Panel Execute DAT",
            "panel member",
            "name",
            "owner",
            "val",
            "valid",
            "Casting to a Value",
            "eval() unnecessary",
            "set() unnecessary",
            "parameter expression",
            "numeric expression",
        }.issubset(set(panelvalue["key_concepts"]))
        assert {"panelexecuteDAT", "panelCHOP", "buttonCOMP", "sliderCOMP", "containerCOMP"}.issubset(
            panelvalue["covered_operators"]
        )
        assert any("valid" in note and "deleted" in note for note in panelvalue["guidance"])
        assert any("eval()" in note and "set()" in note for note in panelvalue["guidance"])

        button_class = article_cards["buttoncomp_class"]
        assert button_class["source_url"] == "https://docs.derivative.ca/ButtonCOMP_Class"
        assert {
            "buttonCOMP Class",
            "Button COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "click()",
            "val",
            "clickCount",
            "force",
            "left",
            "middle",
            "right",
            "default left mouse button",
            "disabled",
        }.issubset(set(button_class["key_concepts"]))
        assert {"buttonCOMP"}.issubset(button_class["covered_operators"])
        assert any("retain" in note and "state" in note for note in button_class["guidance"])
        assert any("disabled" in note and "force" in note for note in button_class["guidance"])

        slider_class = article_cards["slidercomp_class"]
        assert slider_class["source_url"] == "https://docs.derivative.ca/SliderCOMP_Class"
        assert {
            "sliderCOMP Class",
            "Slider COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "click()",
            "uOrV",
            "v",
            "normalized coordinates",
            "U slider",
            "V slider",
            "UV slider",
            "vOnly",
            "clickCount",
            "force",
            "left",
            "middle",
            "right",
        }.issubset(set(slider_class["key_concepts"]))
        assert {"sliderCOMP"}.issubset(slider_class["covered_operators"])
        assert any("one value" in note and "primary coordinate" in note for note in slider_class["guidance"])
        assert any("vOnly" in note and "UV slider" in note for note in slider_class["guidance"])

        container_class = article_cards["containercomp_class"]
        assert container_class["source_url"] == "https://docs.derivative.ca/ContainerCOMP_Class"
        assert {
            "containerCOMP Class",
            "Container COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "click()",
            "clickChild()",
            "u",
            "v",
            "childIndex",
            "clickCount",
            "force",
            "left",
            "middle",
            "right",
            "group",
            "Button COMP",
            "radio buttons",
            "disabled",
        }.issubset(set(container_class["key_concepts"]))
        assert {"containerCOMP", "buttonCOMP"}.issubset(container_class["covered_operators"])
        assert any("specific location" in note for note in container_class["guidance"])
        assert any("radio buttons" in note for note in container_class["guidance"])

    def test_panel_python_class_articles_cover_list_table_text_and_parameter_comp_apis(self) -> None:
        expected_ids = {
            "listcomp_class",
            "tablecomp_class",
            "textcomp_class",
            "parametercomp_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        list_class = article_cards["listcomp_class"]
        assert list_class["source_url"] == "https://docs.derivative.ca/ListCOMP_Class"
        assert {
            "listCOMP Class",
            "List COMP",
            "COMP class",
            "PanelCOMP Class",
            "ListAttribute",
            "ListAttributes",
            "attribs",
            "colAttribs",
            "rowAttribs",
            "cellAttribs",
            "displayAttribs",
            "focusCol",
            "focusRow",
            "radioCol",
            "radioRow",
            "rolloverCol",
            "rolloverRow",
            "selectCol",
            "selectRow",
            "selectionBorderColor",
            "selectionColor",
            "selections",
            "dragRow",
            "dragCol",
            "dropRow",
            "dropCol",
            "scroll()",
            "setKeyboardFocus()",
            "reset()",
            "Callbacks",
            "onInitCell",
            "onSelect",
            "onEdit",
            "onDropGetAccept",
        }.issubset(set(list_class["key_concepts"]))
        assert {"listCOMP"}.issubset(list_class["covered_operators"])
        assert any("attribute priority" in note for note in list_class["guidance"])
        assert any("callbacks" in note and "Reset" in note for note in list_class["guidance"])

        table_class = article_cards["tablecomp_class"]
        assert table_class["source_url"] == "https://docs.derivative.ca/TableCOMP_Class"
        assert {
            "tableCOMP Class",
            "Table COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "getRowFromID()",
            "getColFromID()",
            "getCellID()",
            "click()",
            "clickID()",
            "setKeyboardFocus()",
            "celloverid",
            "cellfocusid",
            "row",
            "col",
            "clickCount",
            "force",
            "left",
            "middle",
            "right",
            "default left mouse button",
        }.issubset(set(table_class["key_concepts"]))
        assert {"tableCOMP"}.issubset(table_class["covered_operators"])
        assert any(
            "cell ID" in note and "row" in note and "column" in note for note in table_class["guidance"]
        )
        assert any("disabled" in note and "force" in note for note in table_class["guidance"])

        text_class = article_cards["textcomp_class"]
        assert text_class["source_url"] == "https://docs.derivative.ca/TextCOMP_Class"
        assert {
            "textCOMP Class",
            "Text COMP",
            "COMP class",
            "editText",
            "selectedText",
            "textHeight",
            "textWidth",
            "evalTextSize()",
            "formatText()",
            "setCursorPosUV()",
            "setKeyboardFocus()",
            "editing",
            "selectAll",
        }.issubset(set(text_class["key_concepts"]))
        assert {"textCOMP"}.issubset(text_class["covered_operators"])
        assert any("textHeight" in note and "textWidth" in note for note in text_class["guidance"])
        assert any("keyboard focus" in note and "selectAll" in note for note in text_class["guidance"])

        parameter_class = article_cards["parametercomp_class"]
        assert parameter_class["source_url"] == "https://docs.derivative.ca/ParameterCOMP_Class"
        assert {
            "parameterCOMP Class",
            "Parameter COMP",
            "COMP class",
            "PanelCOMP Class",
            "minWidth",
            "parameter dialog",
            "No operator specific methods",
        }.issubset(set(parameter_class["key_concepts"]))
        assert {"parameterCOMP"}.issubset(parameter_class["covered_operators"])
        assert any("minimum width" in note and "scaling" in note for note in parameter_class["guidance"])
        assert any("inherits PanelCOMP" in note for note in parameter_class["guidance"])

    def test_panel_python_class_articles_cover_opviewer_select_widget_and_window_comp_apis(self) -> None:
        expected_ids = {
            "opviewercomp_class",
            "selectcomp_class",
            "widgetcomp_class",
            "windowcomp_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        opviewer_class = article_cards["opviewercomp_class"]
        assert opviewer_class["source_url"] == "https://docs.derivative.ca/OpviewerCOMP_Class"
        assert {
            "opviewerCOMP Class",
            "OP Viewer COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "isViewable()",
            "path",
            "recursion issues",
            "operator argument",
            "inherited PanelCOMP",
        }.issubset(set(opviewer_class["key_concepts"]))
        assert {"opviewerCOMP"}.issubset(opviewer_class["covered_operators"])
        assert any(
            "OpviewerCOMP_Class" in note and "OPViewerCOMP_Class" in note
            for note in opviewer_class["guidance"]
        )
        assert any("recursion" in note and "view" in note for note in opviewer_class["guidance"])

        select_class = article_cards["selectcomp_class"]
        assert select_class["source_url"] == "https://docs.derivative.ca/SelectCOMP_Class"
        assert {
            "selectCOMP Class",
            "Select COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "No operator specific methods",
            "inherited PanelCOMP",
            "panel",
            "PanelValue Class",
        }.issubset(set(select_class["key_concepts"]))
        assert {"selectCOMP"}.issubset(select_class["covered_operators"])
        assert any("not document operator-specific" in note for note in select_class["guidance"])
        assert any("inherited PanelCOMP" in note for note in select_class["guidance"])

        widget_class = article_cards["widgetcomp_class"]
        assert widget_class["source_url"] == "https://docs.derivative.ca/WidgetCOMP_Class"
        assert {
            "widgetCOMP Class",
            "Widget COMP",
            "COMP class",
            "PanelCOMP Class",
            "No operator specific members",
            "click()",
            "clickChild()",
            "u",
            "v",
            "childIndex",
            "clickCount",
            "force",
            "left",
            "middle",
            "right",
            "group",
            "Button COMP",
            "radio buttons",
            "disabled",
            "default left mouse button",
        }.issubset(set(widget_class["key_concepts"]))
        assert {"widgetCOMP", "buttonCOMP"}.issubset(widget_class["covered_operators"])
        assert any("specific location" in note for note in widget_class["guidance"])
        assert any("radio buttons" in note for note in widget_class["guidance"])

        window_class = article_cards["windowcomp_class"]
        assert window_class["source_url"] == "https://docs.derivative.ca/WindowCOMP_Class"
        assert {
            "windowCOMP Class",
            "Window COMP",
            "COMP class",
            "scalingMonitorIndex",
            "isBorders",
            "isFill",
            "isOpen",
            "width",
            "height",
            "x",
            "y",
            "contentX",
            "contentY",
            "contentWidth",
            "contentHeight",
            "DPI Scaling",
            "borders",
            "setForeground()",
            "foreground process",
            "process priority",
        }.issubset(set(window_class["key_concepts"]))
        assert {"windowCOMP"}.issubset(window_class["covered_operators"])
        assert any("DPI Scaling" in note and "points or pixels" in note for note in window_class["guidance"])
        assert any(
            "foreground process" in note and "setForeground()" in note for note in window_class["guidance"]
        )

    def test_comp_python_class_articles_cover_base_and_object_comp_foundation_apis(self) -> None:
        expected_ids = {
            "basecomp_class",
            "objectcomp_class",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        base_class = article_cards["basecomp_class"]
        assert base_class["source_url"] == "https://docs.derivative.ca/BaseCOMP_Class"
        assert {
            "baseCOMP Class",
            "Base COMP",
            "COMP class",
            "No operator specific members",
            "No operator specific methods",
            "inherited COMP",
            "extensions",
            "children",
            "create()",
            "copy()",
            "copyOPs()",
            "layout()",
            "findChildren()",
            "progressiveUnload()",
            "loadTox()",
            "save()",
            "appendCustomPage()",
        }.issubset(set(base_class["key_concepts"]))
        assert {"baseCOMP"}.issubset(base_class["covered_operators"])
        assert any("not document operator-specific" in note for note in base_class["guidance"])
        assert any("inherited COMP" in note and "create()" in note for note in base_class["guidance"])

        object_class = article_cards["objectcomp_class"]
        assert object_class["source_url"] == "https://docs.derivative.ca/ObjectCOMP_Class"
        assert {
            "ObjectCOMP Class",
            "Object COMP",
            "COMP class",
            "parent class",
            "localTransform",
            "worldTransform",
            "transform()",
            "setTransform()",
            "preTransform()",
            "setPreTransform()",
            "relativeTransform()",
            "importABC()",
            "importFBX()",
            "Matrix",
            "Alembic",
            "FBX",
            "lights",
            "cameras",
            "mergeGeometry",
            "gpuDeform",
        }.issubset(set(object_class["key_concepts"]))
        assert {"objectCOMP", "cameraCOMP", "geometryCOMP", "lightCOMP"}.issubset(
            object_class["covered_operators"]
        )
        assert any("localTransform" in note and "worldTransform" in note for note in object_class["guidance"])
        assert any("relativeTransform" in note and "space" in note for note in object_class["guidance"])
        assert any("mergeGeometry" in note and "gpuDeform" in note for note in object_class["guidance"])

    def test_glsl_runtime_and_texture_articles_cover_shader_debugging_and_sampling_workflows(self) -> None:
        expected_ids = {
            "shader",
            "compute_shader",
            "debugging_crashes_triggered_by_glsl_errors",
            "vulkan",
            "2d_texture_array",
            "3d_texture",
            "texture_sampling_parameters",
            "texture_coordinates_and_texture_sampling",
            "texture_extend_modes",
            "texture_filtering",
            "phong_mat_shader_resource_usage",
        }
        article_cards = {card["article_id"]: card for _, card in _load_all_json("articles")}

        assert expected_ids.issubset(article_cards)

        shader = article_cards["shader"]
        assert shader["source_url"] == "https://docs.derivative.ca/Shader"
        assert {
            "OpenGL (pre-2022)",
            "Vulkan (2022-)",
            "Text DATs",
            "GLSL Material",
            "GLSL TOP",
            "Vertex Shader",
            "Pixel Shader",
            "Compute Shader",
            "Geometry Shaders are now obsolete",
        }.issubset(set(shader["key_concepts"]))
        assert {"GLSL", "TOP", "MAT"}.issubset(shader["families"])

        compute_shader = article_cards["compute_shader"]
        assert compute_shader["source_url"] == "https://docs.derivative.ca/Compute_Shader"
        assert {
            "1000s of very light-weight threads",
            "arbitrary locations",
            "GLSL 4.30",
            "GLSL TOP",
            "Compute Shader",
        }.issubset(set(compute_shader["key_concepts"]))
        assert any("pixel shader" in note for note in compute_shader["guidance"])

        debugging = article_cards["debugging_crashes_triggered_by_glsl_errors"]
        assert (
            debugging["source_url"] == "https://docs.derivative.ca/Debugging_crashes_triggered_by_GLSL_errors"
        )
        assert {
            "out of bounds array access",
            "sampler arrays",
            "uniform arrays",
            "TD_NUM_*_INPUTS",
            "TOUCH_ROBUST_BUFFER_ACCESS=1",
            "TOUCH_ENABLE_NV_AFTERMATH=1",
        }.issubset(set(debugging["key_concepts"]))
        assert any("Robust Buffer Access" in note for note in debugging["guidance"])

        vulkan = article_cards["vulkan"]
        assert vulkan["source_url"] == "https://docs.derivative.ca/Vulkan"
        assert {
            "Vulkan",
            "MoltenVK",
            "Metal",
            "lower driver overhead",
            "Compute Shaders",
            "Geometry Shaders",
        }.issubset(set(vulkan["key_concepts"]))
        assert {"GPU", "TOP", "GLSL"}.issubset(vulkan["families"])

        texture_array = article_cards["2d_texture_array"]
        assert texture_array["source_url"] == "https://docs.derivative.ca/2D_Texture_Array"
        assert {
            "GL_EXT_texture_array",
            "sampler2DArray",
            "texture2DArray()",
            "non-normalized w coordinate",
            "mipmapped",
            "Texture 3D TOP",
            "GLSL TOP",
        }.issubset(set(texture_array["key_concepts"]))
        assert {"texture3dTOP", "glslTOP"}.issubset(texture_array["covered_operators"])

        texture_3d = article_cards["3d_texture"]
        assert texture_3d["source_url"] == "https://docs.derivative.ca/3D_Texture"
        assert {
            "normalized u/v/w",
            "blend between slices",
            "0.5 / NumberOfSlices",
            "2025.30000+",
            "POffset",
            "Texture 3D TOP",
            "Time Machine TOP",
        }.issubset(set(texture_3d["key_concepts"]))
        assert {"texture3dTOP", "timemachineTOP"}.issubset(texture_3d["covered_operators"])

        resource_usage = article_cards["phong_mat_shader_resource_usage"]
        assert resource_usage["source_url"] == "https://docs.derivative.ca/Phong_MAT_Shader_Resource_Usage"
        assert {
            "per-object resource limits",
            "Light Mask",
            "$SYS_GFX_GLSL_MAX_VARYINGS",
            "varyings",
            "normal mapping",
            "shadow mapped",
            "projection mapped",
            "Render Pass TOP",
            "Add TOP",
            "uniforms",
        }.issubset(set(resource_usage["key_concepts"]))
        assert {"MAT", "GLSL", "GPU", "RENDER"}.issubset(resource_usage["families"])
        assert {"phongMAT", "glslMAT", "renderpassTOP", "addTOP"}.issubset(
            resource_usage["covered_operators"]
        )
        assert any("Light Mask" in note for note in resource_usage["guidance"])
        assert any("Render Pass TOP" in note and "Add TOP" in note for note in resource_usage["guidance"])

        sampling = article_cards["texture_sampling_parameters"]
        assert sampling["source_url"] == "https://docs.derivative.ca/Texture_Sampling_Parameters"
        assert {
            "extendu",
            "extendv",
            "extendw",
            "filter",
            "anisotropy",
            "coord",
            "coordinterp",
            "+ button",
        }.issubset(set(sampling["key_concepts"]))
        assert {"MAT", "TOP", "PARAMETER"}.issubset(sampling["families"])

        coords = article_cards["texture_coordinates_and_texture_sampling"]
        assert coords["source_url"] == "https://docs.derivative.ca/Texture_Coordinates_and_Texture_Sampling"
        assert {
            "uv",
            "Texture SOP",
            "Tube",
            "Grid",
            "Torus",
            "Sphere",
            "texels",
            "Nearest",
            "Linear",
        }.issubset(set(coords["key_concepts"]))
        assert {"textureSOP", "geometryCOMP"}.issubset(coords["covered_operators"])

        extend_modes = article_cards["texture_extend_modes"]
        assert extend_modes["source_url"] == "https://docs.derivative.ca/Texture_Extend_Modes"
        assert {"Hold", "Zero", "Repeat", "Mirror", "[0,1]", "U", "V", "W"}.issubset(
            set(extend_modes["key_concepts"])
        )
        assert any("outside" in note for note in extend_modes["guidance"])

        filtering = article_cards["texture_filtering"]
        assert filtering["source_url"] == "https://docs.derivative.ca/Texture_Filtering"
        assert {
            "Nearest",
            "Linear",
            "Mipmap Linear",
            "Input Smoothness",
            "Viewer Smoothness",
            "Filter Type",
            "Anisotropic Filtering",
        }.issubset(set(filtering["key_concepts"]))
        assert any("Viewer Smoothness" in note for note in filtering["guidance"])
