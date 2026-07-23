"""Coverage audit for the structured operator atlas used by brain profiles."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from td_mcp.brain.planner import _PROFILE_SPECS
from td_mcp.knowledge.card_index import CardIndex

_DEPRECATED_OPERATOR_GAP_NOTES: dict[str, dict[str, Any]] = {
    "bandeqCHOP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["audiobandeqCHOP"],
        "official_doc_note": "Official docs mark Band EQ CHOP as replaced by Audio Band EQ CHOP for better-quality filters.",
        "planner_guidance": "Do not promote Band EQ CHOP for new audio work; use Audio Band EQ CHOP instead.",
    },
    "etherdreamCHOP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["laserdeviceCHOP"],
        "official_doc_note": "Official docs mark EtherDream CHOP deprecated and direct users to Laser Device CHOP.",
        "planner_guidance": "Use Laser Device CHOP for EtherDream laser DAC output and keep EtherDream DAT only for device discovery.",
    },
    "heliosdacCHOP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["laserdeviceCHOP"],
        "official_doc_note": "Official docs mark Helios DAC CHOP deprecated and direct users to Laser Device CHOP.",
        "planner_guidance": "Use Laser Device CHOP for Helios DAC output instead of planning a Helios DAC CHOP.",
    },
    "parametriceqCHOP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["audioparaeqCHOP"],
        "official_doc_note": "Official docs mark Parametric EQ CHOP as replaced by Audio Para EQ CHOP.",
        "planner_guidance": "Use Audio Para EQ CHOP for parametric EQ filtering and leave Parametric EQ CHOP unpromoted.",
    },
    "realsenseCHOP": {
        "gap_status": "deprecated_feature_unavailable",
        "replacement_op_types": ["realsenseTOP"],
        "official_doc_note": "Official docs mark RealSense CHOP deprecated because Cubemos skeleton tracking is no longer licensable.",
        "planner_guidance": "Avoid planning RealSense CHOP skeleton tracking; use RealSense TOP for camera streams and choose a supported tracking path separately.",
    },
    "scanCHOP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["laserCHOP"],
        "official_doc_note": "Official docs mark Scan CHOP deprecated and direct users to Laser CHOP.",
        "planner_guidance": "Use Laser CHOP for oscilloscope or laser-friendly control waves.",
    },
    "fieldCOMP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["textCOMP"],
        "official_doc_note": "Official docs mark Field COMP deprecated as of build 2022.24200 and direct users to Text COMP.",
        "planner_guidance": "Use Text COMP for editable or formatted text panels; Field COMP should stay unpromoted.",
    },
    "webDAT": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["webclientDAT"],
        "official_doc_note": "Official docs mark Web DAT deprecated as of build 2019.15230 and direct users to Web Client DAT.",
        "planner_guidance": "Use Web Client DAT for HTTP requests; reserve Web Server DAT for serving endpoints.",
    },
    "glslcreatePOP": {
        "gap_status": "deprecated_pending_removal",
        "replacement_op_types": ["glsladvancedPOP", "topologyPOP"],
        "official_doc_note": "Official docs say GLSL Create POP is deprecated, will be removed, and should be replaced by GLSL Advanced POP with or without Topology POP.",
        "planner_guidance": "Use GLSL Advanced POP for shader-driven POP creation and add Topology POP when primitive topology must be generated.",
    },
    "fontSOP": {
        "gap_status": "deprecated_replaced",
        "replacement_op_types": ["textSOP"],
        "official_doc_note": "Official docs mark Font SOP deprecated as of build 2019.14650 and direct users to Text SOP.",
        "planner_guidance": "Use Text SOP for 3D text geometry instead of the old Adobe Type 1 Font SOP path.",
    },
    "svgTOP": {
        "gap_status": "deprecated_nonfunctional",
        "replacement_op_types": ["webrenderTOP"],
        "official_doc_note": "Official docs say SVG TOP is deprecated, no longer works, and suggest palette:webSvg plus Web Render TOP as alternatives.",
        "planner_guidance": "Use palette:webSvg or Web Render TOP for SVG rendering workflows; keep SVG TOP unpromoted.",
    },
}

_STRICT_OPERATOR_QUALITY_TYPES = (
    "abletonlinkCHOP",
    "accumulatePOP",
    "actorCOMP",
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
    "transformSOP",
    "trimSOP",
    "tristripSOP",
    "tubeSOP",
    "twistSOP",
    "vertexSOP",
    "wireframeSOP",
    "zedSOP",
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
    "addTOP",
    "alembicinPOP",
    "alembicoutPOP",
    "ambientlightCOMP",
    "analyzeCHOP",
    "analyzePOP",
    "analyzeTOP",
    "angleCHOP",
    "animationCOMP",
    "annotateCOMP",
    "antialiasTOP",
    "attributecombinePOP",
    "attributeconvertPOP",
    "attributePOP",
    "audiobandeqCHOP",
    "audiobinauralCHOP",
    "audiodeviceinCHOP",
    "audiodeviceoutCHOP",
    "audiodynamicsCHOP",
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
    "blobtrackTOP",
    "bloomTOP",
    "blurTOP",
    "bodytrackCHOP",
    "boneCOMP",
    "boxPOP",
    "bulletsolverCHOP",
    "bulletsolverCOMP",
    "buildalistCOMP",
    "buttonCOMP",
    "cachePOP",
    "cacheblendPOP",
    "cacheTOP",
    "cacheselectPOP",
    "cacheselectTOP",
    "cameraCOMP",
    "camerablendCOMP",
    "channelmixTOP",
    "choptoPOP",
    "choptoTOP",
    "chromakeyTOP",
    "circlePOP",
    "circleTOP",
    "clipCHOP",
    "clipblenderCHOP",
    "clockCHOP",
    "compositeCHOP",
    "compositeTOP",
    "convolveTOP",
    "connectivityPOP",
    "containerCOMP",
    "constantCHOP",
    "constantMAT",
    "constantTOP",
    "constraintCOMP",
    "convertPOP",
    "cornerpinTOP",
    "copyCHOP",
    "copyPOP",
    "countCHOP",
    "cplusplusCHOP",
    "cplusplusPOP",
    "cplusplusTOP",
    "cropTOP",
    "crossCHOP",
    "crossTOP",
    "cubemapTOP",
    "cudaTOP",
    "cycleCHOP",
    "curvePOP",
    "dattoCHOP",
    "dattoPOP",
    "delayCHOP",
    "deleteCHOP",
    "deletePOP",
    "depthMAT",
    "depthTOP",
    "differenceTOP",
    "dimensionPOP",
    "directdisplayoutTOP",
    "directxinTOP",
    "directxoutTOP",
    "displaceTOP",
    "dmxinCHOP",
    "dmxfixturePOP",
    "dmxoutCHOP",
    "dmxoutPOP",
    "engineCOMP",
    "envelopeCHOP",
    "environmentlightCOMP",
    "edgeTOP",
    "embossTOP",
    "eventCHOP",
    "expressionCHOP",
    "extrudePOP",
    "extendCHOP",
    "facetPOP",
    "facetrackCHOP",
    "fanCHOP",
    "fbxCOMP",
    "feedbackTOP",
    "feedbackPOP",
    "feedbackCHOP",
    "fieldPOP",
    "fileinCHOP",
    "fileinPOP",
    "fileoutCHOP",
    "fileoutPOP",
    "filterCHOP",
    "fitTOP",
    "flipTOP",
    "forceCOMP",
    "forceradialPOP",
    "freedinCHOP",
    "freedoutCHOP",
    "functionCHOP",
    "functionTOP",
    "geotextCOMP",
    "geometryCOMP",
    "gestureCHOP",
    "gltfinCOMP",
    "gltfoutCOMP",
    "glslMAT",
    "glslPOP",
    "glslTOP",
    "gridPOP",
    "groupPOP",
    "handleCHOP",
    "handleCOMP",
    "histogramPOP",
    "hogCHOP",
    "hokuyoCHOP",
    "holdCHOP",
    "hsvadjustTOP",
    "hsvtorgbTOP",
    "importselectCHOP",
    "importselectPOP",
    "importselectTOP",
    "impulseforceCOMP",
    "inCHOP",
    "inTOP",
    "infoCHOP",
    "inMAT",
    "inPOP",
    "insideTOP",
    "interpolateCHOP",
    "inversecurveCHOP",
    "inversekinCHOP",
    "joinCHOP",
    "joystickCHOP",
    "keyboardinCHOP",
    "keyframeCHOP",
    "kinectCHOP",
    "kinectazureCHOP",
    "kinectTOP",
    "kinectazureTOP",
    "kinectazureselectTOP",
    "lagCHOP",
    "laserCHOP",
    "laserdeviceCHOP",
    "layerTOP",
    "layermixTOP",
    "leapmotionCHOP",
    "layoutTOP",
    "leapmotionTOP",
    "lensdistortTOP",
    "leuzerod4CHOP",
    "lfoCHOP",
    "limitTOP",
    "limitCHOP",
    "limitPOP",
    "logicCHOP",
    "lookupCHOP",
    "lookupTOP",
    "lightCOMP",
    "lineMAT",
    "linethickPOP",
    "linebreakPOP",
    "linedividePOP",
    "levelTOP",
    "linemetricsPOP",
    "linePOP",
    "lineresamplePOP",
    "linesmoothPOP",
    "listCOMP",
    "ltcinCHOP",
    "ltcoutCHOP",
    "lookupattributePOP",
    "lookupchannelPOP",
    "lookuptexturePOP",
    "lumablurTOP",
    "lumalevelTOP",
    "mathCHOP",
    "mathcombinePOP",
    "mathmixPOP",
    "mathPOP",
    "mathTOP",
    "matteTOP",
    "mergeCHOP",
    "mergePOP",
    "midiinCHOP",
    "midiinmapCHOP",
    "midioutCHOP",
    "mirrorTOP",
    "monochromeTOP",
    "mosysCHOP",
    "mosysTOP",
    "mouseinCHOP",
    "mouseoutCHOP",
    "moviefileinTOP",
    "moviefileoutTOP",
    "mpcdiTOP",
    "multiplyTOP",
    "ncamCHOP",
    "ncamTOP",
    "ndiinTOP",
    "ndioutTOP",
    "normalPOP",
    "normalmapTOP",
    "neighborPOP",
    "noiseCHOP",
    "noisePOP",
    "noiseTOP",
    "notchTOP",
    "nullCHOP",
    "nullCOMP",
    "nullMAT",
    "nullPOP",
    "nullTOP",
    "nvidiabackgroundTOP",
    "nvidiadenoiseTOP",
    "nvidiaflexTOP",
    "nvidiaflexsolverCOMP",
    "nvidiaflowTOP",
    "nvidiaflowemitterCOMP",
    "nvidiartxvideoTOP",
    "nvidiaupscalerTOP",
    "normalizePOP",
    "oakdeviceCHOP",
    "oakselectCHOP",
    "oakselectPOP",
    "oakselectTOP",
    "objectCHOP",
    "oculusaudioCHOP",
    "oculusriftCHOP",
    "oculusriftTOP",
    "opencolorioTOP",
    "openvrCHOP",
    "openvrTOP",
    "opticalflowTOP",
    "optitrackinCHOP",
    "oscinCHOP",
    "oscoutCHOP",
    "outCHOP",
    "outMAT",
    "outPOP",
    "outTOP",
    "outsideTOP",
    "overrideCHOP",
    "overTOP",
    "opviewerCOMP",
    "opviewerTOP",
    "orbbecTOP",
    "orbbecselectTOP",
    "ousterTOP",
    "ousterselectTOP",
    "pangolinCHOP",
    "packTOP",
    "pantiltCHOP",
    "panelCHOP",
    "parameterCHOP",
    "particlePOP",
    "parameterCOMP",
    "patternCHOP",
    "pbrMAT",
    "performCHOP",
    "phaserCHOP",
    "phaserPOP",
    "phongMAT",
    "photoshopinTOP",
    "pipeinCHOP",
    "pipeoutCHOP",
    "patternPOP",
    "planePOP",
    "pointPOP",
    "pointfileinPOP",
    "pointfileinTOP",
    "pointfileselectTOP",
    "pointspriteMAT",
    "pointtransformTOP",
    "polygonizePOP",
    "poptoCHOP",
    "poptoDAT",
    "poptoSOP",
    "poptoTOP",
    "posistagenetCHOP",
    "prefiltermapTOP",
    "primitivePOP",
    "projectionPOP",
    "projectionTOP",
    "pulseCHOP",
    "quantizePOP",
    "rampTOP",
    "randomPOP",
    "realsenseTOP",
    "rectanglePOP",
    "rectangleTOP",
    "recordCHOP",
    "renameCHOP",
    "remapTOP",
    "renderpassTOP",
    "renderpickCHOP",
    "renderselectTOP",
    "renderstreaminCHOP",
    "renderstreaminTOP",
    "renderstreamoutTOP",
    "reorderCHOP",
    "reorderTOP",
    "replicatorCOMP",
    "rerangePOP",
    "replaceCHOP",
    "renderTOP",
    "rendersimpleTOP",
    "resolutionTOP",
    "resampleCHOP",
    "proximityPOP",
    "rayPOP",
    "revolvePOP",
    "rgbkeyTOP",
    "rgbtohsvTOP",
    "scalabledisplayTOP",
    "screenTOP",
    "screengrabTOP",
    "scriptPOP",
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
    "textTOP",
    "texture3dTOP",
    "selectMAT",
    "selectPOP",
    "selectCOMP",
    "sharedmeminCOMP",
    "sharedmeminCHOP",
    "sharedmemoutCOMP",
    "sharedmemoutCHOP",
    "scriptCHOP",
    "scurveCHOP",
    "sequencerCHOP",
    "serialCHOP",
    "shuffleCHOP",
    "shiftCHOP",
    "soptoPOP",
    "soptoCHOP",
    "skinPOP",
    "skindeformPOP",
    "sliderCOMP",
    "slopeCHOP",
    "speedCHOP",
    "spliceCHOP",
    "spherePOP",
    "sortCHOP",
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
    "switchCHOP",
    "switchMAT",
    "switchPOP",
    "tableCOMP",
    "tabletCHOP",
    "texturemapPOP",
    "textCOMP",
    "textDAT",
    "textPOP",
    "timeCOMP",
    "timecodeCHOP",
    "timelineCHOP",
    "timerCHOP",
    "timesliceCHOP",
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
    "widgetCOMP",
    "windowCOMP",
    "wireframeMAT",
    "wrnchaiCHOP",
    "zedCHOP",
    "zedPOP",
)

_OPERATOR_QUALITY_MINIMUMS = {
    "key_params": 3,
    "key_concepts": 3,
    "common_gotchas": 3,
}

_OPERATOR_QUALITY_MINIMUM_OVERRIDES = {
    "convertPOP": {
        "key_params": 2,
    },
    "cudaTOP": {
        "key_params": 1,
    },
    "inPOP": {
        "key_params": 2,
    },
    "inSOP": {
        "key_params": 1,
    },
    "inversecurveSOP": {
        "key_params": 1,
    },
    "bonegroupSOP": {
        "key_params": 2,
    },
    "materialSOP": {
        "key_params": 1,
    },
    "nullPOP": {
        "key_params": 1,
    },
    "openvrSOP": {
        "key_params": 1,
    },
    "outSOP": {
        "key_params": 1,
    },
    "poptoSOP": {
        "key_params": 2,
    },
    "scriptSOP": {
        "key_params": 2,
    },
    "selectSOP": {
        "key_params": 1,
    },
    "tristripSOP": {
        "key_params": 3,
    },
}


def audit_brain_atlas(root: str | Path) -> dict[str, Any]:
    """Return operator-card coverage for every vNext brain profile."""
    repo_root = Path(root)
    cards_dir = repo_root / "src" / "td_mcp" / "knowledge" / "cards"
    card_index = CardIndex(cards_dir)
    operator_quality = _operator_card_quality(card_index)

    profiles: dict[str, dict[str, Any]] = {}
    required: set[str] = set()
    missing_all: set[str] = set()
    family_counts: dict[str, int] = {}
    structured_operator_types: set[str] = set()
    operators_dir = cards_dir / "operators"
    for path in sorted(operators_dir.glob("*.json")) if operators_dir.is_dir() else []:
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        op_type = card.get("op_type")
        if op_type:
            structured_operator_types.add(str(op_type))
        family = str(card.get("family") or "UNKNOWN").upper()
        family_counts[family] = family_counts.get(family, 0) + 1

    for profile, spec in sorted(_PROFILE_SPECS.items()):
        operators = sorted({str(item["op_type"]) for item in spec.concepts if item.get("op_type")})
        missing = [op_type for op_type in operators if card_index.get_operator(op_type) is None]
        required.update(operators)
        missing_all.update(missing)
        profiles[profile] = {
            "operators": operators,
            "operator_count": len(operators),
            "missing_cards": missing,
            "coverage": 1.0 if not operators else round((len(operators) - len(missing)) / len(operators), 4),
        }

    return {
        "schema_version": 1,
        "ok": not missing_all and operator_quality["ok"],
        "card_count": card_index.count(),
        "operator_family_counts": dict(sorted(family_counts.items())),
        "docsbrain_operator_coverage": _docsbrain_operator_coverage(
            repo_root=repo_root,
            cards_dir=cards_dir,
            structured_operator_types=structured_operator_types,
            structured_family_counts=family_counts,
            required_profile_operators=required,
        ),
        "profile_count": len(profiles),
        "required_operator_count": len(required),
        "missing_operator_cards": sorted(missing_all),
        "operator_card_quality": operator_quality,
        "release_freshness": _release_freshness(repo_root, cards_dir),
        "profiles": profiles,
    }


def _operator_card_quality(card_index: CardIndex) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    for op_type in sorted(_STRICT_OPERATOR_QUALITY_TYPES):
        card = card_index.get_operator(op_type)
        if card is None:
            gaps.append(
                {
                    "op_type": op_type,
                    "field": "card",
                    "reason": "missing_operator_card",
                    "actual": 0,
                    "minimum": 1,
                }
            )
            continue

        docs_url = str(card.get("docs_url") or "")
        if not docs_url.startswith("https://docs.derivative.ca/"):
            gaps.append(
                {
                    "op_type": op_type,
                    "field": "docs_url",
                    "reason": "non_official_docs_url",
                    "actual": docs_url,
                    "minimum": "https://docs.derivative.ca/",
                }
            )

        if card.get("build_relevance") == "unverified-docsbrain":
            gaps.append(
                {
                    "op_type": op_type,
                    "field": "build_relevance",
                    "reason": "unverified_docsbrain_only",
                    "actual": card.get("build_relevance"),
                    "minimum": "reviewed",
                }
            )

        for field, minimum in _OPERATOR_QUALITY_MINIMUMS.items():
            minimum = _operator_quality_minimum(op_type, field)
            actual = _reviewed_item_count(card.get(field))
            if actual < minimum:
                gaps.append(
                    {
                        "op_type": op_type,
                        "field": field,
                        "reason": "too_few_reviewed_items",
                        "actual": actual,
                        "minimum": minimum,
                    }
                )

    return {
        "ok": not gaps,
        "strict_operator_count": len(_STRICT_OPERATOR_QUALITY_TYPES),
        "strict_operator_types": sorted(_STRICT_OPERATOR_QUALITY_TYPES),
        "minimums": dict(_OPERATOR_QUALITY_MINIMUMS),
        "minimum_overrides": {
            op_type: dict(overrides)
            for op_type, overrides in sorted(_OPERATOR_QUALITY_MINIMUM_OVERRIDES.items())
        },
        "gap_count": len(gaps),
        "gaps": gaps,
    }


def _operator_quality_minimum(op_type: str, field: str) -> int:
    return int(
        _OPERATOR_QUALITY_MINIMUM_OVERRIDES.get(op_type, {}).get(
            field,
            _OPERATOR_QUALITY_MINIMUMS[field],
        )
    )


def _reviewed_item_count(value: Any) -> int:
    if not isinstance(value, list):
        return 0

    placeholder_values = {"", "todo", "tbd", "placeholder", "none", "n/a", "unreviewed"}
    count = 0
    for item in value:
        if isinstance(item, str):
            if item.strip().lower() not in placeholder_values:
                count += 1
        elif isinstance(item, dict):
            if any(
                isinstance(nested, str) and nested.strip().lower() not in placeholder_values
                for nested in item.values()
            ):
                count += 1
    return count


def _release_freshness(repo_root: Path, cards_dir: Path) -> dict[str, Any]:
    structured_latest = _latest_release_card(cards_dir / "release")
    manifest_path = repo_root / "data" / "normalized" / "derivative" / "build_manifest.json"
    docsbrain_latest = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            docsbrain_latest = manifest.get("latest_build")
        except (OSError, json.JSONDecodeError):
            docsbrain_latest = None
    return {
        "structured_latest_build": structured_latest,
        "docsbrain_manifest_latest_build": docsbrain_latest,
        "docsbrain_trails_structured_cards": (
            bool(structured_latest and docsbrain_latest)
            and _parse_build_key(docsbrain_latest) < _parse_build_key(structured_latest)
        ),
    }


def _latest_release_card(release_dir: Path) -> str | None:
    builds: list[str] = []
    if not release_dir.is_dir():
        return None
    for path in release_dir.glob("*.json"):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        build = card.get("build")
        if build:
            builds.append(str(build))
    if not builds:
        return None
    return sorted(builds, key=_parse_build_key, reverse=True)[0]


def _parse_build_key(build: str) -> tuple[int, int]:
    try:
        year, number = build.split(".", 1)
        return int(year), int(number)
    except (AttributeError, ValueError):
        return 0, 0


def _docsbrain_operator_coverage(
    *,
    repo_root: Path,
    cards_dir: Path,
    structured_operator_types: set[str],
    structured_family_counts: dict[str, int],
    required_profile_operators: set[str],
) -> dict[str, Any]:
    """Compare the full Derivative DocsBrain operator corpus with JSON cards."""
    db_path = repo_root / "data" / "normalized" / "derivative" / "docsbrain.db"
    if not db_path.exists():
        return {
            "available": False,
            "reason": f"DocsBrain database not found at {db_path}",
            "docsbrain_operator_count": 0,
            "docsbrain_operator_counts_by_family": {},
            "structured_operator_card_count": len(structured_operator_types),
            "structured_operator_card_counts_by_family": dict(sorted(structured_family_counts.items())),
            "structured_coverage": 0.0,
            "missing_operator_card_count": 0,
            "missing_operator_card_counts_by_family": {},
            "deprecated_missing_operator_cards": [],
            "priority_missing_operator_cards": [],
        }

    operators = _load_docsbrain_operators(db_path)
    docsbrain_types = {item["op_type"] for item in operators}
    missing = [item for item in operators if item["op_type"] not in structured_operator_types]
    deprecated_missing = [item for item in missing if item.get("deprecated")]
    active_missing = [item for item in missing if not item.get("deprecated")]
    release_mentions = _release_operator_mentions(cards_dir / "release")

    return {
        "available": True,
        "docsbrain_operator_count": len(docsbrain_types),
        "docsbrain_operator_counts_by_family": _count_by_family(operators),
        "structured_operator_card_count": len(structured_operator_types),
        "structured_operator_card_counts_by_family": dict(sorted(structured_family_counts.items())),
        "structured_coverage": round(
            len(docsbrain_types & structured_operator_types) / len(docsbrain_types), 4
        )
        if docsbrain_types
        else 0.0,
        "missing_operator_card_count": len(missing),
        "missing_operator_card_counts_by_family": _count_by_family(missing),
        "deprecated_missing_operator_cards": [
            _deprecated_missing_operator_card(item) for item in deprecated_missing
        ],
        "priority_missing_operator_cards": _priority_missing_operators(
            active_missing,
            release_mentions=release_mentions,
            required_profile_operators=required_profile_operators,
        ),
    }


def _load_docsbrain_operators(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT
                operator_family,
                operator_name,
                MAX(
                    CASE
                        WHEN lower(content) LIKE '%deprecated%' THEN 1
                        WHEN lower(content) LIKE '%has been replaced by%' THEN 1
                        WHEN lower(content) LIKE '%please use % in the future%' THEN 1
                        ELSE 0
                    END
                ) AS deprecated
            FROM chunks
            WHERE doc_type = 'operator'
              AND operator_name IS NOT NULL
              AND operator_name != ''
              AND operator_family IS NOT NULL
              AND operator_family != ''
            GROUP BY operator_family, operator_name
            ORDER BY operator_family, operator_name
            """
        ).fetchall()
    finally:
        conn.close()

    operators: list[dict[str, Any]] = []
    for family, display_name, deprecated in rows:
        display = str(display_name)
        if _is_docs_article_operator_name(display):
            continue
        op_type = _operator_name_to_op_type(display)
        if not op_type:
            continue
        operators.append(
            {
                "op_type": op_type,
                "display_name": display,
                "family": str(family).upper(),
                "docs_url": f"https://docs.derivative.ca/{display.replace(' ', '_')}",
                "deprecated": bool(deprecated),
            }
        )
    return operators


def _deprecated_missing_operator_card(item: dict[str, Any]) -> dict[str, Any]:
    base = {key: item[key] for key in ("op_type", "display_name", "family", "docs_url")}
    note = _DEPRECATED_OPERATOR_GAP_NOTES.get(
        item["op_type"],
        {
            "gap_status": "deprecated_unreviewed",
            "replacement_op_types": [],
            "official_doc_note": "DocsBrain marks this operator deprecated, but no manual atlas note has been recorded yet.",
            "planner_guidance": "Review the official Derivative docs before planning or promoting this operator.",
        },
    )
    return base | note | {"source_url": base["docs_url"]}


def _is_docs_article_operator_name(display_name: str) -> bool:
    """Filter tutorial/article pages that DocsBrain labels with an operator family."""
    return display_name.startswith(("Write a ", "Anatomy of a "))


def _operator_name_to_op_type(display_name: str) -> str:
    parts = display_name.split()
    if len(parts) < 2:
        return ""
    return "".join(part.lower() for part in parts[:-1]) + parts[-1]


def _count_by_family(operators: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in operators:
        family = item["family"].upper()
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def _release_operator_mentions(release_dir: Path) -> set[str]:
    mentions: set[str] = set()
    if not release_dir.is_dir():
        return mentions
    for path in release_dir.glob("*.json"):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("new_ops", "changed_ops"):
            for item in card.get(key, []):
                if isinstance(item, dict) and item.get("type"):
                    mentions.add(str(item["type"]).lower())
        for highlight in card.get("highlights", []):
            if isinstance(highlight, str):
                maybe_type = _operator_name_to_op_type(highlight)
                if maybe_type:
                    mentions.add(maybe_type.lower())
    return mentions


def _priority_missing_operators(
    missing: list[dict[str, Any]],
    *,
    release_mentions: set[str],
    required_profile_operators: set[str],
    limit: int = 40,
) -> list[dict[str, Any]]:
    ranked = []
    for item in missing:
        score, reasons = _missing_operator_priority(
            item,
            release_mentions=release_mentions,
            required_profile_operators=required_profile_operators,
        )
        ranked.append(
            {key: item[key] for key in ("op_type", "display_name", "family", "docs_url")}
            | {"priority_score": score, "priority_reasons": reasons}
        )
    ranked.sort(key=lambda item: (-item["priority_score"], item["family"], item["op_type"]))
    return ranked[:limit]


def _missing_operator_priority(
    item: dict[str, Any],
    *,
    release_mentions: set[str],
    required_profile_operators: set[str],
) -> tuple[int, list[str]]:
    family = item["family"].upper()
    display_lower = item["display_name"].lower()
    op_type_lower = item["op_type"].lower()

    family_scores = {
        "POP": 60,
        "TOP": 32,
        "MAT": 30,
        "CHOP": 24,
        "SOP": 18,
        "DAT": 14,
        "COMP": 12,
    }
    score = family_scores.get(family, 8)
    reasons = [f"family:{family}"]

    term_scores = {
        "glsl": 26,
        "render": 22,
        "particle": 20,
        "feedback": 18,
        "cache": 16,
        "attribute": 16,
        "math": 15,
        "transform": 14,
        "texture": 13,
        "normal": 12,
        "merge": 12,
        "switch": 10,
        "select": 10,
        "convert": 10,
        "copy": 8,
    }
    for term, value in term_scores.items():
        if term in display_lower:
            score += value
            reasons.append(f"term:{term}")

    if " to " in display_lower:
        score += 15
        reasons.append("bridge-operator")

    if op_type_lower in release_mentions:
        score += 25
        reasons.append("recent-release-mention")

    if item["op_type"] in required_profile_operators:
        score += 50
        reasons.append("required-by-profile")

    return score, reasons


__all__ = ["audit_brain_atlas"]
