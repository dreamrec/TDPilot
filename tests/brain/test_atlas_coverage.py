from __future__ import annotations

from pathlib import Path

from td_mcp.brain.atlas_audit import audit_brain_atlas
from td_mcp.brain.planner import _PROFILE_SPECS
from td_mcp.knowledge.card_index import CardIndex

_COMP_UTILITY_REVIEWED_2026_06_18 = {
    "animationCOMP",
    "annotateCOMP",
    "blendCOMP",
    "buildalistCOMP",
    "listCOMP",
    "nullCOMP",
    "opviewerCOMP",
    "parameterCOMP",
    "replicatorCOMP",
    "timeCOMP",
}

_COMP_SCENE_RUNTIME_REVIEWED_2026_06_18 = {
    "actorCOMP",
    "boneCOMP",
    "bulletsolverCOMP",
    "constraintCOMP",
    "engineCOMP",
    "fbxCOMP",
    "geotextCOMP",
    "nvidiaflexsolverCOMP",
    "nvidiaflowemitterCOMP",
    "usdCOMP",
}

_COMP_LIGHT_FORCE_SHARED_REVIEWED_2026_06_18 = {
    "ambientlightCOMP",
    "camerablendCOMP",
    "environmentlightCOMP",
    "forceCOMP",
    "handleCOMP",
    "impulseforceCOMP",
    "lightCOMP",
    "sharedmeminCOMP",
    "sharedmemoutCOMP",
}

_COMP_REVIEWED_2026_06_18 = (
    _COMP_UTILITY_REVIEWED_2026_06_18
    | _COMP_SCENE_RUNTIME_REVIEWED_2026_06_18
    | _COMP_LIGHT_FORCE_SHARED_REVIEWED_2026_06_18
)

_CHOP_ROUTING_REVIEWED_2026_06_18 = {
    "deleteCHOP",
    "joinCHOP",
    "renameCHOP",
    "reorderCHOP",
    "replaceCHOP",
    "resampleCHOP",
    "shuffleCHOP",
    "sortCHOP",
    "switchCHOP",
    "trimCHOP",
}

_CHOP_AUDIO_REVIEWED_2026_06_18 = {
    "audiobandeqCHOP",
    "audiobinauralCHOP",
    "audiodeviceinCHOP",
    "audiodeviceoutCHOP",
    "audiodynamicsCHOP",
    "audiofileoutCHOP",
    "audiofilterCHOP",
    "audiomovieCHOP",
    "audiondiCHOP",
    "audiooscillatorCHOP",
}

_CHOP_AUDIO_TAIL_REVIEWED_2026_06_18 = {
    "audioparaeqCHOP",
    "audioplayCHOP",
    "audiorenderCHOP",
    "audiospectrumCHOP",
    "audiostreaminCHOP",
    "audiostreamoutCHOP",
    "audiovstCHOP",
    "audiowebrenderCHOP",
}

_CHOP_TRACKING_DEVICE_REVIEWED_2026_06_18 = {
    "blacktraxCHOP",
    "blobtrackCHOP",
    "bodytrackCHOP",
    "facetrackCHOP",
    "gestureCHOP",
    "hokuyoCHOP",
    "joystickCHOP",
    "kinectCHOP",
    "kinectazureCHOP",
    "leapmotionCHOP",
}

_CHOP_PROTOCOL_TIMECODE_REVIEWED_2026_06_18 = {
    "dmxinCHOP",
    "dmxoutCHOP",
    "freedinCHOP",
    "freedoutCHOP",
    "laserCHOP",
    "laserdeviceCHOP",
    "ltcinCHOP",
    "ltcoutCHOP",
    "midiinCHOP",
    "midioutCHOP",
}

_CHOP_CORE_MOTION_EDIT_REVIEWED_2026_06_18 = {
    "attributeCHOP",
    "bulletsolverCHOP",
    "clipCHOP",
    "clipblenderCHOP",
    "clockCHOP",
    "compositeCHOP",
    "copyCHOP",
    "countCHOP",
    "cplusplusCHOP",
    "crossCHOP",
}

_CHOP_TIMING_FILE_CONTROL_REVIEWED_2026_06_18 = {
    "cycleCHOP",
    "dattoCHOP",
    "delayCHOP",
    "envelopeCHOP",
    "eventCHOP",
    "expressionCHOP",
    "extendCHOP",
    "fanCHOP",
    "feedbackCHOP",
    "fileinCHOP",
}

_CHOP_FILE_FILTER_FUNCTION_REVIEWED_2026_06_18 = {
    "fileoutCHOP",
    "filterCHOP",
    "functionCHOP",
    "handleCHOP",
    "hogCHOP",
    "holdCHOP",
    "importselectCHOP",
    "inCHOP",
    "infoCHOP",
    "interpolateCHOP",
}

_CHOP_IK_INPUT_LOGIC_REVIEWED_2026_06_18 = {
    "inversecurveCHOP",
    "inversekinCHOP",
    "keyboardinCHOP",
    "keyframeCHOP",
    "lagCHOP",
    "leuzerod4CHOP",
    "lfoCHOP",
    "limitCHOP",
    "logicCHOP",
    "lookupCHOP",
}

_CHOP_MERGE_DEVICE_OBJECT_REVIEWED_2026_06_18 = {
    "mergeCHOP",
    "midiinmapCHOP",
    "mosysCHOP",
    "mouseinCHOP",
    "mouseoutCHOP",
    "ncamCHOP",
    "noiseCHOP",
    "oakdeviceCHOP",
    "oakselectCHOP",
    "objectCHOP",
}

_CHOP_VR_OSC_OUTPUT_REVIEWED_2026_06_18 = {
    "oculusaudioCHOP",
    "oculusriftCHOP",
    "openvrCHOP",
    "optitrackinCHOP",
    "oscinCHOP",
    "oscoutCHOP",
    "outCHOP",
    "overrideCHOP",
    "pangolinCHOP",
    "pantiltCHOP",
}

_CHOP_PARAMETER_PATTERN_RECORD_REVIEWED_2026_06_18 = {
    "parameterCHOP",
    "patternCHOP",
    "performCHOP",
    "phaserCHOP",
    "pipeinCHOP",
    "pipeoutCHOP",
    "posistagenetCHOP",
    "pulseCHOP",
    "recordCHOP",
    "renderpickCHOP",
}

_CHOP_SCRIPT_SERIAL_SHARED_MEMORY_REVIEWED_2026_06_18 = {
    "renderstreaminCHOP",
    "scriptCHOP",
    "scurveCHOP",
    "sequencerCHOP",
    "serialCHOP",
    "sharedmeminCHOP",
    "sharedmemoutCHOP",
    "shiftCHOP",
    "slopeCHOP",
    "soptoCHOP",
}

_CHOP_SPEED_STYPE_SYNC_REVIEWED_2026_06_18 = {
    "speedCHOP",
    "spliceCHOP",
    "springCHOP",
    "st2110deviceCHOP",
    "stretchCHOP",
    "stypeinCHOP",
    "stypeoutCHOP",
    "syncinCHOP",
    "syncoutCHOP",
    "tabletCHOP",
}

_CHOP_TIME_TOUCH_TRAIL_TRANSFORM_REVIEWED_2026_06_18 = {
    "timecodeCHOP",
    "timelineCHOP",
    "timerCHOP",
    "timesliceCHOP",
    "toptoCHOP",
    "touchinCHOP",
    "touchoutCHOP",
    "trailCHOP",
    "transformCHOP",
    "transformxyzCHOP",
    "triggerCHOP",
    "warpCHOP",
    "waveCHOP",
    "wrnchaiCHOP",
    "zedCHOP",
}

_CHOP_REVIEWED_2026_06_18 = (
    _CHOP_ROUTING_REVIEWED_2026_06_18
    | _CHOP_AUDIO_REVIEWED_2026_06_18
    | _CHOP_AUDIO_TAIL_REVIEWED_2026_06_18
    | _CHOP_TRACKING_DEVICE_REVIEWED_2026_06_18
    | _CHOP_PROTOCOL_TIMECODE_REVIEWED_2026_06_18
    | _CHOP_CORE_MOTION_EDIT_REVIEWED_2026_06_18
    | _CHOP_TIMING_FILE_CONTROL_REVIEWED_2026_06_18
    | _CHOP_FILE_FILTER_FUNCTION_REVIEWED_2026_06_18
    | _CHOP_IK_INPUT_LOGIC_REVIEWED_2026_06_18
    | _CHOP_MERGE_DEVICE_OBJECT_REVIEWED_2026_06_18
    | _CHOP_VR_OSC_OUTPUT_REVIEWED_2026_06_18
    | _CHOP_PARAMETER_PATTERN_RECORD_REVIEWED_2026_06_18
    | _CHOP_SCRIPT_SERIAL_SHARED_MEMORY_REVIEWED_2026_06_18
    | _CHOP_SPEED_STYPE_SYNC_REVIEWED_2026_06_18
    | _CHOP_TIME_TOUCH_TRAIL_TRANSFORM_REVIEWED_2026_06_18
)

_TOP_IMAGE_COLOR_CACHE_REVIEWED_2026_06_18 = {
    "addTOP",
    "analyzeTOP",
    "antialiasTOP",
    "blobtrackTOP",
    "bloomTOP",
    "blurTOP",
    "cacheTOP",
    "cacheselectTOP",
    "channelmixTOP",
    "choptoTOP",
    "chromakeyTOP",
    "circleTOP",
    "convolveTOP",
    "cornerpinTOP",
    "cplusplusTOP",
    "cropTOP",
    "crossTOP",
    "cubemapTOP",
    "cudaTOP",
    "depthTOP",
}

_TOP_COMPOSITE_IO_GPU_LAYER_REVIEWED_2026_06_18 = {
    "differenceTOP",
    "directdisplayoutTOP",
    "directxinTOP",
    "directxoutTOP",
    "displaceTOP",
    "edgeTOP",
    "embossTOP",
    "fitTOP",
    "flipTOP",
    "functionTOP",
    "hsvadjustTOP",
    "hsvtorgbTOP",
    "importselectTOP",
    "inTOP",
    "insideTOP",
    "kinectTOP",
    "kinectazureTOP",
    "kinectazureselectTOP",
    "layerTOP",
    "layermixTOP",
}

_TOP_LAYOUT_MEDIA_TRACKING_REVIEWED_2026_06_18 = {
    "layoutTOP",
    "leapmotionTOP",
    "lensdistortTOP",
    "limitTOP",
    "lookupTOP",
    "lumablurTOP",
    "lumalevelTOP",
    "mathTOP",
    "matteTOP",
    "mirrorTOP",
    "monochromeTOP",
    "mosysTOP",
    "moviefileinTOP",
    "moviefileoutTOP",
    "mpcdiTOP",
    "multiplyTOP",
    "ncamTOP",
    "ndiinTOP",
    "ndioutTOP",
    "normalmapTOP",
}

_TOP_DEVICE_VR_OUTPUT_REVIEWED_2026_06_18 = {
    "notchTOP",
    "nvidiabackgroundTOP",
    "nvidiadenoiseTOP",
    "nvidiaflexTOP",
    "nvidiaflowTOP",
    "nvidiartxvideoTOP",
    "nvidiaupscalerTOP",
    "oakselectTOP",
    "oculusriftTOP",
    "opencolorioTOP",
    "openvrTOP",
    "opticalflowTOP",
    "opviewerTOP",
    "orbbecTOP",
    "orbbecselectTOP",
    "ousterTOP",
    "ousterselectTOP",
    "outTOP",
    "outsideTOP",
    "overTOP",
}

_TOP_POINT_RENDER_REMAP_REVIEWED_2026_06_18 = {
    "packTOP",
    "photoshopinTOP",
    "pointfileinTOP",
    "pointfileselectTOP",
    "pointtransformTOP",
    "prefiltermapTOP",
    "projectionTOP",
    "rampTOP",
    "realsenseTOP",
    "rectangleTOP",
    "remapTOP",
    "renderpassTOP",
    "renderselectTOP",
    "renderstreaminTOP",
    "renderstreamoutTOP",
    "reorderTOP",
    "resolutionTOP",
    "rgbkeyTOP",
    "rgbtohsvTOP",
    "scalabledisplayTOP",
}

_TOP_SCREEN_SHARED_STYPE_TEXTURE_REVIEWED_2026_06_18 = {
    "screenTOP",
    "screengrabTOP",
    "scriptTOP",
    "sharedmeminTOP",
    "sharedmemoutTOP",
    "sickTOP",
    "simplerenderTOP",
    "slopeTOP",
    "spectrumTOP",
    "ssaoTOP",
    "st2110inTOP",
    "st2110outTOP",
    "stypeTOP",
    "substanceTOP",
    "substanceselectTOP",
    "subtractTOP",
    "syphonspoutinTOP",
    "syphonspoutoutTOP",
    "textTOP",
    "texture3dTOP",
}

_TOP_FINAL_DEVICE_WEB_ZED_REVIEWED_2026_06_18 = {
    "thresholdTOP",
    "tileTOP",
    "timemachineTOP",
    "tonemapTOP",
    "touchinTOP",
    "touchoutTOP",
    "transformTOP",
    "underTOP",
    "videodeviceinTOP",
    "videodeviceoutTOP",
    "videostreaminTOP",
    "videostreamoutTOP",
    "viosoTOP",
    "webrenderTOP",
    "zedTOP",
    "zedselectTOP",
}

_TOP_REVIEWED_2026_06_18 = (
    _TOP_IMAGE_COLOR_CACHE_REVIEWED_2026_06_18
    | _TOP_COMPOSITE_IO_GPU_LAYER_REVIEWED_2026_06_18
    | _TOP_LAYOUT_MEDIA_TRACKING_REVIEWED_2026_06_18
    | _TOP_DEVICE_VR_OUTPUT_REVIEWED_2026_06_18
    | _TOP_POINT_RENDER_REMAP_REVIEWED_2026_06_18
    | _TOP_SCREEN_SHARED_STYPE_TEXTURE_REVIEWED_2026_06_18
    | _TOP_FINAL_DEVICE_WEB_ZED_REVIEWED_2026_06_18
)

_SOP_FOUNDATION_CAPTURE_REVIEWED_2026_06_18 = {
    "addSOP",
    "alembicSOP",
    "alignSOP",
    "armSOP",
    "attributeSOP",
    "attributecreateSOP",
    "basisSOP",
    "blendSOP",
    "bonegroupSOP",
    "booleanSOP",
    "boxSOP",
    "bridgeSOP",
    "cacheSOP",
    "capSOP",
    "captureSOP",
    "captureregionSOP",
    "carveSOP",
    "choptoSOP",
    "circleSOP",
    "claySOP",
}

_SOP_CURVE_DEFORM_FILE_REVIEWED_2026_06_18 = {
    "clipSOP",
    "convertSOP",
    "copySOP",
    "cplusplusSOP",
    "creepSOP",
    "curveclaySOP",
    "curvesectSOP",
    "dattoSOP",
    "deformSOP",
    "deleteSOP",
    "divideSOP",
    "extrudeSOP",
    "facetSOP",
    "facetrackSOP",
    "fileinSOP",
    "filletSOP",
    "fitSOP",
    "forceSOP",
    "fractalSOP",
    "gridSOP",
}

_SOP_GROUP_IMPORT_FIELD_REVIEWED_2026_06_18 = {
    "groupSOP",
    "holeSOP",
    "importselectSOP",
    "inSOP",
    "inversecurveSOP",
    "isosurfaceSOP",
    "joinSOP",
    "jointSOP",
    "kinectSOP",
    "latticeSOP",
    "limitSOP",
    "lineSOP",
    "linethickSOP",
    "lodSOP",
    "lsystemSOP",
    "magnetSOP",
    "materialSOP",
    "metaballSOP",
    "modelSOP",
    "noiseSOP",
}

_SOP_OBJECT_POLY_RAY_REVIEWED_2026_06_18 = {
    "objectmergeSOP",
    "oculusriftSOP",
    "openvrSOP",
    "outSOP",
    "particleSOP",
    "pointSOP",
    "polyloftSOP",
    "polypatchSOP",
    "polyreduceSOP",
    "polysplineSOP",
    "polystitchSOP",
    "primitiveSOP",
    "profileSOP",
    "projectSOP",
    "railsSOP",
    "rasterSOP",
    "raySOP",
    "rectangleSOP",
    "refineSOP",
    "resampleSOP",
}

_SOP_REVOLVE_SCRIPT_SWEEP_TRAIL_REVIEWED_2026_06_18 = {
    "revolveSOP",
    "scriptSOP",
    "selectSOP",
    "sequenceblendSOP",
    "skinSOP",
    "sortSOP",
    "sphereSOP",
    "springSOP",
    "sprinkleSOP",
    "spriteSOP",
    "stitchSOP",
    "subdivideSOP",
    "superquadSOP",
    "surfsectSOP",
    "sweepSOP",
    "textSOP",
    "textureSOP",
    "torusSOP",
    "traceSOP",
    "trailSOP",
}

_SOP_TRANSFORM_TRIM_ZED_REVIEWED_2026_06_18 = {
    "transformSOP",
    "trimSOP",
    "tristripSOP",
    "tubeSOP",
    "twistSOP",
    "vertexSOP",
    "wireframeSOP",
    "zedSOP",
}

_SOP_REVIEWED_2026_06_18 = (
    _SOP_FOUNDATION_CAPTURE_REVIEWED_2026_06_18
    | _SOP_CURVE_DEFORM_FILE_REVIEWED_2026_06_18
    | _SOP_GROUP_IMPORT_FIELD_REVIEWED_2026_06_18
    | _SOP_OBJECT_POLY_RAY_REVIEWED_2026_06_18
    | _SOP_REVOLVE_SCRIPT_SWEEP_TRAIL_REVIEWED_2026_06_18
    | _SOP_TRANSFORM_TRIM_ZED_REVIEWED_2026_06_18
)

_DAT_ARTNET_FILE_REVIEWED_2026_06_18 = {
    "art-netDAT",
    "audiodevicesDAT",
    "chopexecuteDAT",
    "choptoDAT",
    "clipDAT",
    "convertDAT",
    "cplusplusDAT",
    "datexecuteDAT",
    "dmxmapDAT",
    "errorDAT",
    "etherdreamDAT",
    "evaluateDAT",
    "examineDAT",
    "executeDAT",
    "fifoDAT",
    "fileinDAT",
    "fileoutDAT",
    "folderDAT",
    "inDAT",
    "indicesDAT",
}

_DAT_INFO_OUT_REVIEWED_2026_06_18 = {
    "infoDAT",
    "insertDAT",
    "jsonDAT",
    "keyboardinDAT",
    "lookupDAT",
    "mediafileinfoDAT",
    "mergeDAT",
    "midieventDAT",
    "midiinDAT",
    "monitorsDAT",
    "mpcdiDAT",
    "mqttclientDAT",
    "multitouchinDAT",
    "ndiDAT",
    "nullDAT",
    "opexecuteDAT",
    "opfindDAT",
    "oscinDAT",
    "oscoutDAT",
    "outDAT",
}

_DAT_PANEL_SWITCH_REVIEWED_2026_06_18 = {
    "panelexecuteDAT",
    "parameterDAT",
    "parameterexecuteDAT",
    "pargroupexecuteDAT",
    "performDAT",
    "renderpickDAT",
    "reorderDAT",
    "scriptDAT",
    "selectDAT",
    "serialDAT",
    "serialdevicesDAT",
    "socketioDAT",
    "soptoDAT",
    "sortDAT",
    "substituteDAT",
    "switchDAT",
}

_DAT_TABLE_XML_REVIEWED_2026_06_18 = {
    "tableDAT",
    "tcp/ipDAT",
    "touchinDAT",
    "touchoutDAT",
    "transposeDAT",
    "tuioinDAT",
    "udpinDAT",
    "udpoutDAT",
    "udtinDAT",
    "udtoutDAT",
    "videodevicesDAT",
    "webclientDAT",
    "webrtcDAT",
    "webserverDAT",
    "websocketDAT",
    "xmlDAT",
}

_DAT_REVIEWED_2026_06_18 = (
    _DAT_ARTNET_FILE_REVIEWED_2026_06_18
    | _DAT_INFO_OUT_REVIEWED_2026_06_18
    | _DAT_PANEL_SWITCH_REVIEWED_2026_06_18
    | _DAT_TABLE_XML_REVIEWED_2026_06_18
)


def test_brain_profile_operators_have_structured_operator_cards():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    required_ops = sorted(
        {
            concept["op_type"]
            for spec in _PROFILE_SPECS.values()
            for concept in spec.concepts
            if concept.get("op_type")
        }
    )

    missing = [op_type for op_type in required_ops if cards.get_operator(op_type) is None]

    assert missing == []


def test_brain_atlas_audit_reports_profile_operator_coverage():
    report = audit_brain_atlas(Path("."))

    assert report["ok"] is True
    assert report["required_operator_count"] == 28
    assert report["missing_operator_cards"] == []
    assert report["profiles"]["feedback"]["missing_cards"] == []
    assert "levelTOP" in report["profiles"]["feedback"]["operators"]
    assert report["operator_family_counts"]["POP"] >= 10
    assert report["release_freshness"]["structured_latest_build"] >= "2025.32820"


def test_brain_atlas_audit_reports_docsbrain_operator_gaps():
    report = audit_brain_atlas(Path("."))

    coverage = report["docsbrain_operator_coverage"]

    assert coverage["available"] is True
    assert coverage["docsbrain_operator_count"] >= 600
    assert coverage["docsbrain_operator_counts_by_family"]["POP"] >= 100
    assert coverage["structured_operator_card_counts_by_family"]["POP"] >= 25
    assert coverage["missing_operator_card_counts_by_family"]["POP"] > 0
    assert coverage["structured_coverage"] > 0
    assert coverage["missing_operator_card_count"] > 0
    assert coverage["priority_missing_operator_cards"] == []
    assert coverage["deprecated_missing_operator_cards"]
    assert {
        "op_type",
        "display_name",
        "family",
        "docs_url",
    }.issubset(coverage["deprecated_missing_operator_cards"][0])


def test_brain_atlas_audit_separates_deprecated_docsbrain_gaps():
    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]

    deprecated = {item["op_type"] for item in coverage["deprecated_missing_operator_cards"]}
    priority = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert "glslcreatePOP" in deprecated
    assert "glslcreatePOP" not in priority


def test_high_value_pop_and_glsl_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))

    for op_type in [
        "gridPOP",
        "linePOP",
        "spherePOP",
        "transformPOP",
        "mergePOP",
        "selectPOP",
        "switchPOP",
        "attributePOP",
        "feedbackPOP",
        "cachePOP",
        "soptoPOP",
        "choptoPOP",
        "dattoPOP",
        "glslcopyPOP",
        "glslselectPOP",
    ]:
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == "POP"
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["summary"]


def test_audit_ranked_pop_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "analyzePOP": "POP",
        "attributecombinePOP": "POP",
        "attributeconvertPOP": "POP",
        "cacheblendPOP": "POP",
        "cacheselectPOP": "POP",
        "convertPOP": "POP",
        "copyPOP": "POP",
        "cplusplusPOP": "POP",
        "deletePOP": "POP",
        "dmxoutPOP": "POP",
        "extrudePOP": "POP",
        "lookupattributePOP": "POP",
        "lookuptexturePOP": "POP",
        "mathPOP": "POP",
        "normalPOP": "POP",
        "normalizePOP": "POP",
        "polygonizePOP": "POP",
        "renderselectTOP": "TOP",
        "texturemapPOP": "POP",
        "triangulatePOP": "POP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["POP"] >= 45


def test_pop_backbone_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "boxPOP": "POP",
        "dimensionPOP": "POP",
        "fieldPOP": "POP",
        "forceradialPOP": "POP",
        "groupPOP": "POP",
        "inPOP": "POP",
        "limitPOP": "POP",
        "linebreakPOP": "POP",
        "linedividePOP": "POP",
        "linemetricsPOP": "POP",
        "lineresamplePOP": "POP",
        "linesmoothPOP": "POP",
        "linethickPOP": "POP",
        "lookupchannelPOP": "POP",
        "neighborPOP": "POP",
        "outPOP": "POP",
        "patternPOP": "POP",
        "planePOP": "POP",
        "pointPOP": "POP",
        "primitivePOP": "POP",
        "projectionPOP": "POP",
        "proximityPOP": "POP",
        "quantizePOP": "POP",
        "randomPOP": "POP",
        "rayPOP": "POP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["POP"] >= 70


def test_docsbrain_operator_coverage_excludes_docs_articles():
    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert "writeacplusplusPOP" not in priority_ops
    assert "writeaglslTOP" not in priority_ops
    assert "anatomyofaCHOP" not in priority_ops


def test_docsbrain_operator_coverage_treats_replaced_operators_as_deprecated():
    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    deprecated = {item["op_type"] for item in coverage["deprecated_missing_operator_cards"]}
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert "bandeqCHOP" in deprecated
    assert "bandeqCHOP" not in priority_ops


def test_remaining_active_pop_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "accumulatePOP": "POP",
        "alembicinPOP": "POP",
        "alembicoutPOP": "POP",
        "blendPOP": "POP",
        "connectivityPOP": "POP",
        "curvePOP": "POP",
        "dmxfixturePOP": "POP",
        "facetPOP": "POP",
        "fileinPOP": "POP",
        "fileoutPOP": "POP",
        "histogramPOP": "POP",
        "importselectPOP": "POP",
        "oakselectPOP": "POP",
        "phaserPOP": "POP",
        "pointfileinPOP": "POP",
        "rectanglePOP": "POP",
        "rerangePOP": "POP",
        "revolvePOP": "POP",
        "skinPOP": "POP",
        "skindeformPOP": "POP",
        "sortPOP": "POP",
        "sprinklePOP": "POP",
        "subdividePOP": "POP",
        "topologyPOP": "POP",
        "torusPOP": "POP",
        "trailPOP": "POP",
        "trigPOP": "POP",
        "tubePOP": "POP",
        "twistPOP": "POP",
        "zedPOP": "POP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_pop_ops = {
        item["op_type"] for item in coverage["priority_missing_operator_cards"] if item["family"] == "POP"
    }
    deprecated_pop_ops = {
        item["op_type"] for item in coverage["deprecated_missing_operator_cards"] if item["family"] == "POP"
    }

    assert not set(expected).intersection(priority_pop_ops)
    assert priority_pop_ops == set()
    assert deprecated_pop_ops == {"glslcreatePOP"}
    assert coverage["missing_operator_card_counts_by_family"]["POP"] == 1
    assert coverage["structured_operator_card_counts_by_family"]["POP"] >= 101


def test_next_priority_non_pop_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "attributeCHOP": "CHOP",
        "audiorenderCHOP": "CHOP",
        "audiowebrenderCHOP": "CHOP",
        "dattoCHOP": "CHOP",
        "feedbackCHOP": "CHOP",
        "renderpickCHOP": "CHOP",
        "renderstreaminCHOP": "CHOP",
        "poptoDAT": "DAT",
        "selectMAT": "MAT",
        "switchMAT": "MAT",
        "blobtrackTOP": "TOP",
        "cacheTOP": "TOP",
        "cacheselectTOP": "TOP",
        "choptoTOP": "TOP",
        "cplusplusTOP": "TOP",
        "glslmultiTOP": "TOP",
        "hsvtorgbTOP": "TOP",
        "layermixTOP": "TOP",
        "layoutTOP": "TOP",
        "mathTOP": "TOP",
        "moviefileoutTOP": "TOP",
        "normalmapTOP": "TOP",
        "orbbecTOP": "TOP",
        "pointtransformTOP": "TOP",
        "renderpassTOP": "TOP",
        "renderstreaminTOP": "TOP",
        "renderstreamoutTOP": "TOP",
        "rgbtohsvTOP": "TOP",
        "simplerenderTOP": "TOP",
        "texture3dTOP": "TOP",
        "transformTOP": "TOP",
        "webrenderTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 35
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["CHOP"] >= 18
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["MAT"] >= 3
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["DAT"] >= 2


def test_select_bridge_and_dat_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "copyCHOP": "CHOP",
        "importselectCHOP": "CHOP",
        "mergeCHOP": "CHOP",
        "oakselectCHOP": "CHOP",
        "poptoCHOP": "CHOP",
        "soptoCHOP": "CHOP",
        "switchCHOP": "CHOP",
        "toptoCHOP": "CHOP",
        "transformCHOP": "CHOP",
        "transformxyzCHOP": "CHOP",
        "jsonDAT": "DAT",
        "keyboardinDAT": "DAT",
        "renderpickDAT": "DAT",
        "choptoSOP": "SOP",
        "dattoSOP": "SOP",
        "poptoSOP": "SOP",
        "importselectTOP": "TOP",
        "kinectazureselectTOP": "TOP",
        "oakselectTOP": "TOP",
        "orbbecselectTOP": "TOP",
        "ousterselectTOP": "TOP",
        "pointfileselectTOP": "TOP",
        "substanceselectTOP": "TOP",
        "zedselectTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["CHOP"] >= 28
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["DAT"] >= 5
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["SOP"] >= 10
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 45


def test_glsl_sop_and_top_image_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "glslCOMP": "COMP",
        "attributeSOP": "SOP",
        "attributecreateSOP": "SOP",
        "cacheSOP": "SOP",
        "particleSOP": "SOP",
        "addTOP": "TOP",
        "analyzeTOP": "TOP",
        "antialiasTOP": "TOP",
        "bloomTOP": "TOP",
        "blurTOP": "TOP",
        "channelmixTOP": "TOP",
        "chromakeyTOP": "TOP",
        "circleTOP": "TOP",
        "convolveTOP": "TOP",
        "cornerpinTOP": "TOP",
        "cropTOP": "TOP",
        "crossTOP": "TOP",
        "cubemapTOP": "TOP",
        "cudaTOP": "TOP",
        "depthTOP": "TOP",
        "differenceTOP": "TOP",
        "displaceTOP": "TOP",
        "edgeTOP": "TOP",
        "embossTOP": "TOP",
        "fitTOP": "TOP",
        "flipTOP": "TOP",
        "functionTOP": "TOP",
        "hsvadjustTOP": "TOP",
        "inTOP": "TOP",
        "insideTOP": "TOP",
        "layerTOP": "TOP",
        "lensdistortTOP": "TOP",
        "limitTOP": "TOP",
        "lookupTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["COMP"] >= 8
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["SOP"] >= 14
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 74


def test_hardware_io_and_vendor_top_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "directdisplayoutTOP": "TOP",
        "directxinTOP": "TOP",
        "directxoutTOP": "TOP",
        "ndiinTOP": "TOP",
        "ndioutTOP": "TOP",
        "notchTOP": "TOP",
        "nvidiabackgroundTOP": "TOP",
        "nvidiadenoiseTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in (_CHOP_REVIEWED_2026_06_18 | _TOP_REVIEWED_2026_06_18)
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 82


def test_sensor_luma_and_color_top_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "kinectTOP": "TOP",
        "kinectazureTOP": "TOP",
        "leapmotionTOP": "TOP",
        "lumablurTOP": "TOP",
        "lumalevelTOP": "TOP",
        "matteTOP": "TOP",
        "mirrorTOP": "TOP",
        "monochromeTOP": "TOP",
        "multiplyTOP": "TOP",
        "opencolorioTOP": "TOP",
        "opticalflowTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in (_CHOP_REVIEWED_2026_06_18 | _TOP_REVIEWED_2026_06_18)
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 93


def test_tracking_vr_lidar_and_nvidia_top_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "mosysTOP": "TOP",
        "mpcdiTOP": "TOP",
        "ncamTOP": "TOP",
        "nvidiaflexTOP": "TOP",
        "nvidiaflowTOP": "TOP",
        "nvidiaupscalerTOP": "TOP",
        "oculusriftTOP": "TOP",
        "openvrTOP": "TOP",
        "ousterTOP": "TOP",
        "realsenseTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in (_CHOP_REVIEWED_2026_06_18 | _TOP_REVIEWED_2026_06_18)
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 103


def test_output_composite_generator_and_transfer_top_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "nvidiartxvideoTOP": "TOP",
        "outTOP": "TOP",
        "outsideTOP": "TOP",
        "overTOP": "TOP",
        "packTOP": "TOP",
        "photoshopinTOP": "TOP",
        "pointfileinTOP": "TOP",
        "prefiltermapTOP": "TOP",
        "projectionTOP": "TOP",
        "rampTOP": "TOP",
        "rectangleTOP": "TOP",
        "remapTOP": "TOP",
        "reorderTOP": "TOP",
        "resolutionTOP": "TOP",
        "rgbkeyTOP": "TOP",
        "scalabledisplayTOP": "TOP",
        "screenTOP": "TOP",
        "screengrabTOP": "TOP",
        "scriptTOP": "TOP",
        "sharedmeminTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in (_CHOP_REVIEWED_2026_06_18 | _TOP_REVIEWED_2026_06_18)
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 123


def test_network_sensor_effect_and_capture_top_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "sharedmemoutTOP": "TOP",
        "sickTOP": "TOP",
        "slopeTOP": "TOP",
        "spectrumTOP": "TOP",
        "ssaoTOP": "TOP",
        "st2110inTOP": "TOP",
        "st2110outTOP": "TOP",
        "stypeTOP": "TOP",
        "substanceTOP": "TOP",
        "subtractTOP": "TOP",
        "syphonspoutinTOP": "TOP",
        "syphonspoutoutTOP": "TOP",
        "thresholdTOP": "TOP",
        "tileTOP": "TOP",
        "timemachineTOP": "TOP",
        "tonemapTOP": "TOP",
        "touchinTOP": "TOP",
        "touchoutTOP": "TOP",
        "underTOP": "TOP",
        "videodeviceinTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in (_CHOP_REVIEWED_2026_06_18 | _TOP_REVIEWED_2026_06_18)
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    report = audit_brain_atlas(Path("."))
    priority_ops = {
        item["op_type"] for item in report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
    }

    assert not set(expected).intersection(priority_ops)
    assert report["docsbrain_operator_coverage"]["structured_operator_card_counts_by_family"]["TOP"] >= 143


def test_remaining_active_top_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "videodeviceoutTOP": "TOP",
        "videostreaminTOP": "TOP",
        "videostreamoutTOP": "TOP",
        "viosoTOP": "TOP",
        "zedTOP": "TOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in (_CHOP_REVIEWED_2026_06_18 | _TOP_REVIEWED_2026_06_18)
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_top_ops = {
        item["op_type"] for item in coverage["priority_missing_operator_cards"] if item["family"] == "TOP"
    }
    deprecated_top_ops = {
        item["op_type"] for item in coverage["deprecated_missing_operator_cards"] if item["family"] == "TOP"
    }

    assert priority_top_ops == set()
    assert deprecated_top_ops == {"svgTOP"}
    assert coverage["missing_operator_card_counts_by_family"]["TOP"] == 1
    assert coverage["structured_operator_card_counts_by_family"]["TOP"] >= 149


def test_mat_sop_dat_chop_draft_priority_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "abletonlinkCHOP": "CHOP",
        "choptoDAT": "DAT",
        "constantMAT": "MAT",
        "convertSOP": "SOP",
        "copySOP": "SOP",
        "depthMAT": "MAT",
        "importselectSOP": "SOP",
        "inMAT": "MAT",
        "lineMAT": "MAT",
        "mergeDAT": "DAT",
        "nullMAT": "MAT",
        "objectmergeSOP": "SOP",
        "outMAT": "MAT",
        "pbrMAT": "MAT",
        "phongMAT": "MAT",
        "pointspriteMAT": "MAT",
        "selectSOP": "SOP",
        "soptoDAT": "DAT",
        "textureSOP": "SOP",
        "wireframeMAT": "MAT",
    }
    reviewed_today = {
        "constantMAT",
        "depthMAT",
        "inMAT",
        "lineMAT",
        "nullMAT",
        "outMAT",
        "pbrMAT",
        "phongMAT",
        "pointspriteMAT",
        "wireframeMAT",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in reviewed_today
            or op_type in _SOP_REVIEWED_2026_06_18
            or op_type in _DAT_REVIEWED_2026_06_18
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}
    priority_mat_ops = {
        item["op_type"] for item in coverage["priority_missing_operator_cards"] if item["family"] == "MAT"
    }

    assert not set(expected).intersection(priority_ops)
    assert priority_mat_ops == set()
    assert coverage["missing_operator_card_counts_by_family"].get("MAT", 0) == 0
    assert coverage["structured_operator_card_counts_by_family"]["MAT"] >= 13
    assert coverage["structured_operator_card_counts_by_family"]["SOP"] >= 20
    assert coverage["structured_operator_card_counts_by_family"]["DAT"] >= 8
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 29


def test_chop_audio_timing_binding_and_tracking_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "angleCHOP": "CHOP",
        "audiobandeqCHOP": "CHOP",
        "audiobinauralCHOP": "CHOP",
        "audiodeviceinCHOP": "CHOP",
        "audiodeviceoutCHOP": "CHOP",
        "audiodynamicsCHOP": "CHOP",
        "audiofileoutCHOP": "CHOP",
        "audiofilterCHOP": "CHOP",
        "audiomovieCHOP": "CHOP",
        "audiondiCHOP": "CHOP",
        "audiooscillatorCHOP": "CHOP",
        "audioparaeqCHOP": "CHOP",
        "audioplayCHOP": "CHOP",
        "audiospectrumCHOP": "CHOP",
        "audiostreaminCHOP": "CHOP",
        "audiostreamoutCHOP": "CHOP",
        "audiovstCHOP": "CHOP",
        "beatCHOP": "CHOP",
        "bindCHOP": "CHOP",
        "blacktraxCHOP": "CHOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in _CHOP_REVIEWED_2026_06_18 or op_type in _DAT_REVIEWED_2026_06_18
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 49
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 123


def test_chop_control_tracking_clip_dmx_and_expression_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "blendCHOP": "CHOP",
        "blobtrackCHOP": "CHOP",
        "bodytrackCHOP": "CHOP",
        "bulletsolverCHOP": "CHOP",
        "clipCHOP": "CHOP",
        "clipblenderCHOP": "CHOP",
        "clockCHOP": "CHOP",
        "compositeCHOP": "CHOP",
        "countCHOP": "CHOP",
        "cplusplusCHOP": "CHOP",
        "crossCHOP": "CHOP",
        "cycleCHOP": "CHOP",
        "delayCHOP": "CHOP",
        "deleteCHOP": "CHOP",
        "dmxinCHOP": "CHOP",
        "dmxoutCHOP": "CHOP",
        "envelopeCHOP": "CHOP",
        "eventCHOP": "CHOP",
        "expressionCHOP": "CHOP",
        "extendCHOP": "CHOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in _CHOP_REVIEWED_2026_06_18 or op_type in _DAT_REVIEWED_2026_06_18
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 69
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 103


def test_chop_tracking_file_device_kinematics_and_input_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "facetrackCHOP": "CHOP",
        "fanCHOP": "CHOP",
        "fileinCHOP": "CHOP",
        "fileoutCHOP": "CHOP",
        "freedinCHOP": "CHOP",
        "freedoutCHOP": "CHOP",
        "functionCHOP": "CHOP",
        "gestureCHOP": "CHOP",
        "handleCHOP": "CHOP",
        "hogCHOP": "CHOP",
        "hokuyoCHOP": "CHOP",
        "holdCHOP": "CHOP",
        "inCHOP": "CHOP",
        "infoCHOP": "CHOP",
        "interpolateCHOP": "CHOP",
        "inversecurveCHOP": "CHOP",
        "inversekinCHOP": "CHOP",
        "joinCHOP": "CHOP",
        "joystickCHOP": "CHOP",
        "keyboardinCHOP": "CHOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _CHOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 89
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 83


def test_chop_animation_sensor_laser_midi_tracking_and_mouse_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "keyframeCHOP": "CHOP",
        "kinectCHOP": "CHOP",
        "kinectazureCHOP": "CHOP",
        "lagCHOP": "CHOP",
        "laserCHOP": "CHOP",
        "laserdeviceCHOP": "CHOP",
        "leapmotionCHOP": "CHOP",
        "leuzerod4CHOP": "CHOP",
        "limitCHOP": "CHOP",
        "logicCHOP": "CHOP",
        "lookupCHOP": "CHOP",
        "ltcinCHOP": "CHOP",
        "ltcoutCHOP": "CHOP",
        "midiinCHOP": "CHOP",
        "midiinmapCHOP": "CHOP",
        "midioutCHOP": "CHOP",
        "mosysCHOP": "CHOP",
        "mouseinCHOP": "CHOP",
        "mouseoutCHOP": "CHOP",
        "ncamCHOP": "CHOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _CHOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 109
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 63


def test_chop_camera_vr_protocol_output_pattern_and_record_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "oakdeviceCHOP": "CHOP",
        "objectCHOP": "CHOP",
        "oculusaudioCHOP": "CHOP",
        "oculusriftCHOP": "CHOP",
        "openvrCHOP": "CHOP",
        "optitrackinCHOP": "CHOP",
        "oscinCHOP": "CHOP",
        "oscoutCHOP": "CHOP",
        "outCHOP": "CHOP",
        "pangolinCHOP": "CHOP",
        "pantiltCHOP": "CHOP",
        "parameterCHOP": "CHOP",
        "patternCHOP": "CHOP",
        "performCHOP": "CHOP",
        "phaserCHOP": "CHOP",
        "pipeinCHOP": "CHOP",
        "pipeoutCHOP": "CHOP",
        "posistagenetCHOP": "CHOP",
        "pulseCHOP": "CHOP",
        "recordCHOP": "CHOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _CHOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 129
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 43


def test_chop_rename_resample_script_serial_sharedmem_time_and_motion_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "renameCHOP": "CHOP",
        "reorderCHOP": "CHOP",
        "replaceCHOP": "CHOP",
        "resampleCHOP": "CHOP",
        "scriptCHOP": "CHOP",
        "scurveCHOP": "CHOP",
        "sequencerCHOP": "CHOP",
        "serialCHOP": "CHOP",
        "sharedmeminCHOP": "CHOP",
        "sharedmemoutCHOP": "CHOP",
        "shiftCHOP": "CHOP",
        "shuffleCHOP": "CHOP",
        "slopeCHOP": "CHOP",
        "sortCHOP": "CHOP",
        "speedCHOP": "CHOP",
        "spliceCHOP": "CHOP",
        "springCHOP": "CHOP",
        "st2110deviceCHOP": "CHOP",
        "stretchCHOP": "CHOP",
        "stypeinCHOP": "CHOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _CHOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 149
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 23


def test_chop_sync_time_touch_device_dat_and_select_comp_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "stypeoutCHOP": "CHOP",
        "syncinCHOP": "CHOP",
        "syncoutCHOP": "CHOP",
        "tabletCHOP": "CHOP",
        "timecodeCHOP": "CHOP",
        "timelineCHOP": "CHOP",
        "timerCHOP": "CHOP",
        "timesliceCHOP": "CHOP",
        "toptoCHOP": "CHOP",
        "touchinCHOP": "CHOP",
        "touchoutCHOP": "CHOP",
        "trailCHOP": "CHOP",
        "transformCHOP": "CHOP",
        "transformxyzCHOP": "CHOP",
        "triggerCHOP": "CHOP",
        "trimCHOP": "CHOP",
        "warpCHOP": "CHOP",
        "waveCHOP": "CHOP",
        "wrnchaiCHOP": "CHOP",
        "zedCHOP": "CHOP",
        "convertDAT": "DAT",
        "selectDAT": "DAT",
        "switchDAT": "DAT",
        "selectCOMP": "COMP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in _CHOP_REVIEWED_2026_06_18 or op_type in _DAT_REVIEWED_2026_06_18
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["CHOP"] >= 165
    assert coverage["structured_operator_card_counts_by_family"]["DAT"] >= 11
    assert coverage["structured_operator_card_counts_by_family"]["COMP"] >= 9
    assert coverage["missing_operator_card_counts_by_family"]["CHOP"] <= 7
    assert coverage["missing_operator_card_counts_by_family"]["DAT"] <= 64
    assert coverage["missing_operator_card_counts_by_family"]["COMP"] <= 33


def test_sop_foundation_curve_capture_and_cpp_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "addSOP": "SOP",
        "alembicSOP": "SOP",
        "alignSOP": "SOP",
        "armSOP": "SOP",
        "basisSOP": "SOP",
        "blendSOP": "SOP",
        "bonegroupSOP": "SOP",
        "booleanSOP": "SOP",
        "boxSOP": "SOP",
        "bridgeSOP": "SOP",
        "capSOP": "SOP",
        "captureSOP": "SOP",
        "captureregionSOP": "SOP",
        "carveSOP": "SOP",
        "circleSOP": "SOP",
        "claySOP": "SOP",
        "clipSOP": "SOP",
        "cplusplusSOP": "SOP",
        "creepSOP": "SOP",
        "curveclaySOP": "SOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _SOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["SOP"] >= 40
    assert coverage["missing_operator_card_counts_by_family"]["SOP"] <= 73


def test_sop_intersection_deform_file_group_and_legacy_device_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "curvesectSOP": "SOP",
        "deformSOP": "SOP",
        "deleteSOP": "SOP",
        "divideSOP": "SOP",
        "extrudeSOP": "SOP",
        "facetSOP": "SOP",
        "facetrackSOP": "SOP",
        "fileinSOP": "SOP",
        "filletSOP": "SOP",
        "fitSOP": "SOP",
        "forceSOP": "SOP",
        "fractalSOP": "SOP",
        "groupSOP": "SOP",
        "holeSOP": "SOP",
        "inSOP": "SOP",
        "inversecurveSOP": "SOP",
        "isosurfaceSOP": "SOP",
        "joinSOP": "SOP",
        "jointSOP": "SOP",
        "kinectSOP": "SOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _SOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["SOP"] >= 60
    assert coverage["missing_operator_card_counts_by_family"]["SOP"] <= 53


def test_sop_lattice_limit_material_poly_and_vr_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "latticeSOP": "SOP",
        "limitSOP": "SOP",
        "linethickSOP": "SOP",
        "lodSOP": "SOP",
        "lsystemSOP": "SOP",
        "magnetSOP": "SOP",
        "materialSOP": "SOP",
        "metaballSOP": "SOP",
        "modelSOP": "SOP",
        "noiseSOP": "SOP",
        "oculusriftSOP": "SOP",
        "openvrSOP": "SOP",
        "outSOP": "SOP",
        "pointSOP": "SOP",
        "polyloftSOP": "SOP",
        "polypatchSOP": "SOP",
        "polyreduceSOP": "SOP",
        "polysplineSOP": "SOP",
        "polystitchSOP": "SOP",
        "primitiveSOP": "SOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _SOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["SOP"] >= 80
    assert coverage["missing_operator_card_counts_by_family"]["SOP"] <= 33


def test_sop_profile_project_surface_scatter_and_simulation_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "profileSOP": "SOP",
        "projectSOP": "SOP",
        "railsSOP": "SOP",
        "rasterSOP": "SOP",
        "raySOP": "SOP",
        "rectangleSOP": "SOP",
        "refineSOP": "SOP",
        "resampleSOP": "SOP",
        "revolveSOP": "SOP",
        "scriptSOP": "SOP",
        "sequenceblendSOP": "SOP",
        "skinSOP": "SOP",
        "sortSOP": "SOP",
        "springSOP": "SOP",
        "sprinkleSOP": "SOP",
        "spriteSOP": "SOP",
        "stitchSOP": "SOP",
        "subdivideSOP": "SOP",
        "superquadSOP": "SOP",
        "surfsectSOP": "SOP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _SOP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["SOP"] >= 100
    assert coverage["missing_operator_card_counts_by_family"]["SOP"] <= 13


def test_remaining_sop_and_initial_dat_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "sweepSOP": "SOP",
        "textSOP": "SOP",
        "torusSOP": "SOP",
        "traceSOP": "SOP",
        "trailSOP": "SOP",
        "transformSOP": "SOP",
        "trimSOP": "SOP",
        "tristripSOP": "SOP",
        "tubeSOP": "SOP",
        "twistSOP": "SOP",
        "vertexSOP": "SOP",
        "wireframeSOP": "SOP",
        "zedSOP": "SOP",
        "art-netDAT": "DAT",
        "audiodevicesDAT": "DAT",
        "chopexecuteDAT": "DAT",
        "choptoDAT": "DAT",
        "clipDAT": "DAT",
        "convertDAT": "DAT",
        "cplusplusDAT": "DAT",
        "datexecuteDAT": "DAT",
        "dmxmapDAT": "DAT",
        "errorDAT": "DAT",
        "etherdreamDAT": "DAT",
        "evaluateDAT": "DAT",
        "examineDAT": "DAT",
        "executeDAT": "DAT",
        "fifoDAT": "DAT",
        "fileinDAT": "DAT",
        "fileoutDAT": "DAT",
        "folderDAT": "DAT",
        "inDAT": "DAT",
        "indicesDAT": "DAT",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in _SOP_REVIEWED_2026_06_18 or op_type in _DAT_REVIEWED_2026_06_18
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["SOP"] >= 112
    assert coverage["missing_operator_card_counts_by_family"]["SOP"] <= 1
    assert coverage["structured_operator_card_counts_by_family"]["DAT"] >= 19
    assert coverage["missing_operator_card_counts_by_family"]["DAT"] <= 56


def test_dat_table_io_execute_media_and_network_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "evaluateDAT": "DAT",
        "examineDAT": "DAT",
        "executeDAT": "DAT",
        "fifoDAT": "DAT",
        "fileinDAT": "DAT",
        "fileoutDAT": "DAT",
        "folderDAT": "DAT",
        "inDAT": "DAT",
        "indicesDAT": "DAT",
        "infoDAT": "DAT",
        "insertDAT": "DAT",
        "lookupDAT": "DAT",
        "mediafileinfoDAT": "DAT",
        "midieventDAT": "DAT",
        "midiinDAT": "DAT",
        "monitorsDAT": "DAT",
        "mpcdiDAT": "DAT",
        "mqttclientDAT": "DAT",
        "multitouchinDAT": "DAT",
        "ndiDAT": "DAT",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _DAT_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["DAT"] >= 39
    assert coverage["missing_operator_card_counts_by_family"]["DAT"] <= 36
    assert coverage["structured_operator_card_count"] >= 587
    assert coverage["missing_operator_card_count"] <= 80


def test_dat_operator_boundary_event_network_and_table_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "nullDAT": "DAT",
        "opexecuteDAT": "DAT",
        "opfindDAT": "DAT",
        "oscinDAT": "DAT",
        "oscoutDAT": "DAT",
        "outDAT": "DAT",
        "panelexecuteDAT": "DAT",
        "parameterDAT": "DAT",
        "parameterexecuteDAT": "DAT",
        "pargroupexecuteDAT": "DAT",
        "performDAT": "DAT",
        "reorderDAT": "DAT",
        "scriptDAT": "DAT",
        "serialDAT": "DAT",
        "serialdevicesDAT": "DAT",
        "socketioDAT": "DAT",
        "sortDAT": "DAT",
        "substituteDAT": "DAT",
        "tableDAT": "DAT",
        "tcp/ipDAT": "DAT",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _DAT_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["DAT"] >= 59
    assert coverage["missing_operator_card_counts_by_family"]["DAT"] <= 16
    assert coverage["structured_operator_card_count"] >= 607
    assert coverage["missing_operator_card_count"] <= 60


def test_dat_network_web_and_comp_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "touchinDAT": "DAT",
        "touchoutDAT": "DAT",
        "transposeDAT": "DAT",
        "tuioinDAT": "DAT",
        "udpinDAT": "DAT",
        "udpoutDAT": "DAT",
        "udtinDAT": "DAT",
        "udtoutDAT": "DAT",
        "videodevicesDAT": "DAT",
        "webclientDAT": "DAT",
        "webrtcDAT": "DAT",
        "webserverDAT": "DAT",
        "websocketDAT": "DAT",
        "xmlDAT": "DAT",
        "actorCOMP": "COMP",
        "ambientlightCOMP": "COMP",
        "animationCOMP": "COMP",
        "annotateCOMP": "COMP",
        "blendCOMP": "COMP",
        "boneCOMP": "COMP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = (
            "2026-06-18"
            if op_type in _COMP_REVIEWED_2026_06_18 or op_type in _DAT_REVIEWED_2026_06_18
            else "2026-06-17"
        )
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["DAT"] >= 73
    assert coverage["missing_operator_card_counts_by_family"].get("DAT", 0) <= 2
    assert coverage["structured_operator_card_counts_by_family"]["COMP"] >= 15
    assert coverage["missing_operator_card_counts_by_family"]["COMP"] <= 27
    assert coverage["structured_operator_card_count"] >= 627
    assert coverage["missing_operator_card_count"] <= 40


def test_comp_physics_engine_panel_and_sharedmem_priority_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "buildalistCOMP": "COMP",
        "bulletsolverCOMP": "COMP",
        "camerablendCOMP": "COMP",
        "constraintCOMP": "COMP",
        "engineCOMP": "COMP",
        "environmentlightCOMP": "COMP",
        "fbxCOMP": "COMP",
        "forceCOMP": "COMP",
        "geotextCOMP": "COMP",
        "handleCOMP": "COMP",
        "impulseforceCOMP": "COMP",
        "listCOMP": "COMP",
        "nullCOMP": "COMP",
        "nvidiaflexsolverCOMP": "COMP",
        "nvidiaflowemitterCOMP": "COMP",
        "opviewerCOMP": "COMP",
        "parameterCOMP": "COMP",
        "replicatorCOMP": "COMP",
        "sharedmeminCOMP": "COMP",
        "sharedmemoutCOMP": "COMP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _COMP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_counts_by_family"]["COMP"] >= 35
    assert coverage["missing_operator_card_counts_by_family"]["COMP"] <= 7
    assert coverage["structured_operator_card_count"] >= 647
    assert coverage["missing_operator_card_count"] <= 20


def test_remaining_priority_comp_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "tableCOMP": "COMP",
        "textCOMP": "COMP",
        "timeCOMP": "COMP",
        "usdCOMP": "COMP",
        "widgetCOMP": "COMP",
    }

    for op_type, family in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        expected_verified = "2026-06-18" if op_type in _COMP_REVIEWED_2026_06_18 else "2026-06-17"
        assert card["last_verified"] == expected_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(priority_ops)
    assert priority_ops == set()
    assert coverage["structured_operator_card_counts_by_family"]["COMP"] >= 40
    assert coverage["missing_operator_card_counts_by_family"]["COMP"] <= 2
    assert coverage["structured_operator_card_count"] >= 652
    assert coverage["missing_operator_card_count"] <= 15


def test_active_docsbrain_name_drift_operator_cards_are_structured():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    expected = {
        "datexecuteDAT": ("DAT", "2026-06-18"),
        "opviewerTOP": ("TOP", "2026-06-18"),
        "overrideCHOP": ("CHOP", "2026-06-18"),
        "windowCOMP": ("COMP", "2026-06-17"),
    }

    for op_type, (family, last_verified) in expected.items():
        card = cards.get_operator(op_type)

        assert card is not None, op_type
        assert card["family"] == family
        assert card["docs_url"].startswith("https://docs.derivative.ca/")
        assert card["key_params"], op_type
        assert card["common_gotchas"], op_type
        assert card["build_relevance"] != "unverified-docsbrain"
        assert card["last_verified"] == last_verified

    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    deprecated_ops = {item["op_type"] for item in coverage["deprecated_missing_operator_cards"]}
    priority_ops = {item["op_type"] for item in coverage["priority_missing_operator_cards"]}

    assert not set(expected).intersection(deprecated_ops)
    assert not set(expected).intersection(priority_ops)
    assert coverage["structured_operator_card_count"] >= 656
    assert coverage["missing_operator_card_count"] <= 11


def test_high_value_operator_quality_gate_requires_reviewed_key_concepts():
    cards = CardIndex(Path("src/td_mcp/knowledge/cards"))
    report = audit_brain_atlas(Path("."))
    quality = report["operator_card_quality"]
    expected = (
        {
            "selectCOMP",
            "tableCOMP",
            "textCOMP",
            "widgetCOMP",
            "windowCOMP",
            "abletonlinkCHOP",
            "accumulatePOP",
            "actorCOMP",
            "alembicinPOP",
            "alembicoutPOP",
            "analyzeCHOP",
            "analyzePOP",
            "ambientlightCOMP",
            "angleCHOP",
            "animationCOMP",
            "annotateCOMP",
            "audiobandeqCHOP",
            "audiobinauralCHOP",
            "audiodeviceinCHOP",
            "audiodeviceoutCHOP",
            "audiodynamicsCHOP",
            "attributecombinePOP",
            "attributeconvertPOP",
            "attributePOP",
            "audiofileinCHOP",
            "audiofileoutCHOP",
            "audiofilterCHOP",
            "audiomovieCHOP",
            "audiondiCHOP",
            "audiooscillatorCHOP",
            "audioparaeqCHOP",
            "audioplayCHOP",
            "audiorenderCHOP",
            "audiospectrumCHOP",
            "audiostreaminCHOP",
            "audiostreamoutCHOP",
            "audiovstCHOP",
            "audiowebrenderCHOP",
            "attributeCHOP",
            "baseCOMP",
            "beatCHOP",
            "bindCHOP",
            "blacktraxCHOP",
            "blendCHOP",
            "blendCOMP",
            "blendPOP",
            "blobtrackCHOP",
            "bodytrackCHOP",
            "boneCOMP",
            "boxPOP",
            "bulletsolverCHOP",
            "bulletsolverCOMP",
            "buttonCOMP",
            "buildalistCOMP",
            "cachePOP",
            "cacheblendPOP",
            "cacheselectPOP",
            "cameraCOMP",
            "camerablendCOMP",
            "choptoPOP",
            "circlePOP",
            "clipCHOP",
            "clipblenderCHOP",
            "clockCHOP",
            "compositeCHOP",
            "compositeTOP",
            "connectivityPOP",
            "containerCOMP",
            "constantCHOP",
            "constantMAT",
            "constantTOP",
            "constraintCOMP",
            "convertPOP",
            "copyCHOP",
            "copyPOP",
            "countCHOP",
            "cplusplusCHOP",
            "cplusplusPOP",
            "crossCHOP",
            "cycleCHOP",
            "curvePOP",
            "dattoCHOP",
            "dattoPOP",
            "delayCHOP",
            "deleteCHOP",
            "deletePOP",
            "depthMAT",
            "dimensionPOP",
            "dmxinCHOP",
            "dmxfixturePOP",
            "dmxoutCHOP",
            "dmxoutPOP",
            "envelopeCHOP",
            "engineCOMP",
            "environmentlightCOMP",
            "eventCHOP",
            "expressionCHOP",
            "extrudePOP",
            "extendCHOP",
            "facetPOP",
            "facetrackCHOP",
            "fanCHOP",
            "feedbackCHOP",
            "fbxCOMP",
            "feedbackTOP",
            "feedbackPOP",
            "fieldPOP",
            "fileinCHOP",
            "fileinPOP",
            "fileoutCHOP",
            "fileoutPOP",
            "filterCHOP",
            "forceCOMP",
            "forceradialPOP",
            "freedinCHOP",
            "freedoutCHOP",
            "functionCHOP",
            "geotextCOMP",
            "geometryCOMP",
            "gestureCHOP",
            "gridPOP",
            "glslMAT",
            "glslPOP",
            "glslTOP",
            "groupPOP",
            "handleCHOP",
            "handleCOMP",
            "histogramPOP",
            "hogCHOP",
            "hokuyoCHOP",
            "holdCHOP",
            "importselectCHOP",
            "importselectPOP",
            "impulseforceCOMP",
            "inCHOP",
            "infoCHOP",
            "inMAT",
            "inPOP",
            "interpolateCHOP",
            "inversecurveCHOP",
            "inversekinCHOP",
            "joinCHOP",
            "joystickCHOP",
            "keyboardinCHOP",
            "keyframeCHOP",
            "kinectCHOP",
            "kinectazureCHOP",
            "lagCHOP",
            "laserCHOP",
            "laserdeviceCHOP",
            "leapmotionCHOP",
            "leuzerod4CHOP",
            "lfoCHOP",
            "limitCHOP",
            "limitPOP",
            "logicCHOP",
            "lookupCHOP",
            "lightCOMP",
            "lineMAT",
            "listCOMP",
            "linethickPOP",
            "linebreakPOP",
            "linedividePOP",
            "levelTOP",
            "linemetricsPOP",
            "linePOP",
            "lineresamplePOP",
            "linesmoothPOP",
            "ltcinCHOP",
            "ltcoutCHOP",
            "lookupattributePOP",
            "lookupchannelPOP",
            "lookuptexturePOP",
            "mathCHOP",
            "mathcombinePOP",
            "mathmixPOP",
            "mathPOP",
            "mergeCHOP",
            "mergePOP",
            "midiinCHOP",
            "midiinmapCHOP",
            "midioutCHOP",
            "mosysCHOP",
            "mouseinCHOP",
            "mouseoutCHOP",
            "ncamCHOP",
            "normalPOP",
            "neighborPOP",
            "noiseCHOP",
            "noisePOP",
            "noiseTOP",
            "nullCHOP",
            "nullCOMP",
            "nullMAT",
            "nullPOP",
            "nullTOP",
            "nvidiaflexsolverCOMP",
            "nvidiaflowemitterCOMP",
            "normalizePOP",
            "oakdeviceCHOP",
            "oakselectCHOP",
            "oakselectPOP",
            "objectCHOP",
            "oculusaudioCHOP",
            "oculusriftCHOP",
            "openvrCHOP",
            "optitrackinCHOP",
            "oscinCHOP",
            "oscoutCHOP",
            "outCHOP",
            "overrideCHOP",
            "pangolinCHOP",
            "pantiltCHOP",
            "parameterCHOP",
            "patternCHOP",
            "performCHOP",
            "phaserCHOP",
            "pipeinCHOP",
            "pipeoutCHOP",
            "posistagenetCHOP",
            "pulseCHOP",
            "recordCHOP",
            "renderpickCHOP",
            "renderstreaminCHOP",
            "outMAT",
            "outPOP",
            "opviewerCOMP",
            "panelCHOP",
            "particlePOP",
            "parameterCOMP",
            "pbrMAT",
            "phaserPOP",
            "phongMAT",
            "patternPOP",
            "planePOP",
            "pointPOP",
            "pointfileinPOP",
            "pointspriteMAT",
            "polygonizePOP",
            "poptoCHOP",
            "poptoDAT",
            "poptoSOP",
            "poptoTOP",
            "primitivePOP",
            "projectionPOP",
            "quantizePOP",
            "randomPOP",
            "rectanglePOP",
            "renameCHOP",
            "reorderCHOP",
            "replicatorCOMP",
            "rerangePOP",
            "replaceCHOP",
            "renderTOP",
            "rendersimpleTOP",
            "resampleCHOP",
            "proximityPOP",
            "rayPOP",
            "revolvePOP",
            "selectMAT",
            "selectPOP",
            "sharedmeminCOMP",
            "sharedmemoutCOMP",
            "scriptCHOP",
            "scurveCHOP",
            "shuffleCHOP",
            "sequencerCHOP",
            "serialCHOP",
            "sharedmeminCHOP",
            "sharedmemoutCHOP",
            "shiftCHOP",
            "slopeCHOP",
            "speedCHOP",
            "spliceCHOP",
            "soptoPOP",
            "soptoCHOP",
            "skinPOP",
            "skindeformPOP",
            "sliderCOMP",
            "sortCHOP",
            "spherePOP",
            "sortPOP",
            "sprinklePOP",
            "springCHOP",
            "st2110deviceCHOP",
            "stretchCHOP",
            "stypeinCHOP",
            "stypeoutCHOP",
            "subdividePOP",
            "syncinCHOP",
            "syncoutCHOP",
            "switchMAT",
            "switchCHOP",
            "switchPOP",
            "tabletCHOP",
            "timecodeCHOP",
            "timelineCHOP",
            "timerCHOP",
            "timesliceCHOP",
            "texturemapPOP",
            "textDAT",
            "textPOP",
            "timeCOMP",
            "toptoCHOP",
            "topologyPOP",
            "torusPOP",
            "trailPOP",
            "touchinCHOP",
            "touchoutCHOP",
            "trailCHOP",
            "transformCHOP",
            "transformPOP",
            "transformxyzCHOP",
            "triangulatePOP",
            "trigPOP",
            "triggerCHOP",
            "trimCHOP",
            "tubePOP",
            "twistPOP",
            "usdCOMP",
            "warpCHOP",
            "waveCHOP",
            "wireframeMAT",
            "wrnchaiCHOP",
            "zedCHOP",
            "zedPOP",
        }
        | _TOP_REVIEWED_2026_06_18
        | _SOP_REVIEWED_2026_06_18
        | _DAT_REVIEWED_2026_06_18
    )

    assert quality["minimum_overrides"]["convertPOP"]["key_params"] == 2
    assert quality["minimum_overrides"]["inPOP"]["key_params"] == 2
    assert quality["minimum_overrides"]["inSOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["inversecurveSOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["bonegroupSOP"]["key_params"] == 2
    assert quality["minimum_overrides"]["materialSOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["nullPOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["openvrSOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["outSOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["poptoSOP"]["key_params"] == 2
    assert quality["minimum_overrides"]["scriptSOP"]["key_params"] == 2
    assert quality["minimum_overrides"]["selectSOP"]["key_params"] == 1
    assert quality["minimum_overrides"]["tristripSOP"]["key_params"] == 3
    assert quality["ok"] is True
    assert set(quality["strict_operator_types"]).issuperset(expected)
    assert quality["minimum_overrides"]["cudaTOP"]["key_params"] == 1
    assert quality["minimums"]["key_concepts"] >= 3
    assert quality["gaps"] == []

    top_param_guards = {
        "addTOP": {"size", "prefit", "justifyh", "justifyv", "extend", "r", "t", "s"},
        "analyzeTOP": {"op", "analyzechannel", "scope", "excludenans", "mask"},
        "antialiasTOP": {
            "quality",
            "edgedetectsource",
            "edgethreshold",
            "maxsearchsteps",
            "maxdiagsearchsteps",
        },
        "blobtrackTOP": {"reset", "resetpulse", "monosource", "drawblobs", "blobcolor"},
        "bloomTOP": {"minbloomradius", "maxbloomradius", "bloomthreshold", "bloomfill", "bloomintensity"},
        "blurTOP": {"type", "extend", "size", "scale", "offset", "offsetunit", "npasses"},
        "cacheTOP": {"active", "activepulse", "cachesize", "step", "outputindex", "interp", "reset"},
        "cacheselectTOP": {"cachetop", "index", "outputresolution"},
        "channelmixTOP": {"red", "green", "blue", "alpha", "constant", "format"},
        "choptoTOP": {"chop", "dataformat", "clamp", "layout", "rgba", "format"},
        "chromakeyTOP": {
            "huemin",
            "huemax",
            "hsoftlow",
            "hsofthigh",
            "satmin",
            "satmax",
            "rgbout",
            "alphaout",
        },
        "circleTOP": {
            "radius",
            "radiusunit",
            "rotate",
            "center",
            "centerunit",
            "fillcolor",
            "border",
            "sides",
        },
        "convolveTOP": {"dat", "normalize", "applytoalpha", "offset", "scale", "convolvez"},
        "cornerpinTOP": {
            "extractp1",
            "extractp2",
            "extractp3",
            "extractp4",
            "pinp1",
            "pinp2",
            "pinp3",
            "pinp4",
        },
        "cplusplusTOP": {"plugin", "reinit", "reinitpulse", "unloadplugin", "antialias", "numcolorbufs"},
        "cropTOP": {
            "cropleft",
            "cropleftunit",
            "cropright",
            "croprightunit",
            "cropbottom",
            "croptop",
            "extend",
        },
        "crossTOP": {"cross", "size", "prefit", "justifyh", "justifyv", "extend", "r", "t", "s"},
        "cubemapTOP": {"mode", "outputresolution", "format"},
        "cudaTOP": {"replacement"},
        "depthTOP": {
            "rendertop",
            "cameraindex",
            "peellayerindex",
            "pixelformat",
            "depthspace",
            "rangefrom",
            "rangeto",
        },
        "differenceTOP": {"size", "prefit", "justifyh", "justifyv", "extend", "r", "t", "s", "format"},
        "directdisplayoutTOP": {"active", "display", "hwframelock"},
        "directxinTOP": {"handle"},
        "directxoutTOP": {"active", "queuesize"},
        "displaceTOP": {
            "resolutionsource",
            "horzsource",
            "vertsource",
            "zsource",
            "midpoint",
            "displaceweight",
            "extend",
        },
        "edgeTOP": {
            "select",
            "blacklevel",
            "strength",
            "offset",
            "offsetunit",
            "edgecolor",
            "premultrgbbyalpha",
            "alphaoutputmenu",
            "combineinput",
            "operand",
        },
        "embossTOP": {"select", "method", "midpoint", "strength", "offset", "offsetunit", "direction"},
        "fitTOP": {"fit", "justifyh", "justifyv", "xord", "t", "tunit", "r", "s", "p", "punit", "bgcolor"},
        "flipTOP": {"flipx", "flipy", "flipz", "flop", "outputresolution", "format"},
        "functionTOP": {
            "rerange",
            "funcrgba",
            "funcrgb",
            "funcr",
            "funcg",
            "funcb",
            "funca",
            "baseval",
            "expval",
            "constval",
        },
        "hsvadjustTOP": {
            "startcolor",
            "huerange",
            "huefalloff",
            "saturationrange",
            "saturationfalloff",
            "valuerange",
            "valuefalloff",
            "hueoffset",
            "saturationmult",
            "valuemult",
        },
        "hsvtorgbTOP": {"outputresolution", "npasses", "chanmask", "format"},
        "importselectTOP": {"parent", "texture", "reload"},
        "inTOP": {"label", "outputresolution", "format"},
        "insideTOP": {
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
            "legacyxform",
        },
        "kinectTOP": {
            "active",
            "hwversion",
            "sensor",
            "image",
            "camerares",
            "skeleton",
            "neardepthmode",
            "mirrorimage",
            "remap",
            "unknownpointvalue",
        },
        "kinectazureTOP": {
            "active",
            "library",
            "sensor",
            "fps",
            "colorres",
            "depthmode",
            "proccessingmode",
            "image",
            "remapimage",
            "syncmode",
        },
        "kinectazureselectTOP": {"active", "top", "image"},
        "layerTOP": {
            "fixedlayer",
            "base",
            "blanklayer",
            "layerres",
            "layercolor",
            "layeralpha",
            "enblcrop",
            "prefit",
            "justifyh",
            "justifyv",
            "extend",
            "operand",
            "lay",
            "lay0top",
        },
        "layermixTOP": {
            "background",
            "size",
            "bgtop",
            "bgcolor",
            "enablecrop",
            "cropunit",
            "prefit",
            "enablejust",
            "extend",
            "scalemode",
            "operand",
            "comporder",
        },
        "layoutTOP": {
            "top",
            "scaleres",
            "align",
            "fit",
            "rowlayout",
            "numrows",
            "collayout",
            "numcols",
            "bcolor",
            "borders",
            "bgcolor",
            "premultrgbbyalpha",
        },
        "leapmotionTOP": {"active", "api", "libfolder", "camera", "flipx", "flipy", "correction", "hmd"},
        "lensdistortTOP": {
            "invert",
            "k1",
            "k2",
            "k3",
            "p1",
            "p2",
            "center",
            "centerunit",
            "focallength",
            "focallengthunit",
            "layout",
            "extendmode",
            "transformmode",
            "cropmode",
        },
        "limitTOP": {
            "minop",
            "maxop",
            "min",
            "max",
            "positive",
            "norm",
            "normmin",
            "normmax",
            "quantvalue",
            "vstep",
            "voffset",
            "quantpos",
            "posstep",
            "posoffset",
        },
        "lookupTOP": {
            "method",
            "index",
            "channel",
            "independentalpha",
            "darkuv",
            "darkuvunit",
            "lightuv",
            "lightuvunit",
            "chop",
            "clampchopvalues",
            "displaylookup",
        },
        "lumablurTOP": {
            "type",
            "widthchan",
            "blackvalue",
            "whitevalue",
            "blackwidth",
            "whitewidth",
            "extend",
        },
        "lumalevelTOP": {
            "source",
            "invert",
            "blacklevel",
            "brightness1",
            "gamma1",
            "contrast",
            "inlow",
            "inhigh",
            "outlow",
            "outhigh",
            "stepsize",
            "threshold",
            "clamplow",
            "clamphigh",
            "soften",
            "opacity",
        },
        "mathTOP": {
            "preop",
            "chanop",
            "postop",
            "integer",
            "inputmask",
            "outputchannels",
            "preoff",
            "gain",
            "postoff",
            "op",
            "fromrange",
            "torange",
        },
        "matteTOP": {"switchinputs", "mattechannel"},
        "mirrorTOP": {"pivot", "pivotunit", "rotate", "extend", "flipx", "flipy"},
        "monochromeTOP": {"mono", "rgb", "alpha"},
        "mosysTOP": {"chop", "outputresolution", "format"},
        "moviefileinTOP": {
            "file",
            "reload",
            "reloadpulse",
            "playmode",
            "play",
            "index",
            "speed",
            "imageindexing",
            "inputcolorspace",
            "decodepixelformat",
            "prereadframes",
            "hwdecode",
        },
        "moviefileoutTOP": {
            "type",
            "videocodec",
            "file",
            "record",
            "addframe",
            "audiochop",
            "imagefiletype",
            "moviepixelformat",
            "moviecontainer",
        },
        "mpcdiTOP": {
            "file",
            "reloadpulse",
            "outputformat",
            "bufferid",
            "regionid",
            "layoutmax",
            "near",
            "far",
            "alphabeta",
            "gamma",
        },
        "multiplyTOP": {"size", "prefit", "justifyh", "justifyv", "extend", "r", "t", "s", "p"},
        "ncamTOP": {"active", "chop", "output"},
        "ndiinTOP": {
            "active",
            "name",
            "extraips",
            "bandwidth",
            "hwdecode",
            "inputpixelformat",
            "inputcolorspace",
        },
        "ndioutTOP": {
            "active",
            "name",
            "failovername",
            "fps",
            "lowperformancebehavior",
            "outputpixelformat",
            "includealpha",
            "audiochop",
            "metadata",
        },
        "normalmapTOP": {"source", "method", "offset", "offsetunit", "heightmap"},
        "notchTOP": {
            "active",
            "clearparams",
            "block",
            "layer",
            "playmode",
            "init",
            "play",
            "speed",
            "index",
            "purge",
        },
        "nvidiabackgroundTOP": {"mode", "segment", "outputresolution", "format"},
        "nvidiadenoiseTOP": {"mode", "strength", "outputresolution", "format"},
        "nvidiaflexTOP": {"comp", "output", "outputresolution", "format"},
        "nvidiaflowTOP": {
            "initialize",
            "start",
            "play",
            "camera",
            "emitters",
            "simposition",
            "simsize",
            "memusage",
            "speed",
            "maxsteps",
            "rendermode",
        },
        "nvidiartxvideoTOP": {
            "mode",
            "superresquality",
            "hdrcontrast",
            "hdrsaturation",
            "hdrmiddlegray",
            "hdrmaxluminance",
            "outputresolution",
        },
        "nvidiaupscalerTOP": {"mode", "strength", "artifactreduction", "outputresolution"},
        "oakselectTOP": {
            "active",
            "chop",
            "stream",
            "cachesize",
            "outputindex",
            "outputindexunit",
            "limitmax",
            "outputformat",
        },
        "oculusriftTOP": {"active", "debugperfhud", "outputresolution", "format"},
        "opencolorioTOP": {
            "config",
            "reloadconfig",
            "usecolorspacetransform",
            "incolorspace",
            "outcolorspace",
            "usefiletransform",
            "filesource",
            "interpolation",
            "filedirection",
            "cdlmode",
            "slope",
            "offset",
            "power",
            "saturation",
            "useoutput",
            "display",
            "view",
            "gamma",
        },
        "openvrTOP": {"active", "outputresolution", "format"},
        "opticalflowTOP": {"gridsize", "quality", "costoutput", "gain", "manualtiming", "timestamp"},
        "opviewerTOP": {"opviewer", "allowpanel", "preservealpha", "outputresolution", "format"},
        "orbbecTOP": {
            "active",
            "devicesource",
            "device",
            "ip",
            "image",
            "colorres",
            "depthres",
            "depthalignmode",
            "gyro",
            "accel",
            "propschop",
        },
        "orbbecselectTOP": {"active", "top", "image"},
        "ousterTOP": {
            "active",
            "reinitialize",
            "deviceaddress",
            "lidarport",
            "imuport",
            "targetaddress",
            "scanmode",
            "opmode",
            "azimuthwindow",
            "signalmultiplier",
            "dataformat",
            "redchannel",
            "greenchannel",
            "bluechannel",
            "alphachannel",
            "timemode",
            "iomode",
        },
        "ousterselectTOP": {"oustertop", "redchannel", "greenchannel", "bluechannel", "alphachannel"},
        "outTOP": {"label", "outputresolution", "resolution", "outputaspect", "format"},
        "outsideTOP": {"size", "prefit", "justifyh", "justifyv", "extend", "r", "t", "s", "p"},
        "overTOP": {"size", "prefit", "justifyh", "justifyv", "extend", "r", "t", "s", "p"},
        "packTOP": {"packtype", "pack", "unpackr", "unpackrg", "unpackrgb", "unpackrgbA", "format"},
        "photoshopinTOP": {
            "active",
            "address",
            "password",
            "imageformat",
            "lockeddocument",
            "locktocurrent",
            "unlock",
            "updatemode",
            "maxupdaterate",
            "update",
        },
        "pointfileinTOP": {
            "file",
            "reload",
            "reloadpulse",
            "red",
            "green",
            "blue",
            "alpha",
            "playmode",
            "speed",
            "index",
            "prereadframes",
            "frametimeout",
            "frametimeoutstrat",
            "opentimeout",
            "asyncupload",
        },
        "pointfileselectTOP": {"pointfileintop", "red", "green", "blue", "alpha"},
        "pointtransformTOP": {
            "inputtype",
            "innormalize",
            "outnormalize",
            "xord",
            "rord",
            "t",
            "chopinput",
            "multiplyorder",
            "weightchannel",
            "weightrange",
            "alignxformorder",
        },
        "prefiltermapTOP": {"output", "outputresolution", "format"},
        "projectionTOP": {"input", "output", "fov", "r", "outputresolution", "resolution"},
        "rampTOP": {
            "dat",
            "color",
            "type",
            "position",
            "phase",
            "period",
            "extendleft",
            "extendright",
            "interp",
            "tension",
            "fitaspect",
            "antialias",
            "dither",
            "compoverinput",
            "operand",
        },
        "realsenseTOP": {
            "active",
            "model",
            "sensor",
            "image",
            "colorres",
            "maxdepth",
            "mirrorimage",
            "defaulttradeoff",
            "tradeoff",
            "optionschop",
            "skeltracking",
            "licensedir",
            "modelfile",
        },
        "rectangleTOP": {
            "size",
            "sizeunit",
            "rotate",
            "center",
            "centerunit",
            "justifyh",
            "justifyv",
            "fillcolor",
            "fillalpha",
            "border",
            "borderalpha",
            "bgcolor",
            "bgalpha",
            "borderwidth",
            "borderoffset",
            "cornerradius",
            "antialias",
            "softness",
            "compoverinput",
        },
        "remapTOP": {
            "resolutionsource",
            "depthressource",
            "horzsource",
            "vertsource",
            "zsource",
            "fliphorz",
            "flipvert",
            "flipz",
            "extend",
            "interp",
        },
        "renderpassTOP": {
            "renderinput",
            "camera",
            "geometry",
            "lights",
            "cleartocamcolor",
            "cleardepth",
            "overridemat",
            "posside",
            "negside",
            "transparency",
            "allowbufblending",
            "cullface",
            "coloroutputneeded",
            "drawdepthonly",
        },
        "renderselectTOP": {
            "top",
            "colorbufindex",
            "cameraindex",
            "peellayerindex",
            "imageoutput",
            "outputresolution",
        },
        "renderstreaminTOP": {"active", "name", "outputresolution"},
        "renderstreamoutTOP": {"active", "streamindex", "profilechop"},
        "reorderTOP": {
            "outputred",
            "outputredchan",
            "outputgreen",
            "outputgreenchan",
            "outputblue",
            "outputbluechan",
            "outputalpha",
            "outputalphachan",
        },
        "resolutionTOP": {
            "highqualresize",
            "outputresolution",
            "resolution",
            "outputaspect",
            "inputfiltertype",
            "format",
        },
        "rgbkeyTOP": {
            "redmin",
            "redmax",
            "rsoftlow",
            "rsofthigh",
            "greenmin",
            "greenmax",
            "gsoftlow",
            "gsofthigh",
            "bluemin",
            "bluemax",
            "bsoftlow",
            "bsofthigh",
            "invert",
            "rgbout",
            "alphaout",
        },
        "rgbtohsvTOP": {"outputresolution", "npasses", "chanmask", "format"},
        "scalabledisplayTOP": {
            "configfile",
            "near",
            "far",
            "eyepoint",
            "eyepoint1",
            "eyepoint2",
            "eyepoint3",
        },
        "screenTOP": {
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
            "legacyxform",
        },
        "screengrabTOP": {
            "active",
            "activepulse",
            "source",
            "refreshsource",
            "left",
            "leftunit",
            "right",
            "rightunit",
            "bottom",
            "bottomunit",
            "top",
            "topunit",
            "delayed",
        },
        "scriptTOP": {"callbacks", "setuppars", "modoutsidecook", "outputresolution", "format"},
        "sharedmeminTOP": {"name", "memtype", "local", "global", "outputresolution", "format"},
        "sharedmemoutTOP": {"active", "name", "memtype", "local", "global", "downloadtype", "format"},
        "sickTOP": {"active", "reinitialize", "launchfile", "deviceaddress", "port", "customargs"},
        "simplerenderTOP": {"pop", "normalizegeo", "materialsource"},
        "slopeTOP": {"red", "green", "blue", "alpha", "method", "format", "outputresolution"},
        "spectrumTOP": {"mode", "coord", "chan", "transrows", "format"},
        "ssaoTOP": {
            "quality",
            "sampledirs",
            "samplesteps",
            "surfaceavoid",
            "ssaopassres",
            "ssaoradius",
            "contrast",
            "attenuation",
            "edgethresh",
            "blurradius",
            "combinewithcolor",
        },
        "st2110inTOP": {
            "active",
            "st2110devicechop",
            "device",
            "setupmode",
            "videosdp",
            "audiosdp",
            "ancillarysdp",
            "setsourceipfromsdp",
            "inputcolorspace",
            "inputreferencewhite",
            "transfermode",
            "resetstats",
        },
        "st2110outTOP": {
            "active",
            "st2110devicechop",
            "device",
            "videodestip",
            "videosourceport",
            "videodestport",
            "videopayloadid",
            "signalformat",
            "outputpixelformat",
            "audiochop",
            "audiobufferlength",
            "enablesps",
        },
        "stypeTOP": {"chop", "padding", "outputresolution", "format"},
        "substanceTOP": {"file", "reloadconfig", "graph", "output", "invertnormal", "engine"},
        "substanceselectTOP": {"substance", "output", "outputresolution", "format"},
        "subtractTOP": {
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
            "legacyxform",
        },
        "syphonspoutinTOP": {"usespoutactivesender", "sendername", "outputresolution", "format"},
        "syphonspoutoutTOP": {"active", "sendername", "outputresolution", "format"},
        "textTOP": {
            "text",
            "fontfile",
            "fontsizex",
            "alignx",
            "aligny",
            "resolution",
            "fontcolor",
            "bgcolor",
            "legacyparsing",
        },
        "texture3dTOP": {"type", "active", "replacesingle", "replaceindex", "prefill", "cachesize", "step"},
        "thresholdTOP": {"comparator", "rgb", "threshold", "alpha", "soften", "format"},
        "tileTOP": {
            "cropleft",
            "cropright",
            "cropbottom",
            "croptop",
            "extend",
            "flop",
            "repeatx",
            "repeaty",
            "flipx",
            "flipy",
            "reflectx",
            "reflecty",
        },
        "timemachineTOP": {
            "blackoffset",
            "blackoffsetunit",
            "whiteoffset",
            "whiteoffsetunit",
            "outputresolution",
        },
        "tonemapTOP": {"type", "midinputnits", "midoutputnits", "peakinputnits", "exposurebias", "format"},
        "touchinTOP": {"address", "port", "active", "mintarget", "maxtarget", "maxqueue", "targetdelay"},
        "touchoutTOP": {"port", "active", "fps", "videocodec", "alwayscook"},
        "transformTOP": {"xord", "t", "tunit", "rotate", "s", "p", "bgcolor", "extend"},
        "underTOP": {
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
            "legacyxform",
        },
        "videodeviceinTOP": {
            "active",
            "driver",
            "device",
            "specifyip",
            "ip",
            "options",
            "deinterlace",
            "precedence",
            "signalformat",
            "inputpixelformat",
            "inputcolorspace",
            "inputreferencewhite",
            "transfermode",
            "memorymode",
            "syncinputs",
            "capture",
        },
        "videodeviceoutTOP": {
            "active",
            "library",
            "device",
            "signalformat",
            "outputpixelformat",
            "outputcolorformat",
            "audiochop",
            "bufferlength",
            "referencesource",
            "manualfield",
            "firstfield",
            "timecodeop",
            "transfermode",
            "syncoutputs",
            "colorspace",
            "outputreferencewhite",
        },
        "videostreaminTOP": {
            "active",
            "mode",
            "url",
            "reloadpulse",
            "play",
            "deinterlace",
            "precedence",
            "prereadframes",
            "videobufferframes",
            "maxdecodecpus",
            "networkbuffersize",
            "networkqueuesize",
            "disablebuffering",
            "hwdecode",
            "webrtc",
            "webrtcconnection",
            "webrtctrack",
        },
        "videostreamoutTOP": {
            "active",
            "mode",
            "port",
            "streamname",
            "url",
            "forceidr",
            "fps",
            "videocodec",
            "profile",
            "keyframeinterval",
            "bitratemode",
            "avgbitrate",
            "maxbitrate",
            "audiochop",
            "audiocodec",
            "perframemetadata",
            "webrtc",
            "webrtcconnection",
            "webrtcvideotrack",
        },
        "viosoTOP": {"configfile", "projectorindex", "outputresolution"},
        "webrenderTOP": {"active", "source", "url", "dat", "reloadsrc", "transparent", "audio", "userdir"},
        "zedTOP": {
            "active",
            "inputsource",
            "camera",
            "file",
            "streamip",
            "streamport",
            "initialize",
            "play",
            "cuepoint",
            "perspective",
            "image",
            "mirrorimage",
            "disableselfcalib",
            "roimask",
            "roimchannel",
            "autogainexp",
            "gainval",
            "expval",
        },
        "zedselectTOP": {
            "active",
            "zedtop",
            "perspective",
            "image",
            "maxdepth",
            "toocloseval",
            "toofarval",
            "unknownval",
            "rerange",
            "mirrorimage",
        },
    }
    for op_type, expected_params in top_param_guards.items():
        actual_params = {param["name"] for param in cards.get_operator(op_type)["key_params"]}
        assert expected_params.issubset(actual_params), op_type

    sop_param_guards = {
        "addSOP": {
            "pointdat",
            "namedattribs",
            "addpts",
            "point0pos",
            "method",
            "polydat",
            "poly0pattern",
            "normals",
        },
        "alembicSOP": {
            "file",
            "objectpath",
            "time",
            "timeunit",
            "xform",
            "straightgpu",
            "compnml",
            "loadfile",
        },
        "alignSOP": {"group", "align", "inc", "bias", "leftuv", "rightuv", "rightuvend", "individual"},
        "armSOP": {
            "capttype",
            "axis",
            "bonerad",
            "rotatehand",
            "autoelbow",
            "elbowtwist",
            "flipelbow",
            "affector",
        },
        "attributeSOP": {
            "ptdel",
            "pt",
            "pt0from",
            "pt0to",
            "vertdel",
            "vert0from",
            "vert0to",
            "primdel",
            "prim0from",
            "prim0to",
            "attrdel",
            "attr0from",
            "attr0to",
        },
        "attributecreateSOP": {"compnml", "comptang", "mikktspace"},
        "basisSOP": {"group", "ubasis", "uparmtype", "uknots", "uorigin", "ulength", "orderu", "vbasis"},
        "blendSOP": {"group", "diff", "dopos", "doclr", "donml", "douvw", "input0weight"},
        "bonegroupSOP": {"bonesperpoint", "bonespergroup"},
        "booleanSOP": {"booleanop", "creategroup", "groupa", "groupb"},
        "boxSOP": {"orientbounds", "modifybounds", "size", "t", "r", "s", "anchoru", "anchorv"},
        "bridgeSOP": {"group", "bridge", "inc", "order", "sdivs", "tolerance", "curvature", "scalec"},
        "cacheSOP": {
            "active",
            "cachesize",
            "step",
            "outputindex",
            "cachepoints",
            "blendpos",
            "reset",
            "resetpulse",
        },
        "capSOP": {"group", "pshapeu", "firstu", "lastu", "divsu1", "pshapev", "firstv", "lastv"},
        "captureSOP": {
            "group",
            "rootbone",
            "weightfrom",
            "captframe",
            "color",
            "captfile",
            "savefile",
            "savecaptfile",
        },
        "captureregionSOP": {"orient", "t", "theight", "tcap", "bheight", "bcap", "weight", "color"},
        "carveSOP": {
            "group",
            "firstu",
            "domainu1",
            "secondu",
            "domainu2",
            "method",
            "extractop",
            "keeporiginal",
        },
        "choptoSOP": {
            "group",
            "chop",
            "startpos",
            "endpos",
            "chanscope",
            "attscope",
            "organize",
            "mapping",
            "compnml",
        },
        "circleSOP": {"type", "orient", "modifybounds", "rad", "t", "order", "divs", "arc"},
        "claySOP": {"group", "method", "xord", "rord", "t", "r", "s", "p"},
        "clipSOP": {"group", "clipop", "dist", "dir", "dirx", "diry", "dirz", "newg", "above", "below"},
        "convertSOP": {
            "group",
            "fromtype",
            "totype",
            "surftype",
            "divu",
            "divv",
            "lodu",
            "lodv",
            "lodtrim",
            "divtrim",
            "orderu",
            "orderv",
            "new",
            "interphull",
            "prtype",
        },
        "copySOP": {
            "sourcegrp",
            "templategrp",
            "ncy",
            "nprims",
            "nml",
            "cum",
            "xord",
            "rord",
            "t",
            "r",
            "s",
            "p",
            "scale",
            "vlength",
            "newg",
            "copyg",
            "lookat",
            "stamp",
            "copy",
            "copy0param",
            "copy0value",
            "doattr",
        },
        "cplusplusSOP": {"plugin", "reinit", "reinitpulse", "unloadplugin"},
        "creepSOP": {
            "reset",
            "resetmethod",
            "fillpath",
            "keepproportions",
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
        },
        "curveclaySOP": {
            "facegroup",
            "surfgroup",
            "divs",
            "sharp",
            "refine",
            "deformop",
            "deformlen",
            "deforminside",
            "projop",
            "individual",
        },
        "curvesectSOP": {
            "leftgroup",
            "rightgroup",
            "xsect",
            "tolerance",
            "method",
            "left",
            "right",
            "affect",
            "extractpt",
            "keeporiginal",
        },
        "dattoSOP": {
            "pointsdat",
            "verticesdat",
            "primsdat",
            "detaildat",
            "merge",
            "float",
            "int",
            "string",
            "build",
            "n",
            "closed",
            "closedv",
            "connect",
            "prtype",
        },
        "deformSOP": {"group", "delcaptatr", "delcolatr", "donormal", "skelrootpath"},
        "deleteSOP": {
            "group",
            "negate",
            "entity",
            "geotype",
            "usenumber",
            "groupop",
            "pattern",
            "rangestart",
            "rangeend",
            "select1",
            "select2",
            "filter",
            "usebounds",
            "boundtype",
            "usenormal",
            "removegrp",
            "keeppoints",
        },
        "divideSOP": {
            "group",
            "convex",
            "numsides",
            "planar",
            "smooth",
            "weight",
            "weight1",
            "weight2",
            "divs",
            "brick",
            "size",
            "sizex",
            "sizey",
            "sizez",
            "offset",
            "angle",
            "removesh",
            "dual",
        },
        "extrudeSOP": {
            "sourcegrp",
            "xsectiongrp",
            "dofuse",
            "fronttype",
            "backtype",
            "sidetype",
            "initextrude",
            "thickxlate",
            "thickscale",
            "depthxlate",
            "depthscale",
            "vertex",
            "docusp",
            "cuspangle",
            "sharefaces",
            "removesharedsides",
            "newg",
            "frontgrp",
            "backgrp",
            "sidegrp",
        },
        "facetSOP": {
            "group",
            "unit",
            "prenml",
            "unique",
            "cons",
            "dist",
            "inline",
            "inlinedist",
            "orientpolys",
            "cusp",
            "angle",
            "remove",
            "postnml",
        },
        "facetrackSOP": {"chop", "directtogpu", "pretransform", "normals"},
        "fileinSOP": {"file", "flipfacing", "normals", "refresh", "refreshpulse"},
        "filletSOP": {
            "group",
            "fillet",
            "inc",
            "loop",
            "dir",
            "fillettype",
            "primtype",
            "order",
            "leftuv1",
            "rightuv1",
            "lrwidth1",
            "lrscale1",
            "lroffset1",
            "seamless",
            "cut",
        },
        "fitSOP": {
            "group",
            "tol",
            "smooth",
            "method",
            "type",
            "surftype",
            "orderu",
            "orderv",
            "multipleu",
            "multiplev",
            "scope",
            "dataparmu",
            "dataparmv",
            "closeu",
            "closev",
            "corners",
        },
        "forceSOP": {
            "doradial",
            "radial",
            "doaxis",
            "dir",
            "dirx",
            "diry",
            "dirz",
            "axial",
            "vortex",
            "spiral",
        },
        "fractalSOP": {
            "group",
            "divs",
            "smooth",
            "scale",
            "seed",
            "fixed",
            "vtxnms",
            "dir",
            "dirx",
            "diry",
            "dirz",
        },
        "gridSOP": {
            "type",
            "surftype",
            "orient",
            "modifybounds",
            "sizex",
            "sizey",
            "tx",
            "ty",
            "tz",
            "reverseanchors",
            "anchoru",
            "anchorv",
            "rows",
            "cols",
            "orderu",
            "orderv",
            "interpu",
            "interpv",
            "texture",
            "normals",
        },
        "groupSOP": {
            "crname",
            "entity",
            "geotype",
            "usenumber",
            "ordered",
            "groupop",
            "pattern",
            "transfer",
            "range",
            "rangestart",
            "rangeend",
            "select",
            "select1",
            "select2",
            "filter",
            "usebounds",
            "boundtype",
            "size",
            "sizex",
            "sizey",
            "sizez",
            "t",
            "tx",
            "ty",
            "tz",
            "usenormal",
            "dir",
            "dirx",
            "diry",
            "dirz",
            "angle",
            "camera",
            "useedges",
            "doangle",
            "edgeangle",
            "dodepth",
            "edgestep",
            "point",
            "unshared",
            "boundarygroups",
            "grpequal",
            "not1",
            "grp1",
            "op1",
            "not2",
            "grp2",
            "op2",
            "cnvtype",
            "convertg",
            "cnvtname",
            "preserve",
            "oldname",
            "newname",
            "destroyname",
        },
        "holeSOP": {"group", "unbridge", "dist", "angle", "snap"},
        "importselectSOP": {
            "parent",
            "geometry",
            "reload",
            "comptang",
            "useparentanim",
            "shiftanimationstart",
            "sampleratemode",
            "samplerate",
            "playmode",
            "initialize",
            "start",
            "cue",
            "cuepulse",
            "cuepoint",
            "cuepointunit",
            "play",
            "index",
            "indexunit",
            "speed",
            "trim",
            "tstart",
            "tstartunit",
            "tend",
            "tendunit",
            "textendleft",
            "textendright",
        },
        "inSOP": {"label"},
        "inversecurveSOP": {"chop"},
        "isosurfaceSOP": {
            "func",
            "min",
            "minx",
            "miny",
            "minz",
            "max",
            "maxx",
            "maxy",
            "maxz",
            "divs",
            "divsx",
            "divsy",
            "divsz",
            "normals",
        },
        "joinSOP": {
            "group",
            "blend",
            "tolerance",
            "bias",
            "knotmult",
            "proximity",
            "dir",
            "joinop",
            "all",
            "skip",
            "inc",
            "loop",
            "prim",
        },
        "jointSOP": {
            "group",
            "divs",
            "preserve1",
            "preserve2",
            "orient",
            "smoothpath",
            "smoothtwist",
            "majoraxes",
            "mintwist",
            "lrscale",
            "lrscale1",
            "lrscale2",
            "lroffset",
            "lroffset1",
            "lroffset2",
        },
        "kinectSOP": {"hwversion", "sensor", "skeleton", "full", "seated", "neardepthmode", "normals"},
        "latticeSOP": {
            "group",
            "deformtype",
            "lattice",
            "points",
            "divs",
            "divsx",
            "divsy",
            "divsz",
            "kernel",
            "wyvill",
            "elendt",
            "blinn",
            "links",
            "radius",
        },
        "limitSOP": {
            "chop",
            "rord",
            "chanx",
            "chany",
            "chanz",
            "chanrx",
            "chanry",
            "chanrz",
            "chanrad",
            "chanradx",
            "chanrady",
            "chanradz",
            "chanr",
            "chang",
            "chanb",
            "chanalpha",
            "texturew",
            "customattr",
            "customattr0name",
            "customattr0chan0",
            "customattr0chan1",
            "customattr0chan2",
            "customattr0chan3",
            "output",
            "divisions",
            "rad",
            "flipsmooth",
            "dolimit",
            "xlimitmin",
            "xlimitmax",
            "ylimitmin",
            "ylimitmax",
            "zlimitmin",
            "zlimitmax",
            "texture",
            "orient",
            "lookat",
            "dorotate",
            "rotatex",
            "rotatey",
            "rotatez",
            "normals",
        },
        "lineSOP": {"pa", "pax", "pay", "paz", "pb", "pbx", "pby", "pbz", "points", "texture"},
        "linethickSOP": {
            "group",
            "startwidth",
            "startwidth1",
            "startwidth2",
            "endwidth",
            "endwidth1",
            "endwidth2",
            "divisions",
            "rows",
            "domain",
            "domain1",
            "domain2",
            "shape",
            "symmetric",
        },
        "lodSOP": {
            "steppercent",
            "distance",
            "minpercent",
            "borderweight",
            "lengthweight",
            "triangulate",
            "tstrips",
            "polysonly",
        },
        "lsystemSOP": {
            "type",
            "generations",
            "randscale",
            "randseed",
            "contangl",
            "contlength",
            "contwidth",
            "docolor",
            "colormap",
            "incu",
            "incv",
            "pointwidth",
            "rows",
            "cols",
            "tension",
            "smooth",
            "thickinit",
            "thickscale",
            "dotexture",
            "vertinc",
            "stepinit",
            "stepscale",
            "angleinit",
            "anglescale",
            "varb",
            "varc",
            "vard",
            "gravity",
            "pictop",
            "grpprefix",
            "chanprefix",
            "stampa",
            "stampb",
            "stampc",
            "rules",
        },
        "magnetSOP": {
            "deformgrp",
            "magnetgrp",
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
            "position",
            "color",
            "nml",
            "velocity",
        },
        "materialSOP": {"mat"},
        "metaballSOP": {
            "modifybounds",
            "rad",
            "radx",
            "rady",
            "radz",
            "t",
            "tx",
            "ty",
            "tz",
            "metaweight",
            "kernel",
            "expxy",
            "expz",
            "normals",
        },
        "modelSOP": {"num_points", "num_prims", "cook_time"},
        "noiseSOP": {
            "group",
            "attribute",
            "type",
            "seed",
            "period",
            "harmon",
            "spread",
            "rough",
            "exp",
            "numint",
            "amp",
            "keepnormals",
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
        },
        "objectmergeSOP": {"xform", "merge", "merge0sop"},
        "oculusriftSOP": {"model", "leftcontroller", "rightcontroller"},
        "openvrSOP": {"model"},
        "outSOP": {"label"},
        "particleSOP": {
            "sourcegrp",
            "prtype",
            "behave",
            "normals",
            "ptreuse",
            "timepreroll",
            "timeinc",
            "maxsteps",
            "jitter",
            "accurate",
            "rmunused",
            "attractmode",
            "reset",
            "resetpulse",
            "external",
            "wind",
            "turb",
            "period",
            "seed",
            "doid",
            "domass",
            "mass",
            "dodrag",
            "drag",
            "birth",
            "life",
            "lifevar",
            "alpha",
            "subattract",
            "birthcount",
            "birthpulse",
            "limitpos",
            "limitneg",
            "hit",
            "gaintan",
            "gainnorm",
            "splittype",
            "split",
            "splitvel",
            "splitvar",
        },
        "pointSOP": {
            "group",
            "t",
            "tx",
            "ty",
            "tz",
            "doweight",
            "weight",
            "doclr",
            "diff",
            "diffr",
            "diffg",
            "diffb",
            "alpha",
            "donml",
            "n",
            "nx",
            "ny",
            "nz",
            "douvw",
            "map",
            "mapu",
            "mapv",
            "mapw",
            "dowidth",
            "width",
            "dopscale",
            "pscale",
            "attr",
            "attr0name",
            "attr0type",
            "domass",
            "mass",
            "drag",
            "dotension",
            "tension",
            "dospringk",
            "springk",
            "dovel",
            "v",
            "vx",
            "vy",
            "vz",
            "doup",
            "up",
            "upx",
            "upy",
            "upz",
            "doradius",
            "radiusf",
            "doscale",
            "scalef",
            "doradialf",
            "radialf",
            "donormalf",
            "normalf",
            "doedgef",
            "edgef",
            "dodirf",
            "dirf",
        },
        "polyloftSOP": {
            "proximity",
            "consolidate",
            "dist",
            "minimize",
            "closeu",
            "closev",
            "creategroup",
            "polygroup",
            "method",
            "group",
            "prim",
            "point",
            "point0group",
        },
        "polypatchSOP": {
            "group",
            "basis",
            "connecttype",
            "closeu",
            "closev",
            "firstuclamp",
            "lastuclamp",
            "firstvclamp",
            "lastvclamp",
            "divisions",
            "divisionsx",
            "divisionsy",
            "polys",
        },
        "polyreduceSOP": {
            "reduce",
            "creases",
            "method",
            "percentage",
            "numpolys",
            "obj",
            "distance",
            "minpercent",
            "borderweight",
            "creaseweight",
            "lengthweight",
            "meshinvert",
            "triangulate",
            "keepedges",
            "originalpoints",
        },
        "polysplineSOP": {
            "group",
            "basis",
            "closure",
            "divide",
            "segsize",
            "polydivs",
            "edgedivs",
            "first",
            "last",
            "tension",
        },
        "polystitchSOP": {"stitch", "corners", "tol3d", "consolidate", "findcorner", "angle"},
        "primitiveSOP": {
            "group",
            "templategrp",
            "doxform",
            "dorot",
            "xord",
            "rord",
            "t",
            "r",
            "s",
            "attr",
            "closeu",
            "closev",
            "vtxsort",
            "vtxuoff",
            "vtxvoff",
            "p",
            "lookat",
            "upvector",
            "doclr",
            "diff",
            "alpha",
            "docrease",
            "crease",
            "pshapeu",
            "pshapev",
            "clampu",
            "clampv",
            "metaweight",
            "doweight",
            "doprender",
            "prtype",
        },
        "profileSOP": {
            "group",
            "method",
            "parametric",
            "smooth",
            "sdivs",
            "tolerance",
            "keepsurf",
            "delprof",
            "urange",
            "urange1",
            "urange2",
            "vrange",
            "vrange1",
            "vrange2",
            "order",
            "csharp",
            "maptype",
        },
        "projectSOP": {
            "facegroup",
            "surfgroup",
            "cycle",
            "method",
            "axis",
            "vector",
            "vector1",
            "vector2",
            "vector3",
            "projside",
            "rtolerance",
            "ftolerance",
            "accurate",
            "sdivs",
            "uvgap",
            "order",
            "csharp",
            "ufrom",
            "vfrom",
            "userange",
            "urange",
            "urange1",
            "urange2",
            "vrange",
            "vrange1",
            "vrange2",
            "maptype",
        },
        "railsSOP": {
            "xsectgrp",
            "railgrp",
            "cycle",
            "pairs",
            "firstl",
            "stretch",
            "scale",
            "roll",
            "usevtx",
            "vertex",
            "vertex1",
            "vertex2",
            "noflip",
            "usedir",
            "dir",
            "dirx",
            "diry",
            "dirz",
            "newg",
            "railname",
        },
        "rasterSOP": {"top", "direction", "downloadtype"},
        "raySOP": {
            "group",
            "method",
            "dotrans",
            "lookfar",
            "normal",
            "bounces",
            "bouncegeo",
            "putdist",
            "scale",
            "lift",
            "sample",
            "jitter",
            "seed",
            "newgrp",
            "hitgrp",
        },
        "rectangleSOP": {
            "orient",
            "camera",
            "camz",
            "cameraaspect",
            "cameraaspectx",
            "cameraaspecty",
            "modifybounds",
            "size",
            "sizex",
            "sizey",
            "t",
            "tx",
            "ty",
            "tz",
            "reverseanchors",
            "anchoru",
            "anchorv",
            "texture",
            "normals",
        },
        "refineSOP": {
            "group",
            "firstu",
            "domainu1",
            "secondu",
            "domainu2",
            "divsu",
            "firstv",
            "domainv1",
            "secondv",
            "domainv2",
            "divsv",
            "refineu",
            "refinev",
            "space",
            "unrefineu",
            "unrefinev",
            "tolu",
            "tolv",
        },
        "resampleSOP": {
            "group",
            "lod",
            "edge",
            "method",
            "measure",
            "dolength",
            "length",
            "dosegs",
            "segs",
            "last",
        },
        "revolveSOP": {
            "group",
            "surftype",
            "origin",
            "originx",
            "originy",
            "originz",
            "dir",
            "dirx",
            "diry",
            "dirz",
            "polys",
            "imperfect",
            "type",
            "angle",
            "beginangle",
            "endangle",
            "divs",
            "order",
            "cap",
        },
        "scriptSOP": {"callbacks", "setuppars"},
        "selectSOP": {"sop"},
        "sequenceblendSOP": {"blend", "dopos", "doclr", "donml", "douvw", "doup"},
        "skinSOP": {
            "uprims",
            "vprims",
            "surftype",
            "keepshape",
            "closev",
            "force",
            "orderv",
            "skinops",
            "inc",
            "prim",
            "polys",
        },
        "sortSOP": {
            "ptsort",
            "pointseed",
            "pointoffset",
            "pointprox",
            "pointproxx",
            "pointproxy",
            "pointproxz",
            "pointobj",
            "pointdir",
            "pointdirx",
            "pointdiry",
            "pointdirz",
            "primsort",
            "primseed",
            "primoffset",
            "primprox",
            "primproxx",
            "primproxy",
            "primproxz",
            "primobj",
            "primdir",
            "primdirx",
            "primdiry",
            "primdirz",
            "partsort",
            "partreverse",
            "partoffset",
            "partprox",
            "partproxx",
            "partproxy",
            "partproxz",
            "partobj",
            "partdir",
            "partdirx",
            "partdiry",
            "partdirz",
        },
        "sphereSOP": {
            "type",
            "surftype",
            "orientbounds",
            "modifybounds",
            "rord",
            "rad",
            "radx",
            "rady",
            "radz",
            "t",
            "tx",
            "ty",
            "tz",
            "r",
            "rx",
            "ry",
            "rz",
            "reverseanchors",
            "anchoru",
            "anchorv",
            "anchorw",
            "orient",
            "freq",
            "rows",
            "cols",
            "orderu",
            "orderv",
            "imperfect",
            "upole",
            "accurate",
            "texture",
            "normals",
        },
        "springSOP": {
            "timepreroll",
            "timeinc",
            "accurate",
            "attractmode",
            "reset",
            "resetpulse",
            "external",
            "externalx",
            "externaly",
            "externalz",
            "wind",
            "windx",
            "windy",
            "windz",
            "turb",
            "turbx",
            "turby",
            "turbz",
            "period",
            "seed",
            "fixed",
            "revertfixed",
            "copygroups",
            "domass",
            "mass",
            "dodrag",
            "drag",
            "springbehavior",
            "springk",
            "tension",
            "limitpos",
            "limitposx",
            "limitposy",
            "limitposz",
            "limitneg",
            "limitnegx",
            "limitnegy",
            "limitnegz",
            "hit",
            "gaintan",
            "gainnorm",
        },
        "sprinkleSOP": {"seed", "method", "numpoints", "consolidate", "neardist"},
        "spriteSOP": {
            "xyzchop",
            "camera",
            "widthchop",
            "colorchop",
            "alphachop",
            "perspectivewidth",
            "constantwidth",
            "constantwidthnear",
            "constantwitdhfar",
            "falloffstart",
            "falloffend",
        },
        "stitchSOP": {
            "group",
            "stitchop",
            "inc",
            "loop",
            "dir",
            "tolerance",
            "bias",
            "leftuv",
            "leftuv1",
            "leftuv2",
            "rightuv",
            "rightuv1",
            "rightuv2",
            "lrwidth",
            "lrwidth1",
            "lrwidth2",
            "dostitch",
            "dotangent",
            "sharp",
            "fixed",
            "lrscale",
            "lrscale1",
            "lrscale2",
        },
        "subdivideSOP": {
            "subdivide",
            "creases",
            "iterations",
            "overridecrease",
            "creaseweight",
            "outputcrease",
            "outcreasegroup",
            "closeholes",
            "surroundpoly",
            "bias",
        },
        "superquadSOP": {
            "type",
            "surftype",
            "modifybounds",
            "rad",
            "radx",
            "rady",
            "radz",
            "t",
            "tx",
            "ty",
            "tz",
            "reverseanchors",
            "anchoru",
            "anchorv",
            "anchorw",
            "orient",
            "rows",
            "cols",
            "expxy",
            "expz",
            "upole",
            "cusp",
            "angle",
            "texture",
            "normals",
        },
        "surfsectSOP": {
            "groupa",
            "groupb",
            "tol3d",
            "tol2d",
            "step",
            "boolop",
            "insidea",
            "insideb",
            "outsidea",
            "outsideb",
            "target",
            "creategroupa",
            "profilesa",
            "creategroupb",
            "profilesb",
            "mindholes",
            "join",
        },
        "sweepSOP": {
            "xgrp",
            "pathgrp",
            "refgrp",
            "cycle",
            "angle",
            "noflip",
            "skipcoin",
            "aimatref",
            "usevtx",
            "vertex",
            "scale",
            "twist",
            "roll",
            "newg",
            "sweepgrp",
            "skin",
            "fast",
        },
        "textSOP": {
            "font",
            "fontfile",
            "bold",
            "italic",
            "fontsizex",
            "fontsizey",
            "keepfontratio",
            "scalefontobboxheight",
            "output",
            "levelofdetail",
            "language",
            "readingdirection",
            "kerning",
            "kerning1",
            "kerning2",
            "linespacing",
            "alignx",
            "wordwrap",
            "wordwrapsize",
            "text",
            "legacyparsing",
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
        },
        "textureSOP": {
            "group",
            "texlayer",
            "type",
            "axis",
            "camera",
            "coord",
            "s",
            "su",
            "sv",
            "sw",
            "offset",
            "offsetu",
            "offsetv",
            "offsetw",
            "angle",
            "fixseams",
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
            "scaletwo",
            "scaletwox",
            "scaletwoy",
            "scaletwoz",
            "p",
            "px",
            "py",
            "pz",
        },
        "torusSOP": {
            "type",
            "surftype",
            "orient",
            "modifybounds",
            "rad",
            "radx",
            "rady",
            "t",
            "tx",
            "ty",
            "tz",
            "reverseanchors",
            "anchoru",
            "anchorv",
            "anchorw",
            "rows",
            "cols",
            "angleoffset",
            "imperfect",
            "orderu",
            "orderv",
            "angleu",
            "beginangleu",
            "endangleu",
            "anglev",
            "beginanglev",
            "endanglev",
            "closeu",
            "closev",
            "capu",
            "capv",
            "texture",
            "normals",
        },
        "traceSOP": {
            "top",
            "thresh",
            "addtexture",
            "delborder",
            "normals",
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
        "trailSOP": {
            "result",
            "length",
            "inc",
            "cache",
            "evalframe",
            "surftype",
            "close",
            "velscale",
            "reset",
            "resetpulse",
        },
        "transformSOP": {
            "group",
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
            "scale",
            "vlength",
            "lookat",
            "upvector",
            "upvectorx",
            "upvectory",
            "upvectorz",
            "forwarddir",
            "postxord",
            "posttx",
            "fromx",
            "tox",
            "postty",
            "fromy",
            "toy",
            "posttz",
            "fromz",
            "toz",
            "postscale",
            "postscalex",
            "postscaley",
            "postscalez",
        },
        "trimSOP": {"group", "optype", "individual", "bigloop"},
        "tristripSOP": {"group", "constrainstriplength", "maxstriplength"},
        "tubeSOP": {
            "type",
            "surftype",
            "orient",
            "orientbounds",
            "modifybounds",
            "rord",
            "t",
            "tx",
            "ty",
            "tz",
            "r",
            "rx",
            "ry",
            "rz",
            "rad",
            "rad1",
            "rad2",
            "height",
            "reverseanchors",
            "anchoru",
            "anchorv",
            "anchorw",
            "imperfect",
            "rows",
            "cols",
            "orderu",
            "orderv",
            "cap",
            "texture",
            "normals",
        },
        "twistSOP": {"group", "op", "paxis", "saxis", "p", "px", "py", "pz", "strength", "roll"},
        "vertexSOP": {
            "group",
            "doclr",
            "diff",
            "diffr",
            "diffg",
            "diffb",
            "alpha",
            "douvw",
            "map",
            "mapu",
            "mapv",
            "mapw",
            "docrease",
            "crease",
            "attr",
            "attr0name",
            "attr0type",
            "attr0value",
            "attr0value1",
            "attr0value2",
            "attr0value3",
            "attr0value4",
        },
        "wireframeSOP": {"group", "radius", "corners", "caps", "remove", "fast"},
        "zedSOP": {
            "zedtop",
            "sample",
            "reset",
            "resetpulse",
            "preview",
            "maxmemory",
            "resolution",
            "range",
            "normals",
            "texture",
            "filter",
            "consolidatepts",
        },
    }
    for op_type, expected_params in sop_param_guards.items():
        actual_params = {param["name"] for param in cards.get_operator(op_type)["key_params"]}
        assert expected_params.issubset(actual_params), op_type

    dat_param_guards = {
        "art-netDAT": {"callbacks", "columns", "poll", "language", "extension", "customext", "wordwrap"},
        "audiodevicesDAT": {
            "driver",
            "alldrivers",
            "input",
            "output",
            "callbacks",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
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
        },
        "choptoDAT": {
            "chop",
            "names",
            "latestsample",
            "output",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "clipDAT": {
            "edit",
            "file",
            "reload",
            "executeloc",
            "clip",
            "component",
            "framefirst",
            "frameloop",
            "exit",
            "printstate",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "convertDAT": {
            "how",
            "removeblank",
            "delimiters",
            "spacers",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "wordwrap",
        },
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "etherdreamDAT": {"callbacks", "columns", "poll", "language", "extension", "customext", "wordwrap"},
        "evaluateDAT": {
            "dat",
            "datexpr",
            "output",
            "expr",
            "outputsize",
            "dependency",
            "backslash",
            "xfirstrow",
            "xfirstcol",
            "extractrows",
            "rownamestart",
            "rowindexstart",
            "rownameend",
            "rowindexend",
            "rownames",
            "rowexpr",
            "fromcol",
            "extractcols",
            "colnamestart",
            "colindexstart",
            "colnameend",
            "colindexend",
            "colnames",
            "colexpr",
            "fromrow",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "format",
            "outputheaders",
            "outputlevel",
            "outputkey",
            "outputtype",
            "outputvalue",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "wordwrap",
        },
        "fifoDAT": {
            "callbacks",
            "executeloc",
            "fromop",
            "clamp",
            "maxlines",
            "clear",
            "firstrow",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "fileinDAT": {
            "file",
            "converttable",
            "refresh",
            "refreshpulse",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "fileoutDAT": {"file", "n", "write", "append", "language", "extension", "customext", "wordwrap"},
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
        "inDAT": {"label", "language", "extension", "customext", "wordwrap"},
        "indicesDAT": {"start", "end", "level", "origin", "language", "extension", "customext", "wordwrap"},
        "infoDAT": {"op", "passive", "language", "extension", "customext", "wordwrap"},
        "insertDAT": {
            "insert",
            "at",
            "index",
            "contents",
            "includenames",
            "replaceduplicate",
            "replace",
            "replace0names",
            "replace0expr",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "jsonDAT": {
            "filter",
            "output",
            "expression",
            "outputformat",
            "holdlast",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "keyboardinDAT": {
            "active",
            "perform",
            "keys",
            "shortcuts",
            "panels",
            "lrmodifiers",
            "callbacks",
            "executeloc",
            "fromop",
            "clamp",
            "maxlines",
            "clear",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "lookupDAT": {
            "index",
            "valueloction",
            "valuename",
            "valueindex",
            "includeheader",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "mediafileinfoDAT": {
            "file",
            "topchop",
            "reloadpulse",
            "opentimeout",
            "transpose",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "mergeDAT": {
            "dat",
            "how",
            "byname",
            "spacer",
            "unmatched",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "monitorsDAT": {
            "callbacks",
            "bounds",
            "monitors",
            "units",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "mpcdiDAT": {
            "file",
            "reloadpulse",
            "outputby",
            "bufferid",
            "regionid",
            "near",
            "far",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
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
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "posthresh",
            "contactthresh",
            "minrows",
            "doubleclickthresh",
            "callbacks",
            "executeloc",
            "fromop",
            "clamp",
            "maxlines",
            "clear",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "ndiDAT": {"callbacks", "extraips", "persistence", "language", "extension", "customext", "wordwrap"},
        "nullDAT": {"language", "extension", "customext", "wordwrap"},
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
            "customcombine",
            "namefilter",
            "typefilter",
            "parentshortcutfilter",
            "opshortcutfilter",
            "pathfilter",
            "parentfilter",
            "excludefilter",
            "wirepathfilter",
            "commentfilter",
            "tagsfilter",
            "textfilter",
            "parnamefilter",
            "parvaluefilter",
            "parexpressionfilter",
            "parnondefaultonly",
            "legacycols",
            "idcol",
            "namecol",
            "typecol",
            "pathcol",
            "relpathcol",
            "callbacks",
            "convertbool",
            "convertnone",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "outDAT": {"label", "language", "extension", "customext", "wordwrap"},
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
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "renderpickDAT": {
            "strategy",
            "responsetime",
            "pickradius",
            "rendertop",
            "allowmulticamera",
            "usepickableflags",
            "mergeinputdat",
            "activatecallbacks",
            "callbacks",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "reorderDAT": {
            "reorder",
            "method",
            "before",
            "after",
            "order",
            "delete",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "scriptDAT": {"callbacks", "setuppars", "language", "extension", "customext", "wordwrap"},
        "selectDAT": {
            "dat",
            "firstrow",
            "firstcol",
            "extractrows",
            "rownamestart",
            "rowindexstart",
            "rownameend",
            "rowindexend",
            "rownames",
            "rowexpr",
            "fromcol",
            "extractcols",
            "colnamestart",
            "colindexstart",
            "colnameend",
            "colindexend",
            "colnames",
            "colexpr",
            "fromrow",
            "output",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "serialdevicesDAT": {
            "callbacks",
            "usage",
            "refreshpulse",
            "enablepolling",
            "pollingtime",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "soptoDAT": {
            "sop",
            "extract",
            "group",
            "attrib",
            "uvforpts",
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "switchDAT": {"index", "extend", "language", "extension", "customext", "wordwrap"},
        "tableDAT": {
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
            "includenames",
            "fills",
            "fills0names",
            "fills0expr",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "touchinDAT": {
            "protocol",
            "address",
            "port",
            "shared",
            "active",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "touchoutDAT": {
            "protocol",
            "address",
            "port",
            "shared",
            "active",
            "redendantsends",
            "resend",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "transposeDAT": {"language", "extension", "customext", "wordwrap"},
        "tuioinDAT": {
            "protocol",
            "address",
            "port",
            "shared",
            "active",
            "callbacks",
            "executeloc",
            "fromop",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "udpinDAT": {
            "protocol",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "udpoutDAT": {
            "active",
            "protocol",
            "address",
            "port",
            "shared",
            "format",
            "localaddress",
            "localportmode",
            "localport",
            "callbacks",
            "executeloc",
            "fromop",
            "clamp",
            "maxlines",
            "clear",
            "bytes",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "udtinDAT": {
            "protocol",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "udtoutDAT": {
            "protocol",
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
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "videodevicesDAT": {
            "driver",
            "alldrivers",
            "input",
            "output",
            "callbacks",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "webclientDAT": {
            "active",
            "reqmethod",
            "url",
            "uploadfile",
            "request",
            "stop",
            "stream",
            "verifycert",
            "timeout",
            "includeheader",
            "authtype",
            "username",
            "pw",
            "appkey",
            "appsecret",
            "oauthtoken",
            "oauthsecret",
            "clientid",
            "token",
            "clear",
            "clamp",
            "maxlines",
            "callbacks",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "webrtcDAT": {
            "active",
            "reset",
            "bitratelimits",
            "minbitrate",
            "maxbitrate",
            "callbacks",
            "stun",
            "username",
            "password",
            "turn",
            "turn0server",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "webserverDAT": {
            "active",
            "restart",
            "port",
            "secure",
            "privatekey",
            "certificate",
            "password",
            "callbacks",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "websocketDAT": {
            "active",
            "netaddress",
            "port",
            "timeout",
            "callbacks",
            "executeloc",
            "fromop",
            "clamp",
            "maxlines",
            "clear",
            "bytes",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
        "xmlDAT": {
            "sgml",
            "merge",
            "mlabel",
            "label",
            "type",
            "text",
            "name",
            "value",
            "plabel",
            "ptype",
            "ptext",
            "pname",
            "pvalue",
            "oaname",
            "oavalue",
            "oclabel",
            "show",
            "lprefix",
            "language",
            "extension",
            "customext",
            "wordwrap",
        },
    }
    for op_type, expected_params in dat_param_guards.items():
        actual_params = {param["name"] for param in cards.get_operator(op_type)["key_params"]}
        assert expected_params.issubset(actual_params), op_type

    null_comp_params = {param["name"] for param in cards.get_operator("nullCOMP")["key_params"]}
    assert {"xord", "rord", "t", "r", "s", "parentxformsrc", "lookat"}.issubset(null_comp_params)

    replicator_comp_params = {param["name"] for param in cards.get_operator("replicatorCOMP")["key_params"]}
    assert {"method", "template", "opprefix", "master", "destination"}.issubset(replicator_comp_params)

    parameter_comp_params = {param["name"] for param in cards.get_operator("parameterCOMP")["key_params"]}
    assert {"op", "header", "pagescope", "parscope", "syncpage"}.issubset(parameter_comp_params)

    opviewer_comp_params = {param["name"] for param in cards.get_operator("opviewerCOMP")["key_params"]}
    assert {"opviewer", "interactive", "opcenter", "opscale", "topdirect"}.issubset(opviewer_comp_params)

    animation_comp_params = {param["name"] for param in cards.get_operator("animationCOMP")["key_params"]}
    assert {"timeref", "playmode", "play", "inputindexunit", "rangetype"}.issubset(animation_comp_params)

    time_comp_params = {param["name"] for param in cards.get_operator("timeCOMP")["key_params"]}
    assert {"play", "rate", "start", "end", "rangelimit", "independent"}.issubset(time_comp_params)

    list_comp_params = {param["name"] for param in cards.get_operator("listCOMP")["key_params"]}
    assert {"callbacks", "rows", "cols", "lockfirstrow", "reset"}.issubset(list_comp_params)

    blend_comp_params = {param["name"] for param in cards.get_operator("blendCOMP")["key_params"]}
    assert {"parenttype", "sequence", "blendw1", "blendm1", "shortrot"}.issubset(blend_comp_params)

    annotate_comp_params = {param["name"] for param in cards.get_operator("annotateCOMP")["key_params"]}
    assert {"Titletext", "Bodytext", "Mode", "Opviewerdisplay", "encloseops"}.issubset(annotate_comp_params)

    buildalist_comp_params = {param["name"] for param in cards.get_operator("buildalistCOMP")["key_params"]}
    assert {"callbacks", "onInitTable", "onInitCell", "onSelect", "storage"}.issubset(buildalist_comp_params)

    usd_comp_params = {param["name"] for param in cards.get_operator("usdCOMP")["key_params"]}
    assert {"file", "importmethod", "imp", "usematerial", "buildnetwork"}.issubset(usd_comp_params)

    bone_comp_params = {param["name"] for param in cards.get_operator("boneCOMP")["key_params"]}
    assert {"xord", "rord", "t", "r", "xrange", "displaycapture"}.issubset(bone_comp_params)

    actor_comp_params = {param["name"] for param in cards.get_operator("actorCOMP")["key_params"]}
    assert {"initialize", "active", "kinstate", "sops", "shape", "mass"}.issubset(actor_comp_params)

    engine_comp_params = {param["name"] for param in cards.get_operator("engineCOMP")["key_params"]}
    assert {"file", "reload", "reloadoncrash", "assetpaths", "clock"}.issubset(engine_comp_params)

    nvidia_flow_emitter_params = {
        param["name"] for param in cards.get_operator("nvidiaflowemitterCOMP")["key_params"]
    }
    assert {"active", "mode", "type", "shapeop", "linearvel"}.issubset(nvidia_flow_emitter_params)

    nvidia_flex_solver_params = {
        param["name"] for param in cards.get_operator("nvidiaflexsolverCOMP")["key_params"]
    }
    assert {"actors", "forces", "gravity", "init", "substeps", "bounds"}.issubset(nvidia_flex_solver_params)

    bullet_solver_params = {param["name"] for param in cards.get_operator("bulletsolverCOMP")["key_params"]}
    assert {"actors", "forces", "gravity", "dimension", "initall", "substeps"}.issubset(bullet_solver_params)

    constraint_comp_params = {param["name"] for param in cards.get_operator("constraintCOMP")["key_params"]}
    assert {"active", "type", "bodytobody", "actor1", "pivot1", "actor2"}.issubset(constraint_comp_params)

    fbx_comp_params = {param["name"] for param in cards.get_operator("fbxCOMP")["key_params"]}
    assert {"file", "importmethod", "imp", "importscale", "texdir", "mergegeo"}.issubset(fbx_comp_params)

    geotext_comp_params = {param["name"] for param in cards.get_operator("geotextCOMP")["key_params"]}
    assert {"mode", "text", "specdat", "specchop", "wordwrap", "facecam"}.issubset(geotext_comp_params)

    ambient_light_params = {param["name"] for param in cards.get_operator("ambientlightCOMP")["key_params"]}
    assert {"c", "dimmer", "render", "drawpriority", "lightmask"}.issubset(ambient_light_params)

    camera_blend_params = {param["name"] for param in cards.get_operator("camerablendCOMP")["key_params"]}
    assert {"parenttype", "sequence", "blendw1", "blendm1", "shortrot"}.issubset(camera_blend_params)

    environment_light_params = {
        param["name"] for param in cards.get_operator("environmentlightCOMP")["key_params"]
    }
    assert {"c", "dimmer", "envlightmap", "envlightmapquality", "envlightmaprotate"}.issubset(
        environment_light_params
    )

    force_comp_params = {param["name"] for param in cards.get_operator("forceCOMP")["key_params"]}
    assert {"active", "force", "relpos", "torque", "ffactive", "radius"}.issubset(force_comp_params)

    handle_comp_params = {param["name"] for param in cards.get_operator("handleCOMP")["key_params"]}
    assert {"target", "t", "weight", "twistonly", "falloff", "dorxlimit"}.issubset(handle_comp_params)

    impulse_force_params = {param["name"] for param in cards.get_operator("impulseforceCOMP")["key_params"]}
    assert {"pulse", "force", "relpos", "torque"}.issubset(impulse_force_params)

    light_comp_params = {param["name"] for param in cards.get_operator("lightCOMP")["key_params"]}
    assert {"c", "dimmer", "lighttype", "coneangle", "shadowtype"}.issubset(light_comp_params)

    shared_mem_in_params = {param["name"] for param in cards.get_operator("sharedmeminCOMP")["key_params"]}
    assert {"name", "parentshortcut", "opshortcut", "iop", "opviewer"}.issubset(shared_mem_in_params)

    shared_mem_out_params = {param["name"] for param in cards.get_operator("sharedmemoutCOMP")["key_params"]}
    assert {"active", "name", "parentshortcut", "opshortcut", "iop"}.issubset(shared_mem_out_params)

    delete_chop_params = {param["name"] for param in cards.get_operator("deleteCHOP")["key_params"]}
    assert {"delchannels", "discard", "scoped", "select", "delsamples"}.issubset(delete_chop_params)

    join_chop_params = {param["name"] for param in cards.get_operator("joinCHOP")["key_params"]}
    assert {"blendmethod", "blendfunc", "match", "quatrot", "shortrot"}.issubset(join_chop_params)

    rename_chop_params = {param["name"] for param in cards.get_operator("renameCHOP")["key_params"]}
    assert {"renamefrom", "renameto", "scope"}.issubset(rename_chop_params)

    reorder_chop_params = {param["name"] for param in cards.get_operator("reorderCHOP")["key_params"]}
    assert {"method", "orderref", "numpattern", "charpattern", "seed"}.issubset(reorder_chop_params)

    replace_chop_params = {param["name"] for param in cards.get_operator("replaceCHOP")["key_params"]}
    assert {"length", "first", "second", "notify", "srselect"}.issubset(replace_chop_params)

    resample_chop_params = {param["name"] for param in cards.get_operator("resampleCHOP")["key_params"]}
    assert {"method", "rate", "relative", "interp", "constarea", "correct"}.issubset(resample_chop_params)

    shuffle_chop_params = {param["name"] for param in cards.get_operator("shuffleCHOP")["key_params"]}
    assert {"method", "nval", "firstsample", "timeslice", "srselect"}.issubset(shuffle_chop_params)

    sort_chop_params = {param["name"] for param in cards.get_operator("sortCHOP")["key_params"]}
    assert {"method", "seed", "select", "indices", "names", "indexchannel"}.issubset(sort_chop_params)

    switch_chop_params = {param["name"] for param in cards.get_operator("switchCHOP")["key_params"]}
    assert {"indexfirst", "index", "extend"}.issubset(switch_chop_params)

    trim_chop_params = {param["name"] for param in cards.get_operator("trimCHOP")["key_params"]}
    assert {"relative", "start", "end", "discard", "timeslice", "srselect"}.issubset(trim_chop_params)

    audio_band_eq_params = {param["name"] for param in cards.get_operator("audiobandeqCHOP")["key_params"]}
    assert {"band1", "band2", "band3", "band8", "band16"}.issubset(audio_band_eq_params)

    audio_binaural_params = {param["name"] for param in cards.get_operator("audiobinauralCHOP")["key_params"]}
    assert {"active", "inputformat", "ambisonicsorder", "listener", "mappingtable"}.issubset(
        audio_binaural_params
    )

    audio_device_in_params = {
        param["name"] for param in cards.get_operator("audiodeviceinCHOP")["key_params"]
    }
    assert {"active", "driver", "device", "inputs", "format", "rate"}.issubset(audio_device_in_params)

    audio_device_out_params = {
        param["name"] for param in cards.get_operator("audiodeviceoutCHOP")["key_params"]
    }
    assert {"active", "driver", "device", "outputs", "adjustspeed", "clampoutput"}.issubset(
        audio_device_out_params
    )

    audio_dynamics_params = {param["name"] for param in cards.get_operator("audiodynamicsCHOP")["key_params"]}
    assert {"enablecompressor", "compressiontype", "chanlinkingcomp", "enablelimiter"}.issubset(
        audio_dynamics_params
    )

    audio_file_out_params = {param["name"] for param in cards.get_operator("audiofileoutCHOP")["key_params"]}
    assert {"filetype", "file", "codec", "record", "pause", "headerdat"}.issubset(audio_file_out_params)

    audio_filter_params = {param["name"] for param in cards.get_operator("audiofilterCHOP")["key_params"]}
    assert {"filter", "units", "frequency", "resonance", "roll"}.issubset(audio_filter_params)

    audio_movie_params = {param["name"] for param in cards.get_operator("audiomovieCHOP")["key_params"]}
    assert {"play", "moviefileintop", "opentimeout", "syncoffset", "audiotrack"}.issubset(audio_movie_params)

    audio_ndi_params = {param["name"] for param in cards.get_operator("audiondiCHOP")["key_params"]}
    assert {"play", "ndiintop", "timeslice", "srselect"}.issubset(audio_ndi_params)

    audio_oscillator_params = {
        param["name"] for param in cards.get_operator("audiooscillatorCHOP")["key_params"]
    }
    assert {"wavetype", "frequency", "octave", "amp", "bias", "rate"}.issubset(audio_oscillator_params)

    audio_para_eq_params = {param["name"] for param in cards.get_operator("audioparaeqCHOP")["key_params"]}
    assert {"frequency", "enableeq1", "bandwidth1", "enableeq2", "bandwidth2"}.issubset(audio_para_eq_params)

    audio_play_params = {param["name"] for param in cards.get_operator("audioplayCHOP")["key_params"]}
    assert {"device", "outputs", "file", "datlist", "mode", "trigger"}.issubset(audio_play_params)

    audio_render_params = {param["name"] for param in cards.get_operator("audiorenderCHOP")["key_params"]}
    assert {"active", "mode", "outputformat", "listenerobject", "source0object", "mesh"}.issubset(
        audio_render_params
    )

    audio_spectrum_params = {param["name"] for param in cards.get_operator("audiospectrumCHOP")["key_params"]}
    assert {"mode", "visual", "fftsize", "highfreqboost", "outputmenu", "outlength"}.issubset(
        audio_spectrum_params
    )

    audio_stream_in_params = {
        param["name"] for param in cards.get_operator("audiostreaminCHOP")["key_params"]
    }
    assert {"srctype", "url", "videostreamintop", "play", "webrtcconnection"}.issubset(audio_stream_in_params)

    audio_stream_out_params = {
        param["name"] for param in cards.get_operator("audiostreamoutCHOP")["key_params"]
    }
    assert {"active", "mode", "port", "streamname", "webrtcconnection", "webrtctrack"}.issubset(
        audio_stream_out_params
    )

    audio_vst_params = {param["name"] for param in cards.get_operator("audiovstCHOP")["key_params"]}
    assert {"file", "reloadpulse", "rate", "displaygui", "learnparms", "callbacks"}.issubset(audio_vst_params)

    audio_web_render_params = {
        param["name"] for param in cards.get_operator("audiowebrenderCHOP")["key_params"]
    }
    assert {"active", "webrender", "timeslice"}.issubset(audio_web_render_params)

    blacktrax_params = {param["name"] for param in cards.get_operator("blacktraxCHOP")["key_params"]}
    assert {"active", "port", "protocol", "samplerate", "outputformat", "mappingtable"}.issubset(
        blacktrax_params
    )

    blobtrack_params = {param["name"] for param in cards.get_operator("blobtrackCHOP")["key_params"]}
    assert {"searchmode", "maxblobs", "areaofinterest", "lostblobtimeout", "predicttype"}.issubset(
        blobtrack_params
    )

    bodytrack_params = {param["name"] for param in cards.get_operator("bodytrackCHOP")["key_params"]}
    assert {"modelfolder", "top", "bbox", "keypoints", "rotations", "peopletracking"}.issubset(
        bodytrack_params
    )

    facetrack_params = {param["name"] for param in cards.get_operator("facetrackCHOP")["key_params"]}
    assert {"modelfolder", "meshfile", "top", "bbox", "landmarks", "meshtransform"}.issubset(facetrack_params)

    gesture_params = {param["name"] for param in cards.get_operator("gestureCHOP")["key_params"]}
    assert {"playmode", "fitmethod", "numbeats", "blend", "interp", "resetcondition"}.issubset(gesture_params)

    hokuyo_params = {param["name"] for param in cards.get_operator("hokuyoCHOP")["key_params"]}
    assert {"interface", "port", "netaddress", "highsensitivity", "motorspeed", "output"}.issubset(
        hokuyo_params
    )

    joystick_params = {param["name"] for param in cards.get_operator("joystickCHOP")["key_params"]}
    assert {"source", "axisrange", "xaxis", "yaxis", "buttonarray", "axisdeadzone"}.issubset(joystick_params)

    kinect_params = {param["name"] for param in cards.get_operator("kinectCHOP")["key_params"]}
    assert {"hwversion", "sensor", "skeleton", "maxplayers", "worldspace", "facetracking"}.issubset(
        kinect_params
    )

    kinect_azure_params = {param["name"] for param in cards.get_operator("kinectazureCHOP")["key_params"]}
    assert {"top", "maxplayers", "bonelengths", "worldspace", "colorspace", "confidence"}.issubset(
        kinect_azure_params
    )

    leap_motion_params = {param["name"] for param in cards.get_operator("leapmotionCHOP")["key_params"]}
    assert {"api", "libfolder", "hmd", "statuschannels", "hands", "fingersperhand"}.issubset(
        leap_motion_params
    )

    dmx_in_params = {param["name"] for param in cards.get_operator("dmxinCHOP")["key_params"]}
    assert {"interface", "device", "format", "net", "subnet", "universe", "filterdat"}.issubset(dmx_in_params)

    dmx_out_params = {param["name"] for param in cards.get_operator("dmxoutCHOP")["key_params"]}
    assert {"interface", "format", "packetpersample", "universe", "netaddress", "sendartsync"}.issubset(
        dmx_out_params
    )

    freed_in_params = {param["name"] for param in cards.get_operator("freedinCHOP")["key_params"]}
    assert {"protocol", "netaddress", "port", "localaddress", "cameraid"}.issubset(freed_in_params)

    freed_out_params = {param["name"] for param in cards.get_operator("freedoutCHOP")["key_params"]}
    assert {"active", "protocol", "netaddress", "port", "localaddress"}.issubset(freed_out_params)

    laser_params = {param["name"] for param in cards.get_operator("laserCHOP")["key_params"]}
    assert {"source", "sop", "chop", "pop", "outputrate", "debugchan"}.issubset(laser_params)

    laser_device_params = {param["name"] for param in cards.get_operator("laserdeviceCHOP")["key_params"]}
    assert {"type", "device", "netaddress", "port", "queuetime", "queueunits"}.issubset(laser_device_params)

    ltc_in_params = {param["name"] for param in cards.get_operator("ltcinCHOP")["key_params"]}
    assert {"inputrate", "discrete", "totalframes", "totalsec", "userfields", "debugchans"}.issubset(
        ltc_in_params
    )

    ltc_out_params = {param["name"] for param in cards.get_operator("ltcoutCHOP")["key_params"]}
    assert {"playmode", "frame", "second", "minute", "hour", "framerate", "dropframe"}.issubset(
        ltc_out_params
    )

    midi_in_params = {param["name"] for param in cards.get_operator("midiinCHOP")["key_params"]}
    assert {"source", "device", "file", "simplified", "record", "controltype", "chan"}.issubset(
        midi_in_params
    )

    midi_out_params = {param["name"] for param in cards.get_operator("midioutCHOP")["key_params"]}
    assert {"destination", "device", "file", "id", "onebased", "writefile", "cookalways"}.issubset(
        midi_out_params
    )

    attribute_params = {param["name"] for param in cards.get_operator("attributeCHOP")["key_params"]}
    assert {"slerp", "rord", "scope"}.issubset(attribute_params)

    bullet_solver_chop_params = {
        param["name"] for param in cards.get_operator("bulletsolverCHOP")["key_params"]
    }
    assert {"comp", "xformspace", "collisioninfo", "trans", "rot", "linvel", "angvel"}.issubset(
        bullet_solver_chop_params
    )

    clip_params = {param["name"] for param in cards.get_operator("clipCHOP")["key_params"]}
    assert {"rdat", "callbacks", "rord", "transtion", "abspos", "rottype", "pauseend"}.issubset(clip_params)

    clip_blender_params = {param["name"] for param in cards.get_operator("clipblenderCHOP")["key_params"]}
    assert {"default", "datlist", "target", "playspeed", "reset", "resetpulse", "xtrans", "qenable"}.issubset(
        clip_blender_params
    )

    clock_params = {param["name"] for param in cards.get_operator("clockCHOP")["key_params"]}
    assert {
        "output",
        "hourformat",
        "houradjust",
        "startref",
        "ampm",
        "moonphase",
        "sunphase",
        "declination",
    }.issubset(clock_params)

    composite_chop_params = {param["name"] for param in cards.get_operator("compositeCHOP")["key_params"]}
    assert {"base", "match", "quatrot", "shortrot", "rotscope", "effect", "relative", "risefunc"}.issubset(
        composite_chop_params
    )

    copy_chop_params = {param["name"] for param in cards.get_operator("copyCHOP")["key_params"]}
    assert {"method", "output", "threshold", "remainder", "keep", "stamp", "copy", "copy0param"}.issubset(
        copy_chop_params
    )

    count_params = {param["name"] for param in cards.get_operator("countCHOP")["key_params"]}
    assert {
        "threshup",
        "threshdown",
        "retrigger",
        "retriggerunit",
        "triggeron",
        "output",
        "resetcondition",
    }.issubset(count_params)

    cplusplus_chop_params = {param["name"] for param in cards.get_operator("cplusplusCHOP")["key_params"]}
    assert {"plugin", "reinit", "reinitpulse", "unloadplugin", "timeslice", "scope", "srselect"}.issubset(
        cplusplus_chop_params
    )

    cross_params = {param["name"] for param in cards.get_operator("crossCHOP")["key_params"]}
    assert {"cross", "timeslice", "scope", "srselect"}.issubset(cross_params)

    cycle_params = {param["name"] for param in cards.get_operator("cycleCHOP")["key_params"]}
    assert {
        "before",
        "after",
        "mirror",
        "extremes",
        "blendmethod",
        "blendfunc",
        "blendregion",
        "step",
        "stepscope",
    }.issubset(cycle_params)

    dat_to_chop_params = {param["name"] for param in cards.get_operator("dattoCHOP")["key_params"]}
    assert {
        "dat",
        "extractrows",
        "extractcols",
        "output",
        "firstrow",
        "firstcolumn",
        "rownamestart",
        "rowindexstart",
        "rownameend",
        "rowindexend",
        "rownames",
        "rowexpr",
        "fromcol",
        "colnamestart",
        "colindexstart",
        "colnameend",
        "colindexend",
        "colnames",
        "colexpr",
        "fromrow",
    }.issubset(dat_to_chop_params)

    delay_params = {param["name"] for param in cards.get_operator("delayCHOP")["key_params"]}
    assert {"delay", "delayunit", "reset", "resetpulse", "srselect", "scope"}.issubset(delay_params)

    envelope_params = {param["name"] for param in cards.get_operator("envelopeCHOP")["key_params"]}
    assert {"method", "bounds", "width", "widthunit", "interp", "norm", "resample", "samplerate"}.issubset(
        envelope_params
    )

    event_params = {param["name"] for param in cards.get_operator("eventCHOP")["key_params"]}
    assert {
        "id",
        "index",
        "active",
        "input",
        "time",
        "adsr",
        "state",
        "attacktime",
        "attacktunit",
        "decaytime",
        "decaytunit",
        "sustaintime",
        "sustaintunit",
        "releasetime",
        "releasetunit",
        "resetcondition",
        "callbacks",
    }.issubset(event_params)

    expression_params = {param["name"] for param in cards.get_operator("expressionCHOP")["key_params"]}
    assert {"chanperexpr", "limitexpr", "limitnum", "expr", "expr0expr"}.issubset(expression_params)

    extend_params = {param["name"] for param in cards.get_operator("extendCHOP")["key_params"]}
    assert {"left", "right", "asis", "hold", "slope", "cycle", "mirror", "default", "defval"}.issubset(
        extend_params
    )

    fan_params = {param["name"] for param in cards.get_operator("fanCHOP")["key_params"]}
    assert {
        "fanop",
        "channame",
        "range",
        "clamp",
        "loop",
        "zero",
        "alloff",
        "set0",
        "setneg",
        "quantize",
    }.issubset(fan_params)

    feedback_chop_params = {param["name"] for param in cards.get_operator("feedbackCHOP")["key_params"]}
    assert {"output", "delta", "reset", "resetpulse"}.issubset(feedback_chop_params)

    file_in_chop_params = {param["name"] for param in cards.get_operator("fileinCHOP")["key_params"]}
    assert {
        "file",
        "nameoption",
        "name",
        "rateoption",
        "rate",
        "left",
        "right",
        "defval",
        "renamefrom",
        "renameto",
        "overridpattern",
        "overridevalue",
        "refresh",
        "refreshpulse",
    }.issubset(file_in_chop_params)

    file_out_chop_params = {param["name"] for param in cards.get_operator("fileoutCHOP")["key_params"]}
    assert {"active", "file", "interval", "write", "scope"}.issubset(file_out_chop_params)

    filter_params = {param["name"] for param in cards.get_operator("filterCHOP")["key_params"]}
    assert {
        "type",
        "effect",
        "width",
        "widthunit",
        "spike",
        "ramptolerance",
        "ramprate",
        "passes",
        "cutoff",
        "speedcoeff",
        "slopecutoff",
        "slopedownreset",
        "slopedownmax",
        "slopeupreset",
        "slopeupmax",
        "reset",
        "resetpulse",
        "filterpersample",
        "scope",
    }.issubset(filter_params)
    assert {"filtertype", "filterwidth", "resetcondition"}.isdisjoint(filter_params)

    function_chop_params = {param["name"] for param in cards.get_operator("functionCHOP")["key_params"]}
    assert {
        "func",
        "angunit",
        "match",
        "error",
        "pinfval",
        "ninfval",
        "domval",
        "divval",
        "baseval",
        "expval",
        "scope",
    }.issubset(function_chop_params)

    handle_params = {param["name"] for param in cards.get_operator("handleCHOP")["key_params"]}
    assert {"source", "fixed", "iterations", "init", "preroll", "delta"}.issubset(handle_params)

    hog_params = {param["name"] for param in cards.get_operator("hogCHOP")["key_params"]}
    assert {"active", "cookalways", "delay", "delayunit"}.issubset(hog_params)

    hold_params = {param["name"] for param in cards.get_operator("holdCHOP")["key_params"]}
    assert {
        "sample",
        "offtoon",
        "whileon",
        "ontooff",
        "whileoff",
        "valuechange",
        "hold",
        "holdpulse",
        "holdsamples",
    }.issubset(hold_params)

    import_select_chop_params = {
        param["name"] for param in cards.get_operator("importselectCHOP")["key_params"]
    }
    assert {
        "parent",
        "taketype",
        "blendshape",
        "reload",
        "useparentanim",
        "animation",
        "shiftanimationstart",
        "sampleratemode",
        "samplerate",
        "playmode",
        "index",
        "indexunit",
        "play",
        "speed",
        "trim",
        "tstart",
        "tstartunit",
        "tend",
        "tendunit",
        "cue",
        "cuepulse",
        "cuepoint",
        "cuepointunit",
        "textendleft",
        "textendright",
        "scope",
    }.issubset(import_select_chop_params)

    in_chop_params = {param["name"] for param in cards.get_operator("inCHOP")["key_params"]}
    assert {"label", "numchannels", "channames", "scope"}.issubset(in_chop_params)

    info_params = {param["name"] for param in cards.get_operator("infoCHOP")["key_params"]}
    assert {
        "op",
        "infotype",
        "iscope",
        "values",
        "range",
        "range1",
        "range2",
        "passive",
        "childcooktime",
    }.issubset(info_params)

    interpolate_params = {param["name"] for param in cards.get_operator("interpolateCHOP")["key_params"]}
    assert {"blendfunc", "overlap", "avg", "first", "last", "match", "scope"}.issubset(interpolate_params)

    inverse_curve_params = {param["name"] for param in cards.get_operator("inversecurveCHOP")["key_params"]}
    assert {
        "guide",
        "bonestart",
        "boneend",
        "span",
        "span1",
        "span2",
        "interpolation",
        "order",
        "upvector",
        "upvectorx",
        "upvectory",
        "upvectorz",
        "mapexports",
    }.issubset(inverse_curve_params)

    inverse_kin_params = {param["name"] for param in cards.get_operator("inversekinCHOP")["key_params"]}
    assert {
        "solvertype",
        "boneroot",
        "boneend",
        "endaffector",
        "twistaffector",
        "iktwist",
        "ikdampen",
        "curve",
    }.issubset(inverse_kin_params)

    keyboard_in_params = {param["name"] for param in cards.get_operator("keyboardinCHOP")["key_params"]}
    assert {
        "active",
        "keys",
        "modifiers",
        "ignore",
        "none",
        "ctrl",
        "alt",
        "ctrlalt",
        "shift",
        "shiftalt",
        "shiftctrl",
        "shiftctrlalt",
        "channelnames",
        "panels",
        "rate",
        "left",
        "right",
        "defval",
    }.issubset(keyboard_in_params)

    keyframe_params = {param["name"] for param in cards.get_operator("keyframeCHOP")["key_params"]}
    assert {"animation", "rate", "left", "right", "defval", "timeslice", "scope", "srselect"}.issubset(
        keyframe_params
    )

    lag_params = {param["name"] for param in cards.get_operator("lagCHOP")["key_params"]}
    assert {
        "lagmethod",
        "lag",
        "lag1",
        "lag2",
        "lagunit",
        "overshoot",
        "overshoot1",
        "overshoot2",
        "overshootunit",
        "clamp",
        "slope",
        "slope1",
        "slope2",
        "aclamp",
        "accel",
        "accel1",
        "accel2",
        "lagsamples",
        "snap",
        "threshold",
        "reset",
        "resetpulse",
    }.issubset(lag_params)

    leuze_params = {param["name"] for param in cards.get_operator("leuzerod4CHOP")["key_params"]}
    assert {
        "active",
        "netaddress",
        "port",
        "rod4porotocol",
        "inputcoordinate",
        "outputmode",
        "maxblobs",
        "maxpointdistance",
        "maxblobmovement",
        "areaofinterest",
        "maxdistance",
        "lowerleft",
        "lowerleft1",
        "lowerleft2",
        "upperright",
        "upperright1",
        "upperright2",
        "allowmovementoutside",
        "boundingboxmask",
        "rotate",
    }.issubset(leuze_params)

    lfo_params = {param["name"] for param in cards.get_operator("lfoCHOP")["key_params"]}
    assert {
        "wavetype",
        "play",
        "frequency",
        "offset",
        "amp",
        "bias",
        "phase",
        "resetcondition",
        "reset",
        "resetpulse",
        "channelname",
        "rate",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(lfo_params)
    assert {"type", "amplitude"}.isdisjoint(lfo_params)

    limit_chop_params = {param["name"] for param in cards.get_operator("limitCHOP")["key_params"]}
    assert {
        "type",
        "min",
        "max",
        "positive",
        "norm",
        "underflow",
        "quantvalue",
        "vstep",
        "voffset",
        "quantindex",
        "istep",
        "istepunit",
        "ioffset",
        "ioffsetunit",
        "scope",
    }.issubset(limit_chop_params)

    logic_params = {param["name"] for param in cards.get_operator("logicCHOP")["key_params"]}
    assert {
        "convert",
        "preop",
        "chanop",
        "chopop",
        "match",
        "align",
        "bound",
        "boundmin",
        "boundmax",
        "timeslice",
        "scope",
    }.issubset(logic_params)
    assert "inputop" not in logic_params

    lookup_params = {param["name"] for param in cards.get_operator("lookupCHOP")["key_params"]}
    assert {
        "index",
        "index1",
        "index2",
        "cyclic",
        "chanmatch",
        "match",
        "interp",
        "left",
        "right",
        "defval",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(lookup_params)

    merge_params = {param["name"] for param in cards.get_operator("mergeCHOP")["key_params"]}
    assert {
        "align",
        "duplicate",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(merge_params)

    midi_in_map_params = {param["name"] for param in cards.get_operator("midiinmapCHOP")["key_params"]}
    assert {
        "device",
        "id",
        "sliders",
        "buttons",
        "bvelocity",
        "squeue",
        "rate",
        "left",
        "right",
        "defval",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(midi_in_map_params)

    mosys_params = {param["name"] for param in cards.get_operator("mosysCHOP")["key_params"]}
    assert {
        "active",
        "protocol",
        "netaddress",
        "port",
        "localaddress",
        "cameraid",
        "screenwidth",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(mosys_params)

    mouse_in_params = {param["name"] for param in cards.get_operator("mouseinCHOP")["key_params"]}
    assert {
        "active",
        "output",
        "posxname",
        "posyname",
        "lbuttonname",
        "rbuttonname",
        "mbuttonname",
        "wheel",
        "wheelinc",
        "monitor",
        "panels",
        "rate",
        "left",
        "right",
        "defval",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(mouse_in_params)

    mouse_out_params = {param["name"] for param in cards.get_operator("mouseoutCHOP")["key_params"]}
    assert {
        "posu",
        "posv",
        "lbuttonname",
        "rbuttonname",
        "mbuttonname",
        "cookalways",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(mouse_out_params)

    ncam_params = {param["name"] for param in cards.get_operator("ncamCHOP")["key_params"]}
    assert {
        "active",
        "protocol",
        "netaddress",
        "port",
        "cameraview",
        "cameraproj",
        "cameraprops",
        "timecode",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(ncam_params)

    noise_chop_params = {param["name"] for param in cards.get_operator("noiseCHOP")["key_params"]}
    assert {
        "type",
        "seed",
        "period",
        "periodunit",
        "harmon",
        "spread",
        "rough",
        "exp",
        "numint",
        "amp",
        "reset",
        "resetpulse",
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
        "constraint",
        "constrstart",
        "constrend",
        "constrmean",
        "normal",
        "channelname",
        "start",
        "end",
        "rate",
        "left",
        "right",
        "defval",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(noise_chop_params)
    assert "roughness" not in noise_chop_params

    oak_device_params = {param["name"] for param in cards.get_operator("oakdeviceCHOP")["key_params"]}
    assert {
        "active",
        "sensor",
        "refreshpulse",
        "initialize",
        "start",
        "play",
        "gotodone",
        "callbacks",
        "stream0name",
        "stream0frequency",
        "stream0top",
        "outinit",
        "outinitfail",
        "outready",
        "outrunning",
        "outdone",
        "outtimercount",
        "outrunningcount",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(oak_device_params)

    oak_select_params = {param["name"] for param in cards.get_operator("oakselectCHOP")["key_params"]}
    assert {
        "active",
        "chop",
        "stream",
        "queuesize",
        "maxitems",
        "outputformat",
        "firstsample",
        "rate",
        "callbacks",
        "setuppars",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(oak_select_params)

    object_chop_params = {param["name"] for param in cards.get_operator("objectCHOP")["key_params"]}
    assert {
        "dat",
        "target",
        "reference",
        "swaptargetreference",
        "compute",
        "mat",
        "mat3",
        "measure",
        "translate",
        "rotate",
        "scale",
        "quat",
        "bear",
        "singlebear",
        "distance",
        "invsqr",
        "xord",
        "rord",
        "includeorderchans",
        "bearingref",
        "bearing",
        "bearingx",
        "bearingy",
        "bearingz",
        "tscopex",
        "tscopey",
        "tscopez",
        "appendattribs",
        "smoothrotate",
        "nameformat",
        "outputrange",
        "cookpast",
        "start",
        "end",
        "left",
        "right",
        "defval",
        "timeslice",
        "scope",
        "srselect",
    }.issubset(object_chop_params)

    oculus_audio_params = {param["name"] for param in cards.get_operator("oculusaudioCHOP")["key_params"]}
    assert {
        "active",
        "headobject",
        "sourceobject",
        "minrange",
        "maxrange",
        "diameter",
        "bandhint",
        "reflectrevert",
        "attenuation",
        "attenuationscale",
        "boxroommode",
        "roomsize",
        "roomsizex",
        "roomsizey",
        "roomsizez",
        "roomleftrelfect",
        "roomrightrelfect",
        "roombottomrelfect",
        "roomtoprelfect",
        "roomfrontrelfect",
        "roombackrelfect",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(oculus_audio_params)

    oculus_rift_params = {param["name"] for param in cards.get_operator("oculusriftCHOP")["key_params"]}
    assert {
        "active",
        "output",
        "hmd",
        "leftcontroller",
        "rightcontroller",
        "leftmatrix",
        "rightmatrix",
        "orientation",
        "recenter",
        "acceleration",
        "velocity",
        "deviceinfo",
        "controllerbuttons",
        "near",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(oculus_rift_params)

    openvr_params = {param["name"] for param in cards.get_operator("openvrCHOP")["key_params"]}
    assert {
        "active",
        "output",
        "sensor",
        "projmatrices",
        "trackers",
        "frametimings",
        "actions",
        "skeletons",
        "maxtrackers",
        "firsttracker",
        "orientation",
        "generalinfo",
        "near",
        "far",
        "unitscale",
        "customactions",
        "actionmanifest",
        "uselegacynames",
        "skeletonrange",
        "withcontroller",
        "withoutcontroller",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(openvr_params)

    optitrack_in_params = {param["name"] for param in cards.get_operator("optitrackinCHOP")["key_params"]}
    assert {
        "active",
        "connectiontype",
        "mutlicast",
        "unicast",
        "netaddress",
        "localaddress",
        "commandport",
        "dataport",
        "rate",
        "resetpulse",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(optitrack_in_params)

    osc_in_params = {param["name"] for param in cards.get_operator("oscinCHOP")["key_params"]}
    assert {
        "active",
        "protocol",
        "msging",
        "multicastmsging",
        "netaddress",
        "port",
        "localaddress",
        "oscaddressscope",
        "useglobalrate",
        "samplerate",
        "queued",
        "queuevariance",
        "queuevarianceunit",
        "maxqueue",
        "maxqueueunit",
        "adjusttime",
        "adjusttimeunit",
        "stripsegments",
        "resetchannels",
        "resetchannelspulse",
        "resetvalues",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(osc_in_params)

    osc_out_params = {param["name"] for param in cards.get_operator("oscoutCHOP")["key_params"]}
    assert {
        "active",
        "protocol",
        "msging",
        "multicastmsging",
        "reliablemsging",
        "netaddress",
        "port",
        "localaddress",
        "maxsize",
        "maxsizeunit",
        "cookalways",
        "numericformat",
        "int",
        "float",
        "double",
        "format",
        "sample",
        "timeslice",
        "transpose",
        "transposename",
        "maxbytes",
        "sendevents",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(osc_out_params)

    out_chop_params = {param["name"] for param in cards.get_operator("outCHOP")["key_params"]}
    assert {
        "label",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(out_chop_params)

    override_params = {param["name"] for param in cards.get_operator("overrideCHOP")["key_params"]}
    assert {
        "match",
        "index",
        "name",
        "makeindex",
        "indexname",
        "cookmonitor",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(override_params)

    pangolin_params = {param["name"] for param in cards.get_operator("pangolinCHOP")["key_params"]}
    assert {
        "active",
        "source",
        "sop",
        "chop",
        "pop",
        "zone",
        "ratemode",
        "percent",
        "sample",
        "rate",
        "repeat",
        "vector",
        "resend",
        "enableout",
        "disableout",
        "blackout",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(pangolin_params)

    pan_tilt_params = {param["name"] for param in cards.get_operator("pantiltCHOP")["key_params"]}
    assert {
        "reset",
        "resetvals",
        "resetvals1",
        "resetvals2",
        "clamppan",
        "panrange",
        "panrangemin",
        "panrangemax",
        "clamptilt",
        "tiltrange",
        "tiltrangemin",
        "tiltrangemax",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(pan_tilt_params)

    parameter_chop_params = {param["name"] for param in cards.get_operator("parameterCHOP")["key_params"]}
    assert {
        "ops",
        "fetch",
        "partypes",
        "sequencetypes",
        "sequences",
        "pargroups",
        "parameter",
        "custom",
        "builtin",
        "nameformat",
        "op",
        "path",
        "renamefrom",
        "renameto",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(parameter_chop_params)

    pattern_params = {param["name"] for param in cards.get_operator("patternCHOP")["key_params"]}
    assert {
        "wavetype",
        "const",
        "sin",
        "cos",
        "tri",
        "ramp",
        "rampsamples",
        "square",
        "pulse",
        "random",
        "randomcycle",
        "randomnonrepint",
        "step",
        "rampcyclic",
        "length",
        "numcycles",
        "steppercycle",
        "numsteps",
        "bias",
        "seed",
        "phase",
        "phasestep",
        "taper",
        "taper1",
        "taper2",
        "taperdecay",
        "amp",
        "offset",
        "fromrange",
        "fromrange1",
        "fromrange2",
        "torange",
        "torange1",
        "torange2",
        "integer",
        "ceiling",
        "floor",
        "round",
        "reverse",
        "randomize",
        "channelname",
        "combine",
        "append",
        "insert",
        "replace",
        "add",
        "multiply",
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
    }.issubset(pattern_params)

    perform_params = {param["name"] for param in cards.get_operator("performCHOP")["key_params"]}
    assert {
        "fps",
        "msec",
        "cook",
        "droppedframes",
        "mvreadahead",
        "gpumemused",
        "totalgpumem",
        "activeops",
        "deactivatedops",
        "totalops",
        "cpumemused",
        "cookstate",
        "cookrealtime",
        "cookrate",
        "timeslicestep",
        "timeslicemsec",
        "performmode",
        "performfocus",
        "gputemp",
        "aclinestatus",
        "batterycharging",
        "batterylife",
        "batterytime",
        "activeexpressions",
        "optimizedexpression",
        "cachedexpressions",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(perform_params)

    phaser_params = {param["name"] for param in cards.get_operator("phaserCHOP")["key_params"]}
    assert {
        "edge",
        "nsamples",
        "outputformat",
        "samples",
        "channels",
        "extend",
        "clamp",
        "cycle",
        "mirror",
        "mirrorslope",
        "add",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(phaser_params)

    pipe_in_params = {param["name"] for param in cards.get_operator("pipeinCHOP")["key_params"]}
    assert {
        "mode",
        "client",
        "server",
        "address",
        "port",
        "active",
        "queued",
        "mintarget",
        "mintargetunit",
        "maxtarget",
        "maxtargetunit",
        "maxqueue",
        "maxqueueunit",
        "adjusttime",
        "adjusttimeunit",
        "reset",
        "allowscripts",
        "echo",
        "off",
        "on",
        "raw",
        "callbacks",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(pipe_in_params)

    pipe_out_params = {param["name"] for param in cards.get_operator("pipeoutCHOP")["key_params"]}
    assert {
        "mode",
        "client",
        "server",
        "address",
        "port",
        "active",
        "sendinput",
        "sendsingle",
        "sample",
        "scur",
        "sstart",
        "upload",
        "script",
        "sendscript",
        "cookalways",
        "pulse",
        "echo",
        "callbacks",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(pipe_out_params)

    posistage_net_params = {param["name"] for param in cards.get_operator("posistagenetCHOP")["key_params"]}
    assert {
        "active",
        "netaddress",
        "port",
        "samplerate",
        "pos",
        "ori",
        "speed",
        "accel",
        "targetpos",
        "resetpulse",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(posistage_net_params)

    pulse_params = {param["name"] for param in cards.get_operator("pulseCHOP")["key_params"]}
    assert {
        "number",
        "interp",
        "nointerp",
        "linear",
        "easein",
        "easeout",
        "cosine",
        "cubic",
        "connect",
        "width",
        "widthunit",
        "limit",
        "nolimit",
        "clamp",
        "min",
        "max",
        "minspacing",
        "cascade",
        "outpulse",
        "pulseunit",
        "separateoutchan",
        "nonadditives",
        "lastpulse",
        "pulse",
        "pulse0value",
        "channelname",
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
    }.issubset(pulse_params)

    record_params = {param["name"] for param in cards.get_operator("recordCHOP")["key_params"]}
    assert {
        "record",
        "off",
        "on",
        "add",
        "auto",
        "sample",
        "scur",
        "sslice",
        "interp",
        "hold",
        "linear",
        "cubic",
        "output",
        "full",
        "curframe",
        "frame1",
        "slice",
        "segment",
        "segment1",
        "segment2",
        "segmentunit",
        "reset",
        "resetcondition",
        "offtoon",
        "ontooff",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
        "commonrenamefrom",
        "commonrenameto",
    }.issubset(record_params)

    render_pick_params = {param["name"] for param in cards.get_operator("renderpickCHOP")["key_params"]}
    assert {
        "rendertop",
        "strategy",
        "select",
        "holdfirst",
        "holdlast",
        "always",
        "clearprev",
        "responsetime",
        "nextcook",
        "thiscook",
        "pickradius",
        "pickradstep",
        "pickcirstep",
        "usepickableflags",
        "includenonpickable",
        "pickingby",
        "panel",
        "parameters",
        "panelvalue",
        "picku",
        "pickv",
        "activatecallbacks",
        "callbacks",
        "position",
        "no",
        "sopspace",
        "worldspace",
        "cameraspace",
        "relativetoobj",
        "normal",
        "referenceobj",
        "color",
        "uv",
        "path",
        "depth",
        "instanceid",
        "customattrib1",
        "customattrib1type",
        "customattrib2",
        "customattrib2type",
        "customattrib3",
        "customattrib3type",
        "customattrib4",
        "customattrib4type",
        "timeslice",
        "scope",
        "srselect",
        "exportmethod",
        "autoexportroot",
        "exporttable",
    }.issubset(render_pick_params)

    renderstream_in_params = {
        param["name"] for param in cards.get_operator("renderstreaminCHOP")["key_params"]
    }
    assert {"active", "timeout", "streamindex", "schemadat"}.issubset(renderstream_in_params)

    script_chop_params = {param["name"] for param in cards.get_operator("scriptCHOP")["key_params"]}
    assert {"callbacks", "setuppars", "modoutsidecook", "timeslice", "srselect"}.issubset(script_chop_params)

    scurve_params = {param["name"] for param in cards.get_operator("scurveCHOP")["key_params"]}
    assert {
        "type",
        "length",
        "prepend",
        "append",
        "steepness",
        "linearize",
        "bias",
        "fromrange",
        "torange",
        "channelname",
        "rate",
        "left",
        "right",
        "defval",
    }.issubset(scurve_params)

    sequencer_params = {param["name"] for param in cards.get_operator("sequencerCHOP")["key_params"]}
    assert {"datlist", "blendscope", "addscope", "queue", "trigger", "reset", "resetpulse"}.issubset(
        sequencer_params
    )

    serial_params = {param["name"] for param in cards.get_operator("serialCHOP")["key_params"]}
    assert {
        "active",
        "state",
        "port",
        "baudrate",
        "baudmenu",
        "databits",
        "parity",
        "stopbits",
        "script",
        "script0callback",
    }.issubset(serial_params)

    shared_mem_in_chop_params = {
        param["name"] for param in cards.get_operator("sharedmeminCHOP")["key_params"]
    }
    assert {"active", "name", "memtype", "timeslice", "srselect"}.issubset(shared_mem_in_chop_params)

    shared_mem_out_chop_params = {
        param["name"] for param in cards.get_operator("sharedmemoutCHOP")["key_params"]
    }
    assert {"active", "name", "memtype", "timeslice", "srselect"}.issubset(shared_mem_out_chop_params)

    shift_params = {param["name"] for param in cards.get_operator("shiftCHOP")["key_params"]}
    assert {"reference", "relative", "start", "startunit", "end", "endunit", "scroll", "scrollunit"}.issubset(
        shift_params
    )

    slope_params = {param["name"] for param in cards.get_operator("slopeCHOP")["key_params"]}
    assert {"type", "method", "slopesamples", "timeslice", "srselect"}.issubset(slope_params)

    sop_to_chop_params = {param["name"] for param in cards.get_operator("soptoCHOP")["key_params"]}
    assert {
        "sop",
        "group",
        "position",
        "colorrgb",
        "coloralpha",
        "normal",
        "textureuv",
        "texturew",
        "pointindex",
        "normpos",
        "custom",
        "attribscope",
        "renamescope",
        "transobj",
        "rate",
    }.issubset(sop_to_chop_params)

    speed_params = {param["name"] for param in cards.get_operator("speedCHOP")["key_params"]}
    assert {
        "order",
        "speed",
        "constant1",
        "constant2",
        "constant3",
        "limittype",
        "min",
        "max",
        "speedsamples",
        "resetcondition",
        "resetvalue",
        "reset",
        "resetpulse",
        "resetonstart",
    }.issubset(speed_params)

    splice_params = {param["name"] for param in cards.get_operator("spliceCHOP")["key_params"]}
    assert {
        "outputtrimmed",
        "direction",
        "start",
        "startunits",
        "trimmethod",
        "trimlength",
        "trimlengthunits",
        "insertmethod",
        "insertlength",
        "insertunits",
        "insertinterp",
        "match",
        "unmatchedinterp",
    }.issubset(splice_params)

    spring_params = {param["name"] for param in cards.get_operator("springCHOP")["key_params"]}
    assert {
        "springk",
        "mass",
        "dampingk",
        "method",
        "condfromchan",
        "initpos",
        "initspeed",
        "reset",
        "resetpulse",
    }.issubset(spring_params)

    st2110_device_params = {param["name"] for param in cards.get_operator("st2110deviceCHOP")["key_params"]}
    assert {
        "active",
        "driver",
        "device",
        "usedhcp",
        "ipaddress",
        "subnet",
        "gateway",
        "ptpprofile",
        "ptpaddress",
        "ptpdomain",
        "igmpversion",
        "enablesps",
        "spsusedhcp",
        "spsipaddress",
        "spssubnet",
        "spsgateway",
    }.issubset(st2110_device_params)

    stretch_params = {param["name"] for param in cards.get_operator("stretchCHOP")["key_params"]}
    assert {
        "interp",
        "constarea",
        "relative",
        "start",
        "startunit",
        "end",
        "endunit",
        "scale",
        "reverse",
    }.issubset(stretch_params)

    stype_in_params = {param["name"] for param in cards.get_operator("stypeinCHOP")["key_params"]}
    assert {"protocol", "netaddress", "port", "localaddress", "active", "padding"}.issubset(stype_in_params)

    stype_out_params = {param["name"] for param in cards.get_operator("stypeoutCHOP")["key_params"]}
    assert {
        "active",
        "protocol",
        "netaddress",
        "port",
        "localaddress",
        "timecodeop",
        "packetnumber",
    }.issubset(stype_out_params)

    sync_in_params = {param["name"] for param in cards.get_operator("syncinCHOP")["key_params"]}
    assert {"active", "multicastaddress", "port", "timeslice", "srselect"}.issubset(sync_in_params)

    sync_out_params = {param["name"] for param in cards.get_operator("syncoutCHOP")["key_params"]}
    assert {
        "active",
        "multicastaddress",
        "port",
        "localaddress",
        "localportmode",
        "localport",
        "banclients",
        "banclienttimeouts",
        "clearstats",
    }.issubset(sync_out_params)

    tablet_params = {param["name"] for param in cards.get_operator("tabletCHOP")["key_params"]}
    assert {
        "xcoord",
        "ycoord",
        "pressure",
        "xtilt",
        "ytilt",
        "tanpressure",
        "zcoord",
        "rotation",
        "button1",
        "button2",
        "active",
        "play",
        "rate",
    }.issubset(tablet_params)

    timecode_params = {param["name"] for param in cards.get_operator("timecodeCHOP")["key_params"]}
    assert {
        "smpte",
        "mode",
        "timecodestr",
        "rate",
        "dropframe",
        "index",
        "indexunit",
        "negativechan",
        "hourchan",
        "minutechan",
        "secondchan",
        "framechan",
        "totalframes",
        "totalseconds",
    }.issubset(timecode_params)

    timeline_params = {param["name"] for param in cards.get_operator("timelineCHOP")["key_params"]}
    assert {
        "op",
        "usetimecode",
        "timecodeop",
        "frame",
        "rate",
        "start",
        "end",
        "rangestart",
        "rangeend",
        "signature1",
        "signature2",
        "bpm",
        "play",
    }.issubset(timeline_params)

    timer_params = {param["name"] for param in cards.get_operator("timerCHOP")["key_params"]}
    assert {"length", "play", "initialize", "callbacks", "cycle"}.issubset(timer_params)

    timeslice_params = {param["name"] for param in cards.get_operator("timesliceCHOP")["key_params"]}
    assert {"method", "trim", "quatrot", "timeslice", "srselect"}.issubset(timeslice_params)

    top_to_chop_params = {param["name"] for param in cards.get_operator("toptoCHOP")["key_params"]}
    assert {
        "top",
        "downloadtype",
        "r",
        "g",
        "b",
        "a",
        "outputcolorspace",
        "singleset",
        "excludenans",
        "activechannel",
    }.issubset(top_to_chop_params)

    touch_in_params = {param["name"] for param in cards.get_operator("touchinCHOP")["key_params"]}
    assert {
        "protocol",
        "address",
        "port",
        "active",
        "queuetarget",
        "queuetargetunit",
        "queuevariance",
        "maxqueue",
        "maxqueueunit",
        "adjusttime",
        "recover",
        "syncports",
    }.issubset(touch_in_params)

    touch_out_params = {param["name"] for param in cards.get_operator("touchoutCHOP")["key_params"]}
    assert {
        "protocol",
        "address",
        "port",
        "active",
        "maxsize",
        "maxsizeunit",
        "cookalways",
        "resendnames",
        "syncports",
    }.issubset(touch_out_params)

    trail_params = {param["name"] for param in cards.get_operator("trailCHOP")["key_params"]}
    assert {
        "active",
        "growlength",
        "wlength",
        "wlengthunit",
        "capture",
        "resample",
        "samples",
        "setrate",
        "rate",
        "reset",
        "resetpulse",
    }.issubset(trail_params)

    transform_params = {param["name"] for param in cards.get_operator("transformCHOP")["key_params"]}
    assert {
        "custinputorders",
        "inxord",
        "inrord",
        "input0preop",
        "input1preop",
        "inputoperation",
        "inputweight",
        "xord",
        "rord",
        "t",
        "r",
        "s",
        "p",
        "xformmatrixop",
        "lookat",
        "upvector",
        "preop",
        "operation",
        "weight",
    }.issubset(transform_params)

    transformxyz_params = {param["name"] for param in cards.get_operator("transformxyzCHOP")["key_params"]}
    assert {
        "input0type",
        "innormalize",
        "custinputorder",
        "inxord",
        "inrord",
        "input1preop",
        "xord",
        "rord",
        "t",
        "r",
        "s",
        "p",
        "preop",
        "multiplyorder",
        "normalize",
    }.issubset(transformxyz_params)

    trigger_params = {param["name"] for param in cards.get_operator("triggerCHOP")["key_params"]}
    assert {
        "threshold",
        "threshup",
        "threshdown",
        "triggeron",
        "multitrigger",
        "complete",
        "remainder",
        "trigger",
        "release",
        "reset",
        "delay",
        "attack",
        "ashape",
        "peak",
        "decay",
        "sustain",
        "minsustain",
        "channame",
        "specifyrate",
        "rate",
    }.issubset(trigger_params)

    warp_params = {param["name"] for param in cards.get_operator("warpCHOP")["key_params"]}
    assert {"method", "rate", "index", "timeslice", "srselect"}.issubset(warp_params)

    wave_params = {param["name"] for param in cards.get_operator("waveCHOP")["key_params"]}
    assert {
        "wavetype",
        "period",
        "periodunit",
        "phase",
        "bias",
        "amp",
        "offset",
        "decay",
        "channelname",
        "start",
        "startunit",
        "end",
        "endunit",
        "rate",
        "left",
        "right",
    }.issubset(wave_params)

    wrnch_ai_params = {param["name"] for param in cards.get_operator("wrnchaiCHOP")["key_params"]}
    assert {
        "modelfolder",
        "gpu",
        "body3d",
        "body2d",
        "body3dik",
        "facebounds",
        "face",
        "handsbounds",
        "hands",
        "maxplayers",
        "aspectcorrectuv",
    }.issubset(wrnch_ai_params)

    zed_params = {param["name"] for param in cards.get_operator("zedCHOP")["key_params"]}
    assert {
        "active",
        "zedtop",
        "cameratransform",
        "resetcameratransform",
        "planeorientation",
        "getplane",
        "getplanepulse",
        "planepointu",
        "planepointv",
        "planeposition",
        "planerotation",
        "planenormal",
        "planesize",
        "bodytracking",
        "maxbodies",
        "body3d",
        "jointmode",
        "body2d",
        "aspectcorrectuv",
        "boundingboxes",
    }.issubset(zed_params)

    text_pop_params = {param["name"] for param in cards.get_operator("textPOP")["key_params"]}
    assert {"connectivity", "mode", "alignx", "aligny"}.issubset(text_pop_params)
    assert {"outputtype", "align"}.isdisjoint(text_pop_params)

    math_combine_params = {param["name"] for param in cards.get_operator("mathcombinePOP")["key_params"]}
    assert {
        "comb",
        "comb0oper",
        "comb0scopea",
        "comb0scopeb",
        "comb0scopec",
        "comb0result",
    }.issubset(math_combine_params)
    assert {"scopea", "scopeb", "scopec", "resultscope"}.isdisjoint(math_combine_params)

    delete_pop_params = {param["name"] for param in cards.get_operator("deletePOP")["key_params"]}
    assert "invert" in delete_pop_params
    assert "delete" not in delete_pop_params

    cache_blend_params = {param["name"] for param in cards.get_operator("cacheblendPOP")["key_params"]}
    assert {"cache0index", "cache0indexunit", "cache0weight"}.issubset(cache_blend_params)

    switch_pop_params = {param["name"] for param in cards.get_operator("switchPOP")["key_params"]}
    assert {"lengthmismatchnotif", "lengthmismatchaction", "input0pop"}.issubset(switch_pop_params)

    cache_pop_params = {param["name"] for param in cards.get_operator("cachePOP")["key_params"]}
    assert {"alwayscook", "activepulse", "stepunit", "outputindexunit"}.issubset(cache_pop_params)

    assert "indexchanunit" in cache_blend_params

    group_pop_params = {param["name"] for param in cards.get_operator("groupPOP")["key_params"]}
    assert {"attr", "pattern", "group", "bound", "cnvttype", "newname"}.issubset(group_pop_params)

    merge_pop_params = {param["name"] for param in cards.get_operator("mergePOP")["key_params"]}
    assert {"group", "input0pop", "input0groupentity"}.issubset(merge_pop_params)

    sort_pop_params = {param["name"] for param in cards.get_operator("sortPOP")["key_params"]}
    assert {
        "pointoffset",
        "primattr",
        "primuint",
        "primseed",
        "primprox",
        "primdir",
        "primobj",
        "primrev",
        "primshift",
        "primoffset",
    }.issubset(sort_pop_params)

    line_break_params = {param["name"] for param in cards.get_operator("linebreakPOP")["key_params"]}
    assert {
        "useinputlinebreaks",
        "outputlinebreakattr",
        "outputlines",
        "cpureadback",
    }.issubset(line_break_params)

    line_divide_params = {param["name"] for param in cards.get_operator("linedividePOP")["key_params"]}
    assert {
        "interpmethodpersegment",
        "segmethodattr",
        "useweight",
        "usetanin",
        "usetanout",
        "usetaninconst",
        "clamped",
        "tension",
        "resamplemethod",
        "resamplemaxverts",
        "maxtries",
        "rmvunusedpts",
    }.issubset(line_divide_params)

    line_metrics_params = {param["name"] for param in cards.get_operator("linemetricsPOP")["key_params"]}
    assert {
        "angleperdist",
        "maxneighbors",
        "diststart",
        "distend",
        "diststartnorm",
        "distendnorm",
        "primlen",
        "pointindex",
        "numverts",
        "linestripindex",
        "lsindexnorm",
    }.issubset(line_metrics_params)

    trail_params = {param["name"] for param in cards.get_operator("trailPOP")["key_params"]}
    assert {"attrname", "uintmax", "maxls", "surftype", "closed", "xord", "rord", "p"}.issubset(trail_params)

    proximity_params = {param["name"] for param in cards.get_operator("proximityPOP")["key_params"]}
    assert {"endptattrs", "origin", "remunusedpoints", "cpureadback"}.issubset(proximity_params)

    ray_params = {param["name"] for param in cards.get_operator("rayPOP")["key_params"]}
    assert {
        "anyhit",
        "farhit",
        "inside",
        "hitprimindex",
        "barycoords",
        "hitpointattrscope",
        "hitprimattrscope",
        "hitvertattrscope",
    }.issubset(ray_params)

    transform_params = {param["name"] for param in cards.get_operator("transformPOP")["key_params"]}
    assert {
        "inputattrscope",
        "group",
        "xord",
        "rord",
        "p",
        "scale",
        "invert",
        "vlength",
        "lookat",
        "xformmatrixop",
        "alignxformorder",
        "alignopord",
        "map0parm",
    }.issubset(transform_params)

    copy_params = {param["name"] for param in cards.get_operator("copyPOP")["key_params"]}
    assert {
        "p",
        "scale",
        "copyidname",
        "lookat",
        "upvector",
        "forwarddir",
        "vlength",
        "dimension",
        "dotemplatematrix",
        "transformattr",
        "dotemplatetranslate",
        "translateattr",
    }.issubset(copy_params)

    facet_params = {param["name"] for param in cards.get_operator("facetPOP")["key_params"]}
    assert {"gridres", "specifybbox", "bbox", "cpureadback"}.issubset(facet_params)

    normal_params = {param["name"] for param in cards.get_operator("normalPOP")["key_params"]}
    assert {
        "maxprimsperpoint",
        "angle",
        "outputattrscopen",
        "overrideautoattrn",
        "attrtypen",
        "attrnumcompsn",
        "inputposattrt",
        "inputtexattrib",
        "comptangtech",
        "outputattrscopet",
    }.issubset(normal_params)

    primitive_params = {param["name"] for param in cards.get_operator("primitivePOP")["key_params"]}
    assert {
        "premultcolor",
        "attr0name",
        "attr0customname",
        "attr0type",
        "attr0numcomps",
        "attr0value",
        "pt0pos",
        "set",
        "n",
        "prim",
        "prim0type",
        "prim0pattern",
        "unusedpointsop",
        "cpureadback",
        "parmcolorspace",
        "parmreferencewhite",
    }.issubset(primitive_params)
    assert "rmvunusedpts" not in primitive_params

    extrude_params = {param["name"] for param in cards.get_operator("extrudePOP")["key_params"]}
    assert {
        "maxprimsperpoint",
        "cpureadback",
        "map0op",
        "map0element",
        "map0parm",
        "map0combineop",
    }.issubset(extrude_params)

    polygonize_params = {param["name"] for param in cards.get_operator("polygonizePOP")["key_params"]}
    assert {
        "inside",
        "uniquepoints",
        "rerangep",
        "tolow",
        "tohigh",
        "nmlstepmul",
        "texture",
        "allocfract",
        "cpureadback",
    }.issubset(polygonize_params)

    texture_map_params = {param["name"] for param in cards.get_operator("texturemapPOP")["key_params"]}
    assert {
        "transforminput",
        "inputtexattr",
        "fov",
        "centermode",
        "center",
        "cameraaspect",
        "s",
        "offset",
        "angle",
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
        "xord",
        "rord",
        "t",
        "r",
        "scaletwo",
        "p",
    }.issubset(texture_map_params)

    line_thick_params = {param["name"] for param in cards.get_operator("linethickPOP")["key_params"]}
    assert {
        "inversedistanceexponent",
        "widthaffectedbyfov",
        "widthbias",
        "widthsteepness",
        "widthlinearize",
        "colorbias",
        "colorsteepness",
        "colorlinearize",
        "numptsincircle",
        "id",
        "miterthreshold",
        "linestartcaptype",
        "lineendcaptype",
        "linenearcolor",
        "specifylinefarcolor",
        "vectorstartcaptype",
        "vectorendcaptype",
        "vectortaperstrength",
        "roundwidth",
        "arrowtaillength",
        "endcapwidthmultiplier",
        "startcappullback",
        "parmcolorspace",
        "parmreferencewhite",
    }.issubset(line_thick_params)

    accumulate_params = {param["name"] for param in cards.get_operator("accumulatePOP")["key_params"]}
    assert "attrdefaultval" in accumulate_params

    analyze_params = {param["name"] for param in cards.get_operator("analyzePOP")["key_params"]}
    assert {
        "numgroupelements",
        "appendattrname",
        "centroid",
        "size",
        "minindex",
        "maxindex",
        "sum",
        "rmspower",
        "numpointsvertsprims",
        "numprimsbatch",
        "pattrvals",
    }.issubset(analyze_params)

    blend_pop_params = {param["name"] for param in cards.get_operator("blendPOP")["key_params"]}
    assert {
        "lengthmismatchaction",
        "input0pop",
        "map",
        "map0op",
        "map0element",
        "map0parm",
        "map0combineop",
    }.issubset(blend_pop_params)

    feedback_params = {param["name"] for param in cards.get_operator("feedbackPOP")["key_params"]}
    assert {"preroll", "prerollunit", "donepulse"}.issubset(feedback_params)

    force_radial_params = {param["name"] for param in cards.get_operator("forceradialPOP")["key_params"]}
    assert {
        "axial",
        "axialr",
        "spiral",
        "spiralr",
        "planar",
        "planarexponent",
        "planarstrength",
        "falloffsteepness",
        "falloffbias",
        "falloffexponent",
        "falloffradius",
        "falloffplateau",
        "fallofflimitrange",
        "globforcemult",
        "windspeedmult",
        "map",
        "map0op",
        "map0element",
        "map0parm",
        "map0combineop",
    }.issubset(force_radial_params)

    limit_params = {param["name"] for param in cards.get_operator("limitPOP")["key_params"]}
    assert {
        "outputattrscope",
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
        "quantize",
        "quantstep",
        "quantoffset",
    }.issubset(limit_params)

    pattern_params = {param["name"] for param in cards.get_operator("patternPOP")["key_params"]}
    assert {
        "steppercycle",
        "bias",
        "phase",
        "exp",
        "fromlow",
        "fromhigh",
        "tolow",
        "tohigh",
        "reverse",
        "closed",
        "outputlinebreakattr",
        "texture",
        "combineattrscope",
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
        "attrclass",
        "group",
    }.issubset(pattern_params)

    quantize_params = {param["name"] for param in cards.get_operator("quantizePOP")["key_params"]}
    assert {
        "group",
        "overrideautoattr",
        "attrnumcomps",
        "attrdefaultval",
    }.issubset(quantize_params)

    random_params = {param["name"] for param in cards.get_operator("randomPOP")["key_params"]}
    assert {
        "exp",
        "valuebproba",
        "minval",
        "maxval",
        "conedir",
        "coneangle",
        "combineop",
        "combineattrscope",
        "outputattrscope",
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
        "attrclass",
        "group",
        "map",
        "map0op",
        "map0element",
        "map0parm",
        "map0combineop",
    }.issubset(random_params)

    trig_params = {param["name"] for param in cards.get_operator("trigPOP")["key_params"]}
    assert {"attrtype", "attrdefaultval"}.issubset(trig_params)

    alembic_in_params = {param["name"] for param in cards.get_operator("alembicinPOP")["key_params"]}
    assert {
        "interp",
        "loadfile",
        "sampleratemode",
        "samplerate",
        "indexunit",
        "tstart",
        "tend",
        "textendleft",
        "textendright",
    }.issubset(alembic_in_params)

    alembic_out_params = {param["name"] for param in cards.get_operator("alembicoutPOP")["key_params"]}
    assert {
        "input0ptattrname",
        "input0vertattrname",
        "input0primattrname",
        "uniquesuff",
        "limitlength",
        "lengthunit",
        "maxactive",
        "unchangedtopology",
        "abcfps",
    }.issubset(alembic_out_params)

    dmx_fixture_params = {param["name"] for param in cards.get_operator("dmxfixturePOP")["key_params"]}
    assert {
        "changap",
        "quantizeuni",
        "dmxchan",
        "dmxchan0name",
        "dmxchan0valuetype",
        "dmxchan0attr",
        "dmxchan0valueres",
        "dmxchan0normalized",
        "dmxchan0merge",
        "dmxchan0interleavebytes",
        "parmcolorspace",
    }.issubset(dmx_fixture_params)
    assert "quantizeuniverse" not in dmx_fixture_params

    dmx_out_params = {param["name"] for param in cards.get_operator("dmxoutPOP")["key_params"]}
    assert {
        "active",
        "interface",
        "rate",
        "fixture",
        "fixture0active",
        "fixture0pop",
        "serialport",
        "device",
        "netaddress",
        "routingtable",
    }.issubset(dmx_out_params)
    assert {"protocol", "fixturepops"}.isdisjoint(dmx_out_params)

    file_out_params = {param["name"] for param in cards.get_operator("fileoutPOP")["key_params"]}
    assert {
        "limitlength",
        "length",
        "lengthunit",
        "maxactive",
        "texcoordattrib",
        "outputcolorspace",
        "attr",
        "attr0name",
        "attr0fields",
    }.issubset(file_out_params)

    import_select_params = {param["name"] for param in cards.get_operator("importselectPOP")["key_params"]}
    assert {
        "sampleratemode",
        "samplerate",
        "initialize",
        "start",
        "cuepulse",
        "indexunit",
        "speed",
        "trim",
        "tstart",
        "tend",
        "textendleft",
        "textendright",
    }.issubset(import_select_params)

    point_file_in_params = {param["name"] for param in cards.get_operator("pointfileinPOP")["key_params"]}
    assert {
        "texturefields",
        "attr0fields",
        "attr0name",
        "attr0isarray",
        "attr0arraysize",
        "attr0qualifier",
        "inputcolorspace",
        "inputreferencewhite",
        "thinoutrange",
        "thinstep",
        "thinrandomseed",
        "rerange",
        "rerange0scope",
        "rerange0fromlow",
        "rerange0tohigh",
    }.issubset(point_file_in_params)

    zed_params = {param["name"] for param in cards.get_operator("zedPOP")["key_params"]}
    assert {
        "donepulse",
        "normals",
        "color",
        "filter",
        "perspective",
        "rerangefromlow",
        "rerangetolow",
        "mirrorimage",
        "overridecamera",
        "viewanglemethod",
        "fov",
        "focallengths",
        "center",
        "deletenear",
        "depthfar",
    }.issubset(zed_params)

    dimension_params = {param["name"] for param in cards.get_operator("dimensionPOP")["key_params"]}
    assert {"mode", "dimorder", "dim", "dim0number"}.issubset(dimension_params)

    field_params = {param["name"] for param in cards.get_operator("fieldPOP")["key_params"]}
    assert {
        "transitiontype",
        "absvalue",
        "invert",
        "torange",
        "deletezeros",
        "linestripbehavior",
        "xord",
        "rord",
        "t",
        "r",
        "s",
        "p",
        "weight",
        "outputattr",
        "signeddistance",
        "sdoutputattr",
        "perfieldweights",
        "perfieldweightsoutputattr",
        "perfielddistances",
        "perfielddistancesoutputattr",
        "combineop",
        "combineentity",
        "combineattr",
        "combineoutputattr",
        "combineoverrideautoattr",
        "combineattrtype",
        "combineattrnumcomps",
        "combineattrdefaultval",
    }.issubset(field_params)

    histogram_params = {param["name"] for param in cards.get_operator("histogramPOP")["key_params"]}
    assert {"inputrangemin", "inputrangemax"}.issubset(histogram_params)

    neighbor_params = {param["name"] for param in cards.get_operator("neighborPOP")["key_params"]}
    assert {
        "nebrattrname",
        "numnbrsattrname",
        "distattrname",
        "maxnebrsavg",
        "incquerypt",
        "addprefix",
        "castintstofloats",
        "nebrptattrs",
    }.issubset(neighbor_params)

    phaser_params = {param["name"] for param in cards.get_operator("phaserPOP")["key_params"]}
    assert {
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
        "attrclass",
        "fromlow",
        "fromhigh",
        "tolow",
        "tohigh",
    }.issubset(phaser_params)

    projection_params = {param["name"] for param in cards.get_operator("projectionPOP")["key_params"]}
    assert {
        "aspectcorrectuv",
        "aspect",
        "fov",
        "depthnear",
        "depthfar",
        "outputattrscope",
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
    }.issubset(projection_params)

    skin_deform_params = {param["name"] for param in cards.get_operator("skindeformPOP")["key_params"]}
    assert {
        "inputattrscope",
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
    }.issubset(skin_deform_params)
    assert {"skindeformgeo", "skindeformattrib"}.isdisjoint(skin_deform_params)

    sprinkle_params = {param["name"] for param in cards.get_operator("sprinklePOP")["key_params"]}
    assert "vertattribscope" in sprinkle_params

    twist_params = {param["name"] for param in cards.get_operator("twistPOP")["key_params"]}
    assert {
        "overrideautoattr",
        "attrtype",
        "attrnumcomps",
        "attrdefaultval",
    }.issubset(twist_params)

    convert_params = {param["name"] for param in cards.get_operator("convertPOP")["key_params"]}
    assert {"convert", "delinputattrs"}.issubset(convert_params)

    cplusplus_params = {param["name"] for param in cards.get_operator("cplusplusPOP")["key_params"]}
    assert {"plugin", "reinit", "reinitpulse", "unloadplugin"}.issubset(cplusplus_params)

    in_params = {param["name"] for param in cards.get_operator("inPOP")["key_params"]}
    assert {"label", "connectorder"}.issubset(in_params)

    out_params = {param["name"] for param in cards.get_operator("outPOP")["key_params"]}
    assert {"selectpop", "label", "connectorder"}.issubset(out_params)

    noise_top_params = {param["name"] for param in cards.get_operator("noiseTOP")["key_params"]}
    assert {
        "type",
        "seed",
        "period",
        "harmon",
        "rough",
        "aspectcorrect",
        "t",
        "t4d",
        "rgb",
        "alpha",
        "gradient",
        "mode",
    }.issubset(noise_top_params)

    feedback_top_params = {param["name"] for param in cards.get_operator("feedbackTOP")["key_params"]}
    assert {"top", "reset", "resetpulse"}.issubset(feedback_top_params)

    level_top_params = {param["name"] for param in cards.get_operator("levelTOP")["key_params"]}
    assert {
        "clampinput",
        "blacklevel",
        "brightness1",
        "gamma1",
        "contrast",
        "inlow",
        "outhigh",
        "stepping",
        "opacity",
        "premultrgbbyalpha",
    }.issubset(level_top_params)

    constant_top_params = {param["name"] for param in cards.get_operator("constantTOP")["key_params"]}
    assert {
        "color",
        "alpha",
        "multrgbbyalpha",
        "rgbaunit",
        "compoverinput",
        "operand",
        "swaporder",
        "type",
        "slices",
    }.issubset(constant_top_params)

    render_top_params = {param["name"] for param in cards.get_operator("renderTOP")["key_params"]}
    assert {
        "camera",
        "geometry",
        "lights",
        "rendermode",
        "drawdepthonly",
        "numcolorbufs",
        "depthformat",
        "overridemat",
        "vec0name",
        "sampler0name",
        "image0name",
        "parmcolorspace",
    }.issubset(render_top_params)

    render_simple_params = {param["name"] for param in cards.get_operator("rendersimpleTOP")["key_params"]}
    assert {
        "ortho",
        "fov",
        "orthowidth",
        "normalizegeo",
        "bgcolor",
        "pop",
        "geotranslate",
        "lighttranslate",
        "materialsource",
        "wireframe",
        "mat",
    }.issubset(render_simple_params)

    text_dat_params = {param["name"] for param in cards.get_operator("textDAT")["key_params"]}
    assert {
        "edit",
        "file",
        "syncfile",
        "loadonstart",
        "write",
        "language",
        "extension",
        "customext",
        "wordwrap",
    }.issubset(text_dat_params)

    audio_file_in_params = {param["name"] for param in cards.get_operator("audiofileinCHOP")["key_params"]}
    assert {
        "file",
        "reloadpulse",
        "play",
        "playmode",
        "speed",
        "cuepulse",
        "index",
        "timecodeop",
        "repeat",
        "trim",
        "opentimeout",
        "mono",
        "volume",
    }.issubset(audio_file_in_params)

    analyze_chop_params = {param["name"] for param in cards.get_operator("analyzeCHOP")["key_params"]}
    assert {"function", "allowstart", "allowend", "nopeakvalue", "valleys"}.issubset(analyze_chop_params)

    math_chop_params = {param["name"] for param in cards.get_operator("mathCHOP")["key_params"]}
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
        "torange",
    }.issubset(math_chop_params)

    null_top_params = {param["name"] for param in cards.get_operator("nullTOP")["key_params"]}
    assert {"outputresolution", "resolution", "npasses", "chanmask", "format"}.issubset(null_top_params)

    composite_top_params = {param["name"] for param in cards.get_operator("compositeTOP")["key_params"]}
    assert {
        "top",
        "previewgrid",
        "selectinput",
        "inputindex",
        "operand",
        "swaporder",
        "size",
        "prefit",
        "t",
        "s",
        "p",
        "legacyxform",
    }.issubset(composite_top_params)

    glsl_top_params = {param["name"] for param in cards.get_operator("glslTOP")["key_params"]}
    assert {
        "glslversion",
        "mode",
        "predat",
        "vertexdat",
        "pixeldat",
        "computedat",
        "compilebehavior",
        "errorbehavior",
        "dispatchsizex",
        "outputaccess",
        "autodispatchsize",
        "numcolorbufs",
        "buffer0pop",
        "buffer0attr",
    }.issubset(glsl_top_params)

    glsl_mat_params = {param["name"] for param in cards.get_operator("glslMAT")["key_params"]}
    assert {
        "glslversion",
        "vdat",
        "pdat",
        "gdat",
        "lightingspace",
        "attr0name",
        "sampler0name",
        "vec0name",
        "const0name",
        "dodeform",
        "pcaptpath",
        "blending",
        "depthtest",
        "wireframe",
    }.issubset(glsl_mat_params)

    glsl_pop_params = {param["name"] for param in cards.get_operator("glslPOP")["key_params"]}
    assert {
        "computedat",
        "attrclass",
        "numthreadsmode",
        "workgroupsizex",
        "dispatchsizex",
        "outputattrs",
        "outputaccess",
        "prevpassoutput",
        "attr0name",
        "vec0name",
        "sampler0name",
        "tempbuffer0name",
        "const0name",
        "asname",
        "delinputattrs",
    }.issubset(glsl_pop_params)

    camera_params = {param["name"] for param in cards.get_operator("cameraCOMP")["key_params"]}
    assert {
        "xord",
        "rord",
        "t",
        "r",
        "lookat",
        "pathsop",
        "projection",
        "orthowidth",
        "fov",
        "near",
        "far",
        "projmatrixop",
        "customproj",
        "fog",
        "camlightmask",
        "render",
    }.issubset(camera_params)

    geometry_params = {param["name"] for param in cards.get_operator("geometryCOMP")["key_params"]}
    assert {
        "xord",
        "rord",
        "t",
        "r",
        "lookat",
        "instancing",
        "instancecountmode",
        "instanceop",
        "instancetop",
        "instancepop",
        "instancerottoorder",
        "instanceorder",
        "instancecolorop",
        "instance0customx",
        "material",
        "render",
        "lightmask",
    }.issubset(geometry_params)

    null_chop_params = {param["name"] for param in cards.get_operator("nullCHOP")["key_params"]}
    assert {"cooktype", "checkvalues", "checknames", "checkrange", "timeslice"}.issubset(null_chop_params)

    constant_chop_params = {param["name"] for param in cards.get_operator("constantCHOP")["key_params"]}
    assert {
        "const",
        "const0name",
        "const0value",
        "snap",
        "first",
        "current",
        "single",
        "start",
        "end",
        "rate",
        "left",
        "right",
        "defval",
    }.issubset(constant_chop_params)

    null_pop_params = {param["name"] for param in cards.get_operator("nullPOP")["key_params"]}
    assert {"bypass"}.issubset(null_pop_params)

    base_params = {param["name"] for param in cards.get_operator("baseCOMP")["key_params"]}
    assert {
        "reinitextensions",
        "initextonstart",
        "ext0object",
        "parentshortcut",
        "opshortcut",
        "iop0op",
        "opviewer",
        "enablecloning",
        "clone",
        "loadondemand",
        "externaltox",
        "reloadcustom",
        "relpath",
    }.issubset(base_params)

    button_params = {param["name"] for param in cards.get_operator("buttonCOMP")["key_params"]}
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
        "x",
        "y",
        "w",
        "h",
        "display",
        "enable",
        "opacity",
    }.issubset(button_params)

    circle_pop_params = {param["name"] for param in cards.get_operator("circlePOP")["key_params"]}
    assert {
        "connectivity",
        "orient",
        "modifybounds",
        "rad",
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
        "tangent",
        "texture",
    }.issubset(circle_pop_params)

    container_params = {param["name"] for param in cards.get_operator("containerCOMP")["key_params"]}
    assert {
        "x",
        "y",
        "w",
        "h",
        "display",
        "enable",
        "opacity",
        "bgcolor",
        "top",
        "topfill",
        "composite",
        "align",
        "spacing",
        "margin",
        "justifyh",
        "justifyv",
        "fit",
        "phscrollbar",
        "pvscrollbar",
    }.issubset(container_params)

    math_mix_params = {param["name"] for param in cards.get_operator("mathmixPOP")["key_params"]}
    assert {
        "lengthmismatchnotif",
        "lengthmismatchaction",
        "group",
        "angleunit",
        "input0pop",
        "attrclass",
        "vec0name",
        "premultcolor",
        "color0name",
        "comb0oper",
        "comb0scopea",
        "comb0scopeb",
        "comb0scopec",
        "comb0result",
        "delattrs",
        "delnewattrs",
        "parmcolorspace",
    }.issubset(math_mix_params)

    noise_pop_params = {param["name"] for param in cards.get_operator("noisePOP")["key_params"]}
    assert {
        "noiselookupattrib",
        "type",
        "noisesize",
        "seed",
        "period",
        "harmon",
        "attrclass",
        "group",
        "xord",
        "t",
        "t4d",
        "noise",
        "noiseoutputattscope",
        "gradient",
        "curl3d",
        "combineop",
        "outputattrscope",
        "overrideautoattr",
        "computenormals",
        "map0op",
    }.issubset(noise_pop_params)

    panel_chop_params = {param["name"] for param in cards.get_operator("panelCHOP")["key_params"]}
    assert {"component", "select", "rename", "queue", "queuesize", "timeslice", "scope"}.issubset(
        panel_chop_params
    )

    slider_params = {param["name"] for param in cards.get_operator("sliderCOMP")["key_params"]}
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
        "x",
        "y",
        "w",
        "h",
        "display",
        "enable",
        "opacity",
    }.issubset(slider_params)

    pbr_mat_params = {param["name"] for param in cards.get_operator("pbrMAT")["key_params"]}
    assert {
        "basecolor",
        "basecolormap",
        "roughness",
        "roughnessmap",
        "metallic",
        "metallicmap",
        "normalmap",
        "heightmap",
        "envmap",
        "outputshader",
    }.issubset(pbr_mat_params)

    phong_mat_params = {param["name"] for param in cards.get_operator("phongMAT")["key_params"]}
    assert {
        "ambdiff",
        "diff",
        "amb",
        "spec",
        "emit",
        "shininess",
        "colormap",
        "normalmap",
        "heightmap",
        "outputshader",
    }.issubset(phong_mat_params)

    constant_mat_params = {param["name"] for param in cards.get_operator("constantMAT")["key_params"]}
    assert {
        "applyprojmaps",
        "color",
        "alpha",
        "applypointcolor",
        "colormap",
        "colormapcoord",
        "dodeform",
        "blending",
        "depthtest",
    }.issubset(constant_mat_params)

    line_mat_params = {param["name"] for param in cards.get_operator("lineMAT")["key_params"]}
    assert {
        "linetype",
        "color",
        "linewidth",
        "nearwidth",
        "farwidth",
        "roundwidth",
        "arrowwidth",
        "startcappullback",
        "dodeform",
    }.issubset(line_mat_params)

    point_sprite_mat_params = {param["name"] for param in cards.get_operator("pointspriteMAT")["key_params"]}
    assert {
        "color",
        "colormap",
        "pointsize",
        "sizingmodel",
        "attenpscale",
        "attennear",
        "attenfar",
        "offsetleft",
        "offsetright",
    }.issubset(point_sprite_mat_params)

    wireframe_mat_params = {param["name"] for param in cards.get_operator("wireframeMAT")["key_params"]}
    assert {
        "color",
        "wireframemode",
        "topologywireframe",
        "linewidth",
        "dodeform",
        "blending",
        "depthtest",
        "polygonoffset",
    }.issubset(wireframe_mat_params)

    depth_mat_params = {param["name"] for param in cards.get_operator("depthMAT")["key_params"]}
    assert {
        "dodeform",
        "depthtest",
        "depthfunc",
        "depthwriting",
        "cullface",
        "polygonoffset",
    }.issubset(depth_mat_params)

    in_mat_params = {param["name"] for param in cards.get_operator("inMAT")["key_params"]}
    assert {
        "label",
        "dodeform",
        "deformdata",
        "targetsop",
        "skelrootpath",
        "blending",
        "depthtest",
    }.issubset(in_mat_params)

    null_mat_params = {param["name"] for param in cards.get_operator("nullMAT")["key_params"]}
    assert {"label", "dodeform", "blending", "depthtest", "cullface"}.issubset(null_mat_params)

    out_mat_params = {param["name"] for param in cards.get_operator("outMAT")["key_params"]}
    assert {"label", "dodeform", "blending", "depthtest", "cullface"}.issubset(out_mat_params)

    select_mat_params = {param["name"] for param in cards.get_operator("selectMAT")["key_params"]}
    assert {"selectmat", "dodeform", "blending", "depthtest", "cullface"}.issubset(select_mat_params)

    switch_mat_params = {param["name"] for param in cards.get_operator("switchMAT")["key_params"]}
    assert {"index", "extend", "dodeform", "blending", "depthtest"}.issubset(switch_mat_params)


def test_deprecated_docsbrain_operator_gaps_have_planner_notes():
    coverage = audit_brain_atlas(Path("."))["docsbrain_operator_coverage"]
    deprecated = {item["op_type"]: item for item in coverage["deprecated_missing_operator_cards"]}
    expected = {
        "bandeqCHOP": ["audiobandeqCHOP"],
        "etherdreamCHOP": ["laserdeviceCHOP"],
        "heliosdacCHOP": ["laserdeviceCHOP"],
        "parametriceqCHOP": ["audioparaeqCHOP"],
        "realsenseCHOP": ["realsenseTOP"],
        "scanCHOP": ["laserCHOP"],
        "fieldCOMP": ["textCOMP"],
        "webDAT": ["webclientDAT"],
        "glslcreatePOP": ["glsladvancedPOP", "topologyPOP"],
        "fontSOP": ["textSOP"],
        "svgTOP": ["webrenderTOP"],
    }

    assert set(expected).issubset(deprecated)
    assert "datexecuteDAT" not in deprecated
    assert "opviewerTOP" not in deprecated
    assert "overrideCHOP" not in deprecated
    assert "windowCOMP" not in deprecated

    for op_type, replacement_op_types in expected.items():
        item = deprecated[op_type]

        assert item["gap_status"].startswith("deprecated"), op_type
        assert item["replacement_op_types"] == replacement_op_types
        assert item["planner_guidance"], op_type
        assert item["official_doc_note"], op_type
        assert item["source_url"] == item["docs_url"]
