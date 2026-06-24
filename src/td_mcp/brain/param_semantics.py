"""Parameter semantics registry and pre-transaction PatchPlan checks."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from td_mcp.brain.validators import validate_reference_params_for_plan
from td_mcp.models.brain import ParamSemantics, ValidationIssue
from td_mcp.models.patch import PatchPlan

_CREATE_TYPE_ALIASES: dict[str, str] = {
    "glsl": "glslTOP",
    "glsltop": "glslTOP",
    "glslmat": "glslMAT",
    "glslcomp": "glslCOMP",
    "glslpop": "glslPOP",
    "glslmulti": "glslmultiTOP",
    "glslmultitop": "glslmultiTOP",
    "rendersimple": "rendersimpleTOP",
    "rendersimpletop": "rendersimpleTOP",
    "render": "renderTOP",
    "rendertop": "renderTOP",
}
_PARAM_NAME_ALIASES: dict[tuple[str, str], str] = {
    ("noiseTOP", "harmonics"): "harmon",
    ("noiseTOP", "roughness"): "rough",
    ("noiseTOP", "amplitude"): "amp",
}
_GLSL_ADVANCED_POP_DOCS = "https://docs.derivative.ca/GLSL_Advanced_POP"
_DAT_EXECUTE_DOCS = "https://docs.derivative.ca/DAT_Execute_DAT"
_CHOP_EXECUTE_DOCS = "https://docs.derivative.ca/CHOP_Execute_DAT"
_EXECUTE_DAT_DOCS = "https://docs.derivative.ca/Execute_DAT"
_OP_EXECUTE_DOCS = "https://docs.derivative.ca/OP_Execute_DAT"
_PARAMETER_EXECUTE_DOCS = "https://docs.derivative.ca/Parameter_Execute_DAT"
_PANEL_EXECUTE_DOCS = "https://docs.derivative.ca/Panel_Execute_DAT"
_PARGROUP_EXECUTE_DOCS = "https://docs.derivative.ca/ParGroup_Execute_DAT"
_SERIAL_DAT_DOCS = "https://docs.derivative.ca/Serial_DAT"
_OSC_IN_DAT_DOCS = "https://docs.derivative.ca/OSC_In_DAT"
_WEBSOCKET_DAT_DOCS = "https://docs.derivative.ca/WebSocket_DAT"
_WEB_CLIENT_DAT_DOCS = "https://docs.derivative.ca/Web_Client_DAT"
_WEB_SERVER_DAT_DOCS = "https://docs.derivative.ca/Web_Server_DAT"
_MIDI_IN_CHOP_DOCS = "https://docs.derivative.ca/MIDI_In_CHOP"
_MQTT_CLIENT_DAT_DOCS = "https://docs.derivative.ca/MQTT_Client_DAT"
_UDP_IN_DAT_DOCS = "https://docs.derivative.ca/UDP_In_DAT"
_ERROR_DAT_DOCS = "https://docs.derivative.ca/Error_DAT"
_TABLE_DAT_DOCS = "https://docs.derivative.ca/Table_DAT"
_SELECT_DAT_DOCS = "https://docs.derivative.ca/Select_DAT"
_RENDER_TOP_DOCS = "https://docs.derivative.ca/Render_TOP"
_GEOMETRY_COMP_DOCS = "https://docs.derivative.ca/Geometry_COMP"
_CAMERA_COMP_DOCS = "https://docs.derivative.ca/Camera_COMP"
_LIGHT_COMP_DOCS = "https://docs.derivative.ca/Light_COMP"
_PBR_MAT_DOCS = "https://docs.derivative.ca/PBR_MAT"
_PHONG_MAT_DOCS = "https://docs.derivative.ca/Phong_MAT"
_GLSL_TOP_DOCS = "https://docs.derivative.ca/GLSL_TOP"
_GLSL_MULTI_TOP_DOCS = "https://docs.derivative.ca/GLSL_Multi_TOP"
_GLSL_POP_DOCS = "https://docs.derivative.ca/GLSL_POP"
_GLSL_MAT_DOCS = "https://docs.derivative.ca/GLSL_MAT"
_GLSL_COMP_DOCS = "https://docs.derivative.ca/GLSL_COMP"
_RENDER_SIMPLE_TOP_DOCS = "https://docs.derivative.ca/Render_Simple_TOP"
_CIRCLE_POP_DOCS = "https://docs.derivative.ca/Circle_POP"
_NOISE_POP_DOCS = "https://docs.derivative.ca/Noise_POP"
_MATH_MIX_POP_DOCS = "https://docs.derivative.ca/Math_Mix_POP"
_ATTRIBUTE_COMBINE_POP_DOCS = "https://docs.derivative.ca/Attribute_Combine_POP"
_GRID_SOP_DOCS = "https://docs.derivative.ca/Grid_SOP"
_NOISE_SOP_DOCS = "https://docs.derivative.ca/Noise_SOP"
_TRANSFORM_SOP_DOCS = "https://docs.derivative.ca/Transform_SOP"
_NDI_IN_TOP_DOCS = "https://docs.derivative.ca/NDI_In_TOP"
_KINECT_AZURE_TOP_DOCS = "https://docs.derivative.ca/Kinect_Azure_TOP"
_MOVIE_FILE_IN_TOP_DOCS = "https://docs.derivative.ca/Movie_File_In_TOP"
_VIDEO_DEVICE_IN_TOP_DOCS = "https://docs.derivative.ca/Video_Device_In_TOP"
_NOISE_TOP_DOCS = "https://docs.derivative.ca/Noise_TOP"
_TRANSFORM_TOP_DOCS = "https://docs.derivative.ca/Transform_TOP"
_CACHE_TOP_DOCS = "https://docs.derivative.ca/Cache_TOP"
_FEEDBACK_TOP_DOCS = "https://docs.derivative.ca/Feedback_TOP"
_LEVEL_TOP_DOCS = "https://docs.derivative.ca/Level_TOP"
_EDGE_TOP_DOCS = "https://docs.derivative.ca/Edge_TOP"
_BLUR_TOP_DOCS = "https://docs.derivative.ca/Blur_TOP"
_COMPOSITE_TOP_DOCS = "https://docs.derivative.ca/Composite_TOP"
_SWITCH_TOP_DOCS = "https://docs.derivative.ca/Switch_TOP"
_BASE_COMP_DOCS = "https://docs.derivative.ca/Base_COMP"
_CONTAINER_COMP_DOCS = "https://docs.derivative.ca/Container_COMP"
_SLIDER_COMP_DOCS = "https://docs.derivative.ca/Slider_COMP"
_BUTTON_COMP_DOCS = "https://docs.derivative.ca/Button_COMP"
_PANEL_CHOP_DOCS = "https://docs.derivative.ca/Panel_CHOP"
_PARAMETER_COMP_DOCS = "https://docs.derivative.ca/Parameter_COMP"
_LFO_CHOP_DOCS = "https://docs.derivative.ca/LFO_CHOP"
_WAVE_CHOP_DOCS = "https://docs.derivative.ca/Wave_CHOP"
_NOISE_CHOP_DOCS = "https://docs.derivative.ca/Noise_CHOP"
_AUDIO_FILE_IN_CHOP_DOCS = "https://docs.derivative.ca/Audio_File_In_CHOP"
_AUDIO_FILE_OUT_CHOP_DOCS = "https://docs.derivative.ca/Audio_File_Out_CHOP"
_AUDIO_DEVICE_IN_CHOP_DOCS = "https://docs.derivative.ca/Audio_Device_In_CHOP"
_AUDIO_DEVICE_OUT_CHOP_DOCS = "https://docs.derivative.ca/Audio_Device_Out_CHOP"
_ANALYZE_CHOP_DOCS = "https://docs.derivative.ca/Analyze_CHOP"
_MATH_CHOP_DOCS = "https://docs.derivative.ca/Math_CHOP"
_FILTER_CHOP_DOCS = "https://docs.derivative.ca/Filter_CHOP"
_LAG_CHOP_DOCS = "https://docs.derivative.ca/Lag_CHOP"
_LARGE_POP_CAPACITY_THRESHOLD = 1_000_000.0
_LARGE_GEOMETRY_INSTANCE_THRESHOLD = 1_000_000.0
_MAX_POP_CAPACITY_GUARD = 1_000_000_000.0
_PRIORITY_SEMANTICS_GROUPS: dict[str, tuple[str, ...]] = {
    "render_material": (
        "renderTOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "glslMAT",
        "pbrMAT",
        "phongMAT",
    ),
    "glsl": (
        "glslTOP",
        "glslmultiTOP",
        "glslPOP",
        "glsladvancedPOP",
        "glslCOMP",
    ),
    "feedback_top_processing": (
        "moviefileinTOP",
        "videodeviceinTOP",
        "noiseTOP",
        "feedbackTOP",
        "levelTOP",
        "compositeTOP",
        "transformTOP",
        "cacheTOP",
    ),
    "pop": (
        "circlePOP",
        "noisePOP",
        "mathmixPOP",
        "attributecombinePOP",
        "rendersimpleTOP",
    ),
    "sop_geometry": (
        "gridSOP",
        "noiseSOP",
        "transformSOP",
    ),
    "audio_control": (
        "audiofileinCHOP",
        "audiofileoutCHOP",
        "audiodeviceinCHOP",
        "audiodeviceoutCHOP",
        "lfoCHOP",
        "waveCHOP",
        "noiseCHOP",
        "midiinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "filterCHOP",
        "lagCHOP",
    ),
    "panel_parameters": (
        "baseCOMP",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "parameterCOMP",
    ),
    "dat_callbacks_protocols": (
        "datexecuteDAT",
        "chopexecuteDAT",
        "executeDAT",
        "tableDAT",
        "selectDAT",
        "serialDAT",
        "oscinDAT",
        "websocketDAT",
        "webclientDAT",
        "webserverDAT",
        "mqttclientDAT",
        "udpinDAT",
    ),
}
_CHOP_UNIT_MENU_VALUES = ["Samples", "Frames", "Seconds", "samples", "frames", "seconds"]
_AUDIO_INDEX_UNIT_VALUES = ["Index", "index", "Frames", "frames", "Seconds", "seconds"]
_AUDIO_FILE_PLAY_MODE_VALUES = [
    "Locked to Timeline",
    "locked",
    "Specify Index",
    "specify",
    "Sequential",
    "sequential",
    "Timecode Object/CHOP/DAT",
    "timecodeop",
]
_AUDIO_REPEAT_VALUES = ["Off", "off", "On", "on"]
_AUDIO_FILE_OUT_TYPE_VALUES = ["WAV", "wav", "OGG", "ogg", "MP3", "mp3", "AIFF", "aiff"]
_AUDIO_DEVICE_DRIVER_VALUES = [
    "DirectSound/CoreAudio",
    "default",
    "ASIO",
    "asio",
    "DataPath (RGBEASY)",
    "datapath",
    "Blackmagic",
    "blackmagic",
    "AJA",
    "aja",
]
_AUDIO_DEVICE_FORMAT_VALUES = ["Mono", "mono", "Stereo", "stereo", "Multi-Channel", "multichannel"]
_AUDIO_DEVICE_CHANNEL_TOGGLES = [
    ("frontleft", "Front Left"),
    ("frontright", "Front Right"),
    ("frontcenter", "Front Center"),
    ("lowfrequency", "Low Frequency"),
    ("backleft", "Back Left"),
    ("backright", "Back Right"),
    ("frontleftcenter", "Front Left of Center"),
    ("frontrightcenter", "Front Right of Center"),
    ("backcenter", "Back Center"),
    ("sideleft", "Side Left"),
    ("sideright", "Side Right"),
    ("topcenter", "Top Center"),
    ("topfrontleft", "Top Front Left"),
    ("topfrontcenter", "Top Front Center"),
    ("topfrontright", "Top Front Right"),
    ("topbackleft", "Top Back Left"),
    ("topbackcenter", "Top Back Center"),
    ("topbackright", "Top Back Right"),
]
_MIDI_IN_SOURCE_VALUES = ["Device", "device", "Internal", "internal", "File", "file"]
_MOVIE_FILE_TOP_PLAY_MODE_VALUES = [
    "Locked to Timeline",
    "locked",
    "Specify Index",
    "specify",
    "Sequential",
    "sequential",
]
_MOVIE_FILE_TOP_IMAGE_INDEXING_VALUES = [
    "Zero Based",
    "zero",
    "One Based",
    "one",
    "Native",
    "native",
]
_TOP_COLOR_SPACE_VALUES = [
    "Automatic",
    "auto",
    "sRGB",
    "srgb",
    "Linear",
    "linear",
    "Rec. 709",
    "rec709",
    "Raw",
    "raw",
]
_MOVIE_DECODE_PIXEL_FORMAT_VALUES = [
    "Automatic",
    "auto",
    "8-bit fixed",
    "rgba8",
    "16-bit float",
    "rgba16float",
    "32-bit float",
    "rgba32float",
]
_VIDEO_DEVICE_DRIVER_VALUES = [
    "Default",
    "default",
    "DirectShow",
    "directshow",
    "Media Foundation",
    "mediafoundation",
    "AVFoundation",
    "avfoundation",
    "Blackmagic",
    "blackmagic",
    "AJA",
    "aja",
    "DataPath",
    "datapath",
]
_VIDEO_DEVICE_DEINTERLACE_VALUES = [
    "Off",
    "off",
    "Blend",
    "blend",
    "Bob",
    "bob",
]
_VIDEO_DEVICE_PRECEDENCE_VALUES = [
    "Newest",
    "newest",
    "Oldest",
    "oldest",
]
_VIDEO_DEVICE_SIGNAL_FORMAT_VALUES = [
    "Automatic",
    "auto",
    "NTSC",
    "ntsc",
    "PAL",
    "pal",
    "720p",
    "1080p",
    "2160p",
]
_VIDEO_DEVICE_PIXEL_FORMAT_VALUES = [
    "Automatic",
    "auto",
    "8-bit RGBA",
    "rgba8",
    "10-bit YUV",
    "yuv10",
    "16-bit float",
    "rgba16float",
]
_VIDEO_DEVICE_REFERENCE_WHITE_VALUES = [
    "Default",
    "default",
    "100 nits",
    "100",
    "203 nits",
    "203",
]
_VIDEO_DEVICE_TRANSFER_MODE_VALUES = [
    "Automatic",
    "auto",
    "CPU",
    "cpu",
    "GPU Direct",
    "gpudirect",
]
_VIDEO_DEVICE_MEMORY_MODE_VALUES = [
    "Automatic",
    "auto",
    "CPU",
    "cpu",
    "GPU",
    "gpu",
]
_NOISE_TOP_TYPE_VALUES = [
    "Perlin",
    "perlin",
    "Simplex",
    "simplex",
    "Simplex 2D",
    "simplex2d",
    "Simplex 3D",
    "simplex3d",
    "Simplex 4D",
    "simplex4d",
    "Random GPU",
    "randomgpu",
    "Sparse",
    "sparse",
    "Hermite",
    "hermite",
    "Harmonic Summation",
    "harmonic",
    "harmonicsum",
    "Random",
    "random",
    "Alligator",
    "alligator",
]
_NOISE_TOP_COMBINE_VALUES = [
    "Noise",
    "noise",
    "Input",
    "input",
    "Input * Noise",
    "multiply",
    "inputnoise",
    "Input + Noise",
    "add",
    "Input - Noise",
    "subtract",
    "sub",
]
_NOISE_TOP_ALPHA_VALUES = [
    "Zero",
    "zero",
    "One",
    "one",
    *_NOISE_TOP_COMBINE_VALUES,
]
_NOISE_TOP_MODE_VALUES = ["Performance", "performance", "Quality", "quality"]
_ANALYZE_CHOP_FUNCTIONS = [
    "Average",
    "average",
    "Maximum",
    "maximum",
    "Minimum",
    "minimum",
    "Index of Maximum",
    "maximumindex",
    "Index of Minimum",
    "minimumindex",
    "Sum",
    "sum",
    "RMS Power",
    "rmspower",
    "Value of First Peak",
    "firstpeakvalue",
    "Index of First Peak",
    "firstpeakindex",
    "Value of Last Peak",
    "lastpeakvalue",
    "Index of Last Peak",
    "lastpeakindex",
    "Value of Highest Peak",
    "highestpeakvalue",
    "Index of Highest Peak",
    "highestpeakindex",
    "Value of Lowest Peak",
    "lowestpeakvalue",
    "Index of Lowest Peak",
    "lowestpeakindex",
    "Total Peaks",
    "totalpeaks",
    "Duplicates",
    "duplicates",
]
_CHOP_SAMPLE_RATE_MATCH_VALUES = [
    "Resample At First Input's Rate",
    "first",
    "Resample At Maximum Rate",
    "max",
    "Resample At Minimum Rate",
    "min",
    "Error If Rates Differ",
    "err",
]
_CHOP_EXPORT_METHOD_VALUES = [
    "DAT Table by Index",
    "datindex",
    "DAT Table by Name",
    "datname",
    "Channel Name is Path:Parameter",
    "autoname",
]
_CHOP_RESET_CONDITION_VALUES = [
    "Off to On",
    "offtoon",
    "While On",
    "whileon",
    "On to Off",
    "ontooff",
    "While Off",
    "whileoff",
]
_LFO_CHOP_WAVE_TYPE_VALUES = [
    "Sine",
    "sine",
    "Gaussian",
    "gaussian",
    "Triangle",
    "triangle",
    "Ramp",
    "ramp",
    "Square",
    "square",
    "Pulse",
    "pulse",
]
_WAVE_CHOP_WAVE_TYPE_VALUES = [
    "Constant",
    "constant",
    "const",
    "Sine",
    "sine",
    "sin",
    "Gaussian",
    "gaussian",
    "normal",
    "Triangle",
    "triangle",
    "tri",
    "Ramp",
    "ramp",
    "Square",
    "square",
    "Pulse",
    "pulse",
    "Expression",
    "expression",
    "expr",
]
_NOISE_CHOP_TYPE_VALUES = [
    "Sparse",
    "sparse",
    "Hermite",
    "hermite",
    "Harmonic",
    "harmonic",
    "Brownian",
    "brownian",
    "Random",
    "random",
    "Alligator",
    "alligator",
]
_NOISE_CHOP_PERIOD_UNIT_VALUES = [*_CHOP_UNIT_MENU_VALUES, "Fraction", "fraction"]
_SWITCH_INDEX_TABLE_EXPR = re.compile(
    r"^min\(1,\s*max\(0,\s*int\(op\('(?P<path>[^']+)'\)\[1,\s*'selected_index'\]\)\)\)$"
)
_CHOP_REFERENCE_EXPR = re.compile(r"^op\('(?P<path>[^']+)'\)\[(?P<index>[0-9]+|'[^']+')\]$")
_MATH_CHOP_UNARY_OP_VALUES = [
    "Off",
    "off",
    "Negate",
    "negate",
    "Positive",
    "pos",
    "Root",
    "root",
    "Square",
    "square",
    "Inverse",
    "inverse",
]
_MATH_CHOP_COMBINE_VALUES = [
    "Off",
    "off",
    "Add",
    "add",
    "Subtract",
    "sub",
    "Multiply",
    "mul",
    "Divide",
    "div",
    "Average",
    "avg",
    "Minimum",
    "min",
    "Maximum",
    "max",
    "Length",
    "len",
]
_MATH_CHOP_MATCH_VALUES = ["Channel Number", "index", "Channel Name", "name"]
_MATH_CHOP_ALIGN_VALUES = [
    "Automatic",
    "auto",
    "Extend to Min/Max",
    "none",
    "Stretch to Min/Max",
    "stretch",
    "Shift to Minimum",
    "start",
    "Shift to Maximum",
    "end",
    "Shift to First Interval",
    "shift1",
    "Trim to First Interval",
    "trim1",
    "Stretch to First Interval",
    "stretch1",
    "Trim to Smallest Interval",
    "trim",
    "Stretch to Smallest Interval",
    "squash",
]
_MATH_CHOP_INTEGER_VALUES = ["Off", "off", "Ceiling", "ceiling", "Floor", "floor", "Round", "round"]
_FILTER_CHOP_TYPES = [
    "Gaussian",
    "gauss",
    "Left Half Gaussian",
    "halfgauss",
    "Box",
    "box",
    "Left Half Box",
    "halfbox",
    "Edge Detect",
    "edge",
    "Sharpen",
    "sharpen",
    "De-spike",
    "despike",
    "Ramp Preserve",
    "ramp",
    "One Euro",
    "oneeuro",
]
_LAG_CHOP_METHODS = [
    "Lag Value",
    "value",
    "Lag Amplitude",
    "amp",
    "Lag Magnitude",
    "mag",
    "Quaternion Rotation",
    "Quaternion Rotation (Commercial)",
    "rotation",
]
_GLSL_VERSION_VALUES = [
    "glsl120",
    "glsl330",
    "glsl400",
    "glsl410",
    "glsl420",
    "glsl430",
    "glsl440",
    "glsl450",
    "glsl460",
]
_GLSL_SHADER_MODE_VALUES = [
    "Vertex/Pixel Shader",
    "vertexpixel",
    "Compute Shader",
    "compute",
]
_GLSL_OUTPUT_ACCESS_VALUES = [
    "Write Only",
    "writeonly",
    "Read Only",
    "readonly",
    "Read-Write",
    "readwrite",
]
_GLSL_TOP_OUTPUT_ACCESS_VALUES = [
    "Write Only",
    "writeonly",
    "Read-Write",
    "readwrite",
]
_GLSL_MULTI_OUTPUT_TYPE_VALUES = [
    "2D Texture",
    "texture2d",
    "2D Texture Array",
    "texture2darray",
    "3D Texture",
    "texture3d",
]
_GLSL_COMPILE_BEHAVIOR_VALUES = [
    "Stall Until Done",
    "stalluntildone",
    "Threaded, Show Checkerboard Until Done",
    "threadedcheckerboard",
    "Threaded, Show Black Until Done",
    "threadedblack",
    "Threaded, Show Previous Shader Until Done",
    "threadedprevious",
]
_GLSL_ERROR_BEHAVIOR_VALUES = [
    "Show Checkerboard",
    "showcheckerboard",
    "Show Black",
    "showblack",
    "Show Previous Shader",
    "showprevious",
]
_GLSL_SIMPLEX_NOISE_VALUES = ["Performance", "performance", "Quality", "quality"]
_INPUT_OR_CUSTOM_VALUES = ["Input", "input", "Custom", "custom"]
_GLSL_MULTI_INPUT_MAPPING_VALUES = [
    "All Inputs to Every Slice",
    "all",
    "N Input(s) per Slice",
    "ninputs",
]
_GLSL_ARRAY_TYPE_VALUES = ["float", "vec2", "vec3", "vec4"]
_GLSL_ARRAY_STORAGE_VALUES = ["Uniform Array", "uniformarray", "Texture Buffer", "texturebuffer"]
_GLSL_ATOMIC_COUNTER_INIT_VALUES = ["Single Value", "val", "CHOP Values", "chop"]
_GLSL_COMP_FILTER_VALUES = ["Nearest", "nearest", "Linear", "linear", "Mipmap Linear", "mipmaplinear"]
_GLSL_COMP_ANISOTROPY_VALUES = ["Off", "off", "2x", "4x", "8x", "16x"]
_MAT_TEXTURE_SAMPLING_MODE_VALUES = [
    "Regular",
    "regular",
    "Screen Space Coordinates",
    "screenspace",
    "Triplanar Mapping",
    "triplanar",
]
_MAT_TEXTURE_COORD_VALUES = [
    "Texture Layer 0 (uv[0-2])",
    "uv0",
    "Texture Layer 1 (uv[3-5])",
    "uv1",
    "Texture Layer 2 (uv[6-8])",
    "uv2",
    "Texture Layer 3 (uv[9-11])",
    "uv3",
    "Texture Layer 4 (uv[12-14])",
    "uv4",
    "Texture Layer 5 (uv[15-17])",
    "uv5",
    "Texture Layer 6 (uv[18-20])",
    "uv6",
    "Texture Layer 7 (uv[21-23])",
    "uv7",
]
_MAT_TEXTURE_COORD_INTERP_VALUES = [
    "Perspective Correct",
    "perspectivecorrect",
    "Linear (noperspective)",
    "linear",
]
_MAT_CHANNEL_SOURCE_VALUES = [
    "Luminance",
    "luminance",
    "Red",
    "red",
    "Green",
    "green",
    "Blue",
    "blue",
    "Alpha",
    "alpha",
    "RGB Average",
    "rgbaverage",
    "RGBA Average",
    "average",
]
_GLSL_COMP_FIXED_ASPECT_VALUES = ["Off", "off", "Use Horizontal", "horizontal", "Use Vertical", "vertical"]
_GLSL_COMP_LAYOUT_MODE_VALUES = ["Fixed Width", "Fixed Height", "fixed", "Fill", "fill", "Anchors", "anchors"]
_POP_ATTRIBUTE_CLASS_VALUES = [
    "point",
    "vertex",
    "primitive",
]
_CIRCLE_CONNECTIVITY_VALUES = [
    "None",
    "none",
    "Point Primitives",
    "points",
    "Surface",
    "surface",
    "Line Strip",
    "linestrip",
    "Lines",
    "lines",
]
_CIRCLE_ORIENT_VALUES = ["XY Plane", "xy", "YZ Plane", "yz", "ZX Plane", "zx"]
_CIRCLE_ATTRIBUTE_OUTPUT_VALUES = ["None", "none", "Point", "pointNormals", "Vertex", "vertNormals"]
_NOISE_TYPE_VALUES = [
    "Perlin 2D (GPU)",
    "perlin2d",
    "Perlin 3D (GPU)",
    "perlin3d",
    "Perlin 4D (GPU)",
    "perlin4d",
    "Simplex 2D (GPU)",
    "simplex2d",
    "Simplex 3D (GPU)",
    "simplex3d",
    "Simplex 4D (GPU)",
    "simplex4d",
]
_NOISE_SIZE_VALUES = ["1", "2", "3", "4"]
_ROTATE_ORDER_VALUES = [
    "Rx Ry Rz",
    "xyz",
    "Rx Rz Ry",
    "xzy",
    "Ry Rx Rz",
    "yxz",
    "Ry Rz Rx",
    "yzx",
    "Rz Rx Ry",
    "zxy",
    "Rz Ry Rx",
    "zyx",
]
_NOISE_COMBINE_VALUES = [
    "None",
    "none",
    "Add",
    "add",
    "Multiply",
    "mult",
    "Translate along Normal",
    "translatealongnormal",
]
_NOISE_COMBINE_ENTITY_VALUES = ["Noise", "noise", "Curl 3D", "curl3d", "Curl 2D", "curl2d"]
_NOISE_ATTR_TYPE_VALUES = [
    "float",
    "double",
    "int",
    "uint",
    "Color",
    "color",
    "Color (double)",
    "dcolor",
    "Direction",
    "dir",
    "Direction (double)",
    "ddir",
]
_NOISE_MODE_VALUES = ["Performance", "performance", "Quality", "quality"]
_NOISE_MAP_PARM_VALUES = ["period", "offset", "amp", "exp", "spread", "gain"]
_MAP_COMBINE_VALUES = ["Set", "set", "Multiply", "mult", "Add", "add"]
_ANGLE_UNIT_VALUES = ["Degrees", "degrees", "Radians", "radians", "Cycles", "cycles"]
_LENGTH_MISMATCH_NOTIF_VALUES = ["Ignore", "ignore", "Warning", "warning", "Error", "error"]
_MATH_MIX_VEC_TYPE_VALUES = [
    "float",
    "float2",
    "float3",
    "float4",
    "double",
    "double2",
    "double3",
    "double4",
    "int",
    "int2",
    "int3",
    "int4",
    "uint",
    "uint2",
    "uint3",
    "uint4",
]
_MATH_MIX_COMBINE_VALUES = [
    "none",
    "copya",
    "abs",
    "sign",
    "sqrt",
    "square",
    "inverse",
    "floor",
    "round",
    "ceil",
    "int",
    "fract",
    "normalize",
    "exp10",
    "exp2",
    "exp",
    "log10",
    "log2",
    "ln",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "degrees",
    "radians",
    "length",
    "add",
    "asubb",
    "bsuba",
    "mult",
    "adivb",
    "bdiva",
    "apowerb",
    "avg",
    "min",
    "max",
    "mod",
    "dot",
    "angle",
    "cross",
    "mix",
    "clamp",
    "smoothstep",
    "rgbtohsv",
    "hsvtorgb",
]
_ATTRIBUTE_COMBINE_DUPLICATE_VALUES = [
    "Auto-Rename",
    "autorename",
    "Keep First",
    "keepfirst",
    "Keep Last",
    "keeplast",
    "Only Replace Attribs of First Input",
    "replaceattribs",
]
_GLSL_POP_THREAD_MODE_VALUES = [
    "automatic",
    "input",
    "manual",
    "manualnumelems",
    "Manual Number of Elements",
    "attribute",
    "Attribute Value",
]
_DAT_EXECUTE_LOCATION_VALUES = [
    "Current Node",
    "current",
    "This Node",
    "here",
    "Specified Operator",
    "op",
]
_CALLBACK_DAT_EXECUTE_LOCATION_VALUES = [
    "Current Node",
    "current",
    "Callbacks DAT",
    "callbacks",
    "Specified Operator",
    "op",
]
_CHOP_EXECUTE_FREQ_VALUES = [
    "Execute For Every Sample",
    "everysample",
    "Execute Once Per Frame",
    "onceperframe",
]
_DAT_EXECUTE_TRIGGER_PARAMS = [
    ("tablechange", "Table Change"),
    ("rowchange", "Row Change"),
    ("colchange", "Column Change"),
    ("cellchange", "Cell Change"),
    ("sizechange", "Size Change"),
]
_DAT_EXECUTE_EXECUTE_VALUES = [
    "Start of Frame",
    "start",
    "End of Frame",
    "end",
]
_CHOP_EXECUTE_TRIGGER_PARAMS = [
    ("offtoon", "Off to On"),
    ("whileon", "While On"),
    ("ontooff", "On to Off"),
    ("whileoff", "While Off"),
    ("valuechange", "Value Change"),
]
_EXECUTE_DAT_TRIGGER_PARAMS = [
    ("start", "Start"),
    ("create", "Create"),
    ("exit", "Exit"),
    ("framestart", "Frame Start"),
    ("frameend", "Frame End"),
    ("playstatechange", "Play State Change"),
    ("devicechange", "Device Change"),
]
_OP_EXECUTE_TRIGGER_PARAMS = [
    ("precook", "Pre Cook"),
    ("postcook", "Post Cook"),
    ("opdelete", "Destroy"),
    ("flagchange", "Flag Change"),
    ("wirechange", "Wire Change"),
    ("namechange", "Name Change"),
    ("pathchange", "Path Change"),
    ("uichange", "UI Change"),
    ("numchildrenchange", "Number Children Change"),
    ("childrename", "Child Rename"),
    ("currentchildchange", "Current Child Change"),
    ("extensionchange", "Extension Change"),
]
_PARAMETER_EXECUTE_TRIGGER_PARAMS = [
    ("valuechange", "Value Change"),
    ("valueschanged", "Values Changed"),
    ("onpulse", "On Pulse"),
    ("expressionchange", "Expression Change"),
    ("exportchange", "Export Change"),
    ("enablechange", "Enable Change"),
    ("modechange", "Mode Change"),
    ("custom", "Custom"),
    ("builtin", "Built-In"),
]
_PANEL_EXECUTE_TRIGGER_PARAMS = [
    ("offtoon", "Off to On"),
    ("whileon", "While On"),
    ("ontooff", "On to Off"),
    ("whileoff", "While Off"),
    ("valuechange", "Value Change"),
]
_PARGROUP_EXECUTE_TRIGGER_PARAMS = [
    ("valuechange", "Value Change"),
    ("onpulse", "On Pulse"),
    ("expressionchange", "Expression Change"),
    ("exportchange", "Export Change"),
    ("enablechange", "Enable Change"),
    ("modechange", "Mode Change"),
    ("custom", "Custom"),
    ("builtin", "Built-In"),
]
_PARGROUP_CALLBACK_MODE_VALUES = [
    "Per ParGroup Change",
    "pargroup",
    "Combine ParGroup Changes as List",
    "pargrouplist",
]
_SERIAL_DAT_FORMAT_VALUES = [
    "One Per Byte",
    "perbyte",
    "One Per Line",
    "perline",
    "One Per Message",
    "permessage",
]
_SERIAL_DAT_BAUD_RATE_VALUES = [
    "1200",
    "2400",
    "9600",
    "19200",
    "38400",
    "57600",
    "115200",
    "230400",
    "460800",
    "921600",
    "1382400",
]
_SERIAL_DAT_DATA_BITS_VALUES = ["6", "7", "8", "9"]
_SERIAL_DAT_PARITY_VALUES = ["Even", "even", "Odd", "odd", "None", "none"]
_SERIAL_DAT_STOP_BITS_VALUES = ["1", "2"]
_SERIAL_DAT_DTR_VALUES = ["Disable", "disable", "Enable", "enable", "Handshake", "handshake"]
_SERIAL_DAT_RTS_VALUES = [
    "Disable",
    "disable",
    "Enable",
    "enable",
    "Handshake",
    "handshake",
    "Toggle",
    "toggle",
]
_LIGHT_COMP_TYPES = [
    "Point Light",
    "point",
    "Cone Light",
    "cone",
    "Distant Light",
    "distant",
]
_LIGHT_PROJECTOR_MAP_TYPE_VALUES = [
    "Spot",
    "spot",
    "Point (Equirectangular)",
    "point",
]
_LIGHT_PROJECTOR_MAP_MODE_VALUES = [
    "Simple Horizontal FOV",
    "simplehorzfov",
    "Use View Settings",
    "useview",
]
_LIGHT_FACE_LIT_VALUES = [
    "Front Lit",
    "frontlit",
    "Back Lit",
    "backlit",
]
_LIGHT_SHADOW_TYPE_VALUES = [
    "Off",
    "off",
    "Hard, 2D Mapped",
    "hard2d",
    "Soft, 2D Mapped",
    "soft2d",
    "Custom",
    "custom",
]
_LIGHT_PROJECTION_VALUES = [
    "Perspective",
    "perspective",
    "Orthographic",
    "ortho",
    "Custom Projection Matrix",
    "custommatrix",
]
_CAMERA_PROJECTION_VALUES = [
    "Perspective",
    "perspective",
    "Orthographic",
    "ortho",
    "Perspective to Ortho Blend",
    "persporthoblend",
    "Custom Projection Matrix",
    "custommatrix",
]
_CAMERA_VIEW_ANGLE_METHOD_VALUES = [
    "Horizontal FOV",
    "horzfov",
    "Vertical FOV",
    "vertfov",
    "Focal Length and Aperture",
    "focalaperture",
]
_CAMERA_WIN_ROLL_PIVOT_VALUES = [
    "Viewport Origin",
    "viewport",
    "Camera Origin",
    "camera",
    "Legacy Behavior",
    "legacy",
]
_CAMERA_FOG_VALUES = [
    "Off",
    "off",
    "Linear",
    "linear",
    "Exponential",
    "exp",
    "Squared Exponential",
    "exp2",
]
_TRANSFORM_ORDER_VALUES = [
    "Scale Rotate Translate",
    "srt",
    "Scale Translate Rotate",
    "str",
    "Rotate Scale Translate",
    "rst",
    "Rotate Translate Scale",
    "rts",
    "Translate Scale Rotate",
    "tsr",
    "Translate Rotate Scale",
    "trs",
]
_ROTATION_ORDER_VALUES = [
    "Rx Ry Rz",
    "xyz",
    "Rx Rz Ry",
    "xzy",
    "Ry Rx Rz",
    "yxz",
    "Ry Rz Rx",
    "yzx",
    "Rz Rx Ry",
    "zxy",
    "Rz Ry Rx",
    "zyx",
]
_COMP_PARENT_XFORM_SOURCE_VALUES = [
    "From Parent Object (Hierarchy)",
    "hierarchy",
    "Specify Parent Object",
    "specify",
    "World Origin",
    "worldorigin",
]
_COMP_FORWARD_DIRECTION_VALUES = [
    "+X",
    "posx",
    "-X",
    "negx",
    "+Y",
    "posy",
    "-Y",
    "negy",
    "+Z",
    "posz",
    "-Z",
    "negz",
]
_COMP_LOOK_AT_UP_VALUES = [
    "Don't use up vector",
    "off",
    "Use up vector",
    "on",
    "Use quaternions",
    "quat",
    "Use Roll",
    "roll",
]
_GEOMETRY_INSTANCE_COUNT_MODE_VALUES = [
    "Manual",
    "manual",
    "Instance OP(s) Length",
    "oplength",
]
_GEOMETRY_INSTANCE_FIRST_ROW_VALUES = [
    "Ignored",
    "ignored",
    "Names",
    "names",
    "Values",
    "values",
]
_TOP_EXTEND_VALUES = [
    "Hold",
    "hold",
    "Zero",
    "zero",
    "Repeat",
    "repeat",
    "Mirror",
    "mirror",
]
_TOP_OUTPUT_RESOLUTION_VALUES = [
    "Use Input",
    "useinput",
    "Eighth",
    "eighth",
    "Quarter",
    "quarter",
    "Half",
    "half",
    "2X",
    "2x",
    "4X",
    "4x",
    "8X",
    "8x",
    "Fit Resolution",
    "fit",
    "Limit Resolution",
    "limit",
    "Custom Resolution",
    "custom",
]
_LEVEL_CLAMP_INPUT_VALUES = ["Automatic", "automatic", "Clamp [0-1]", "clamp", "Unclamped", "unclamped"]
_COMPOSITE_OPERAND_VALUES = [
    "Add",
    "add",
    "Atop",
    "atop",
    "Average",
    "average",
    "Brightest",
    "brightest",
    "Burn Color",
    "burncolor",
    "Burn Linear",
    "burnlinear",
    "Chroma Difference",
    "chromadifference",
    "Color",
    "color",
    "Darker Color",
    "darkercolor",
    "Difference",
    "difference",
    "Dimmest",
    "dimmest",
    "Divide",
    "divide",
    "Dodge",
    "dodge",
    "Exclude",
    "exclude",
    "Freeze",
    "freeze",
    "Glow",
    "glow",
    "Hard Light",
    "hardlight",
    "Hard Mix",
    "hardmix",
    "Heat",
    "heat",
    "Hue",
    "hue",
    "Inside",
    "inside",
    "Inside Luminance",
    "insideluminance",
    "Inverse",
    "inverse",
    "Lighter Color",
    "lightercolor",
    "Luminance Difference",
    "luminancedifference",
    "Maximum",
    "maximum",
    "Minimum",
    "minimum",
    "Multiply",
    "multiply",
    "Negate",
    "negate",
    "Outside",
    "outside",
    "Outside Luminance",
    "outsideluminance",
    "Over",
    "over",
    "Overlay",
    "overlay",
    "Pinlight",
    "pinlight",
    "Reflect",
    "reflect",
    "Screen",
    "screen",
    "Soft Light",
    "softlight",
    "Linear Light",
    "linearlight",
    "Stencil Luminance",
    "stencilluminance",
    "Subtract",
    "subtract",
    "Subtractive",
    "subtractive",
    "Under",
    "under",
    "Vivid Light",
    "vividlight",
    "Xor",
    "xor",
    "Y Film",
    "yfilm",
    "Z Film",
    "zfilm",
]
_COMPOSITE_SIZE_VALUES = ["Input 1", "input1", "Input 2", "input2"]
_COMPOSITE_PREFIT_VALUES = [
    "Fill",
    "fill",
    "Fit Horizontal",
    "fithorz",
    "Fit Vertical",
    "fitvert",
    "Fit Best",
    "fitbest",
    "Fit Outside",
    "fitoutside",
    "Native Resolution",
    "nativeres",
]
_COMPOSITE_JUSTIFY_H_VALUES = ["Left", "left", "Center", "center", "Right", "right"]
_COMPOSITE_JUSTIFY_V_VALUES = ["Bottom", "bottom", "Center", "center", "Top", "top"]
_RENDER_SIMPLE_MATERIAL_SOURCE_VALUES = ["Internal Phong", "internalphong", "MAT Node", "matnode"]
_RENDER_MULTI_CAMERA_HINT_VALUES = [
    "Automatic",
    "automatic",
    "Off (One Pass Per Camera)",
    "off",
    "X-Offset Stereo Cameras",
    "stereocameras",
]
_RENDER_ANTI_ALIAS_VALUES = [
    "1x (Off)",
    "aa1",
    "2x",
    "aa2",
    "4x",
    "aa4",
    "8x (Medium)",
    "aa8mid",
    "8x (High)",
    "aa8high",
    "16x (Low)",
    "aa16low",
    "16x (Medium)",
    "aa16mid",
    "16x (High)",
    "aa16high",
    "32x",
    "aa32",
]
_RENDER_MODE_VALUES = [
    "2D",
    "render2d",
    "Cube Map",
    "cubemap",
    "Fish-Eye (180)",
    "fisheye180",
    "Dual Paraboloid",
    "dualparaboloid",
    "UV Unwrap",
    "uvunwrap",
    "Cube Map (Omnidirectional Stereo)",
    "cubemapods",
]
_RENDER_TRANSPARENCY_VALUES = [
    "Sorted Draw with Blending",
    "sortedblending",
    "Order Independent Transparency",
    "orderind",
    "Alpha-to-Coverage",
    "alphatocoverage",
]
_RENDER_DEPTH_FORMAT_VALUES = [
    "24-Bit Fixed-Point",
    "fixed24",
    "32-Bit Floating-Point",
    "float32",
]
_RENDER_CULL_FACE_VALUES = [
    "Neither",
    "neither",
    "Back Faces",
    "backfaces",
    "Front Faces",
    "frontfaces",
    "Both Faces",
    "bothfaces",
]
_GLSL_MAT_LIGHTING_SPACE_VALUES = [
    "World Space",
    "worldspace",
    "Camera Space (Legacy 088 shaders)",
    "cameraspace",
]
_GLSL_MAT_INPUT_PRIMITIVE_VALUES = [
    "Points",
    "points",
    "Lines",
    "lines",
    "Triangles",
    "triangles",
]
_GLSL_MAT_OUTPUT_PRIMITIVE_VALUES = [
    "Points",
    "points",
    "Line Strip",
    "linestrip",
    "Triangle Strip",
    "tristrip",
]
_GLSL_MAT_ATTR_TYPE_VALUES = [
    "float",
    "vec2",
    "vec3",
    "vec4",
    "double",
    "dvec2",
    "dvec3",
    "dvec4",
    "int",
    "ivec2",
    "ivec3",
    "ivec4",
    "uint",
    "uvec2",
    "uvec3",
    "uvec4",
]
_GLSL_MAT_DEFORM_DATA_VALUES = [
    "From a SOP",
    "sop",
    "From another MAT",
    "mat",
    "From a DeformIn MAT",
    "deformin",
]
_GLSL_MAT_BLEND_OP_VALUES = [
    "Add",
    "add",
    "Subtract",
    "subtract",
    "Reverse Subtract",
    "revsubtract",
    "Minimum",
    "minimum",
    "Maximum",
    "maximum",
]
_GLSL_MAT_BLEND_FACTOR_VALUES = [
    "Zero",
    "zero",
    "Dest Color",
    "dcol",
    "One Minus Dest Color",
    "omdcol",
    "Source Alpha",
    "sa",
    "One Minus Source Alpha",
    "omsa",
    "Dest Alpha",
    "da",
    "One Minus Dest Alpha",
    "omda",
    "Source Alpha Saturate",
    "sas",
    "One",
    "one",
    "Constant Color",
    "constantcol",
    "One Minus Constant Color",
    "omconstantcol",
    "Constant Alpha",
    "constanta",
    "One Minus Constant Alpha",
    "omconstanta",
    "Src Color",
    "scol",
    "One Minus Src Color",
    "omscol",
]
_GLSL_MAT_POINT_COLOR_PREMULT_VALUES = [
    "Already Pre-Multiplied By Alpha",
    "alreadypremult",
    "Pre-Multiply By Alpha in Shader",
    "premultinshader",
]
_GLSL_MAT_DEPTH_FUNC_VALUES = [
    "Less Than",
    "less",
    "Less Than or Equal",
    "lessorequal",
    "Equal",
    "equal",
    "Greater Than",
    "greater",
    "Greater Than or Equal",
    "greaterorequal",
    "Not Equal",
    "notequal",
    "Always",
    "always",
]
_GLSL_MAT_ALPHA_FUNC_VALUES = [
    "Less Than",
    "less",
    "Less Than or Equal",
    "lessorequal",
    "Greater Than",
    "greater",
    "Greater Than or Equal",
    "greaterorequal",
]
_GLSL_MAT_WIREFRAME_VALUES = [
    "Off",
    "off",
    "OpenGL Tesselated Wire Frame",
    "tesselated",
    "Topology Wire Frame",
    "topology",
]
_GLSL_MAT_CULL_FACE_VALUES = [
    "Use Render Setting",
    "userender",
    "Neither",
    "neither",
    "Back Faces",
    "backfaces",
    "Front Faces",
    "frontfaces",
    "Both Faces",
    "bothfaces",
]
_SLIDER_COMP_TYPES = [
    "Slider U",
    "slideru",
    "Slider V",
    "sliderv",
    "Slider UV",
    "slideruv",
]
_BUTTON_COMP_TYPES = [
    "Momentary",
    "momentary",
    "Momentary Up",
    "momentaryup",
    "Toggle Down",
    "toggledown",
    "Toggle Up",
    "toggleup",
    "Toggle Up Anywhere",
    "toggleupany",
    "Radio Down",
    "radiodown",
    "Radio Up",
    "radioup",
    "Radio Up Anywhere",
    "radionupany",
    "Exclusive Down",
    "exclusivedown",
    "Exclusive Up",
    "exclusiveup",
    "Exclusive Up Anywhere",
    "exclusivenupany",
]
_BUTTON_SCALE_TO_FIT_VALUES = [
    "Never",
    "never",
    "Always",
    "always",
    "Only when Too Large",
    "onlyshrink",
]
_COMP_REL_PATH_VALUES = [
    "Use Parent's Behavior",
    "inherit",
    "Relative to Project File (.toe)",
    "project",
    "Relative to External COMP File (.tox)",
    "externaltox",
]
_PARAMETER_COMP_COMBINE_SCOPES = ["Any (Or)", "any", "All (And)", "all"]
_OSC_IN_PROTOCOL_VALUES = [
    "Messaging (UDP)",
    "msging",
    "Multi-Cast Messaging (UDP)",
    "multicastmsging",
    "Reliable Messaging (UDT Library)",
    "reliablemsging",
]
_UDP_IN_PROTOCOL_VALUES = [
    "Messaging (UDP)",
    "msging",
    "Multi-Cast Messaging (UDP)",
    "multicastmsging",
]
_UDP_IN_FORMAT_VALUES = _SERIAL_DAT_FORMAT_VALUES
_WEB_CLIENT_REQUEST_METHOD_VALUES = [
    "GET",
    "get",
    "POST",
    "post",
    "PUT",
    "put",
    "DELETE",
    "delete",
    "HEAD",
    "head",
    "OPTIONS",
    "options",
    "PATCH",
    "patch",
]
_WEB_CLIENT_AUTH_TYPE_VALUES = [
    "None",
    "none",
    "Basic",
    "basic",
    "Digest",
    "digest",
    "OAuth1",
    "oauth1",
    "OAuth2",
    "oauth2",
]
_WEB_CLIENT_SECRET_PARAMS = {"pw", "appsecret", "oauthtoken", "oauthsecret", "token"}
_GLSL_ADVANCED_POP_CAPACITY_PARAMS: dict[str, tuple[str, str]] = {
    "maxpoints": ("Maximum Points", "points"),
    "maxtriangles": ("Maximum Triangles", "primitives"),
    "maxquads": ("Maximum Quads", "primitives"),
    "maxlinestrips": ("Maximum Line Strips", "primitives"),
    "maxlsverts": ("Maximum Line Strip Vertices", "vertices"),
    "maxlines": ("Maximum Lines", "primitives"),
    "maxpointprims": ("Maximum Point Primitives", "primitives"),
}
_GLSL_POP_THREAD_INT_PARAMS: dict[str, tuple[str, str | None, float, str, str, str | None]] = {
    "threadsinput": ("Thread Count Input", None, 0.0, "input_index_for_thread_count_source", "medium", None),
    "numelems": (
        "Manual Number of Elements",
        "elements",
        1.0,
        "small_bounded_manual_element_count",
        "high",
        "warn_large_pop_capacity",
    ),
    "workgroupsizex": ("Workgroup Size X", "threads", 1.0, "small_manual_workgroup_size", "high", None),
    "workgroupsizey": ("Workgroup Size Y", "threads", 1.0, "small_manual_workgroup_size", "high", None),
    "workgroupsizez": ("Workgroup Size Z", "threads", 1.0, "small_manual_workgroup_size", "high", None),
    "dispatchsizex": ("Dispatch Size X", "groups", 1.0, "small_manual_dispatch_size", "high", None),
    "dispatchsizey": ("Dispatch Size Y", "groups", 1.0, "small_manual_dispatch_size", "high", None),
    "dispatchsizez": ("Dispatch Size Z", "groups", 1.0, "small_manual_dispatch_size", "high", None),
    "npasses": ("Shader Passes", "passes", 1.0, "single_pass_unless_explicitly_required", "high", None),
}
_GLSL_MULTI_DAT_PARAMS: dict[str, str] = {
    "predat": "Preprocess Directives DAT",
    "vertexdat": "Vertex Shader DAT",
    "pixeldat": "Pixel Shader DAT",
    "computedat": "Compute Shader DAT",
}
_GLSL_MULTI_INT_PARAMS: dict[str, tuple[str, str | None, float, str, str]] = {
    "dispatchsizex": ("Dispatch Size X", "groups", 1.0, "small_manual_dispatch_size", "high"),
    "dispatchsizey": ("Dispatch Size Y", "groups", 1.0, "small_manual_dispatch_size", "high"),
    "dispatchsizez": ("Dispatch Size Z", "groups", 1.0, "small_manual_dispatch_size", "high"),
    "customdepth": ("Custom Depth", "slices", 1.0, "bounded_custom_texture_depth", "high"),
    "nval": ("N Value", "inputs_per_slice", 1.0, "positive_inputs_per_slice", "medium"),
    "numcolorbufs": (
        "Number of Color Buffers",
        "buffers",
        1.0,
        "single_buffer_unless_multi_output_is_required",
        "high",
    ),
    "resolutionw": ("Resolution Width", "pixels", 1.0, "bounded_custom_output_width", "high"),
    "resolutionh": ("Resolution Height", "pixels", 1.0, "bounded_custom_output_height", "high"),
    "npasses": ("Passes", "passes", 1.0, "single_pass_unless_feedback_passes_are_explicit", "high"),
}
_GLSL_TOP_INT_PARAMS: dict[str, tuple[str, str | None, float, str, str]] = {
    "dispatchsizex": ("Dispatch Size X", "groups", 1.0, "small_manual_dispatch_size", "high"),
    "dispatchsizey": ("Dispatch Size Y", "groups", 1.0, "small_manual_dispatch_size", "high"),
    "dispatchsizez": ("Dispatch Size Z", "groups", 1.0, "small_manual_dispatch_size", "high"),
    "customdepth": ("Custom Depth", "slices", 1.0, "bounded_custom_texture_depth", "high"),
    "nval": ("N Value", "inputs_per_slice", 1.0, "positive_inputs_per_slice", "medium"),
    "numcolorbufs": (
        "Number of Color Buffers",
        "buffers",
        1.0,
        "single_buffer_unless_multi_output_is_required",
        "high",
    ),
    "npasses": ("Passes", "passes", 1.0, "single_pass_unless_feedback_passes_are_explicit", "high"),
}


def load_param_semantics_registry() -> list[ParamSemantics]:
    """Return the Phase 2 seed registry for high-risk/typed parameters."""
    return [
        *_level_top_semantics(),
        *_feedback_top_semantics(),
        *_composite_top_semantics(),
        *_edge_top_semantics(),
        *_blur_top_semantics(),
        *_switch_top_semantics(),
        *_table_dat_semantics(),
        *_select_dat_semantics(),
        *_movie_file_in_top_semantics(),
        *_video_device_in_top_semantics(),
        *_kinect_azure_top_semantics(),
        *_noise_top_semantics(),
        ParamSemantics(
            op_type="transformTOP",
            name="xord",
            label="Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_predictable_image_motion",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="transformTOP",
            name="t",
            label="Translate",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="two_axis_image_offset",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="transformTOP",
            name="rotate",
            label="Rotate",
            value_kind="float",
            unit="degrees",
            default_strategy="bounded_image_rotation",
            cook_risk="medium",
            validation_rule="numeric_rotation",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="transformTOP",
            name="s",
            label="Scale",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="two_axis_image_scale",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="transformTOP",
            name="p",
            label="Pivot",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="two_axis_transform_pivot",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="transformTOP",
            name="bgcolor",
            label="Background Color",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="transparent_black_background",
            cook_risk="low",
            validation_rule="rgba_tuple",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="transformTOP",
            name="extend",
            label="Extend",
            value_kind="enum",
            enum_values=_TOP_EXTEND_VALUES,
            default_strategy="hold_or_repeat_for_feedback_tiling",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_TRANSFORM_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="cacheTOP",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="capture_only_when_cache_history_is_required",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_CACHE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="cacheTOP",
            name="cachesize",
            label="Cache Size",
            value_kind="int",
            default_strategy="small_bounded_gpu_image_history",
            cook_risk="high",
            validation_rule="integer_cache_size",
            official_source=_CACHE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="cacheTOP",
            name="step",
            label="Step Size",
            value_kind="int",
            default_strategy="one_frame_step_for_realtime_history",
            cook_risk="medium",
            validation_rule="integer_step_size",
            official_source=_CACHE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="cacheTOP",
            name="outputindex",
            label="Output Index",
            value_kind="float",
            default_strategy="negative_index_for_frame_delay",
            cook_risk="medium",
            validation_rule="numeric_cache_output_index",
            official_source=_CACHE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="cacheTOP",
            name="interp",
            label="Interpolate Frames",
            value_kind="bool",
            default_strategy="enable_only_for_fractional_output_index",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_CACHE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="cacheTOP",
            name="reset",
            label="Reset",
            value_kind="bool",
            default_strategy="leave_off_unless_explicit_cache_clear_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_CACHE_TOP_DOCS,
        ),
        *_render_top_semantics(),
        *_geometry_comp_semantics(),
        *_camera_comp_semantics(),
        *_light_comp_semantics(),
        *_glsl_top_semantics(),
        *_glsl_multi_top_semantics(),
        ParamSemantics(
            op_type="glslPOP",
            name="computedat",
            label="Compute Shader DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_POP_DOCS,
        ),
        ParamSemantics(
            op_type="glslPOP",
            name="attrclass",
            label="Attribute Class",
            value_kind="enum",
            enum_values=_POP_ATTRIBUTE_CLASS_VALUES,
            default_strategy="selected_attribute_class_for_generated_pop_shader",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_POP_DOCS,
        ),
        ParamSemantics(
            op_type="glslPOP",
            name="numthreadsmode",
            label="Number of Threads Mode",
            value_kind="enum",
            enum_values=_GLSL_POP_THREAD_MODE_VALUES,
            default_strategy="derive_thread_count_from_input_unless_explicitly_bounded",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_POP_DOCS,
        ),
        ParamSemantics(
            op_type="glslPOP",
            name="numelemspop",
            label="Number of Elements POP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="created_pop_source_for_attribute_count",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_POP_DOCS,
        ),
        ParamSemantics(
            op_type="glslPOP",
            name="numelemsclass",
            label="Number of Elements Attribute Class",
            value_kind="enum",
            enum_values=_POP_ATTRIBUTE_CLASS_VALUES,
            default_strategy="match_selected_attribute_class",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_POP_DOCS,
        ),
        ParamSemantics(
            op_type="glslPOP",
            name="initoutputattrs",
            label="Initialize Output Attributes",
            value_kind="bool",
            default_strategy="enabled_when_shader_reads_or_partially_writes_outputs",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_GLSL_POP_DOCS,
        ),
        ParamSemantics(
            op_type="glslPOP",
            name="prevpassoutput",
            label="Copy Previous Pass Output to Input",
            value_kind="bool",
            default_strategy="disabled_unless_multi_pass_feedback_is_required",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_POP_DOCS,
        ),
        *_glsl_pop_thread_int_semantics(),
        ParamSemantics(
            op_type="glsladvancedPOP",
            name="computedat",
            label="Compute Shader DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_ADVANCED_POP_DOCS,
        ),
        *_glsl_advanced_pop_capacity_semantics(),
        *_glsl_mat_semantics(),
        *_glsl_comp_semantics(),
        *_pbr_mat_semantics(),
        *_phong_mat_semantics(),
        *_render_simple_top_semantics(),
        *_circle_pop_semantics(),
        *_noise_pop_semantics(),
        *_math_mix_pop_semantics(),
        *_attribute_combine_pop_semantics(),
        ParamSemantics(
            op_type="gridSOP",
            name="rows",
            label="Rows",
            value_kind="int",
            valid_range=(2.0, 10000.0),
            default_strategy="moderate_terrain_grid_resolution",
            cook_risk="medium",
            validation_rule="positive_grid_resolution",
            official_source=_GRID_SOP_DOCS,
        ),
        ParamSemantics(
            op_type="gridSOP",
            name="cols",
            label="Columns",
            value_kind="int",
            valid_range=(2.0, 10000.0),
            default_strategy="moderate_terrain_grid_resolution",
            cook_risk="medium",
            validation_rule="positive_grid_resolution",
            official_source=_GRID_SOP_DOCS,
        ),
        ParamSemantics(
            op_type="gridSOP",
            name="sizex",
            label="Size X",
            value_kind="float",
            valid_range=(0.0, 10000.0),
            default_strategy="bounded_terrain_width",
            cook_risk="medium",
            validation_rule="non_negative_sop_size",
            official_source=_GRID_SOP_DOCS,
        ),
        ParamSemantics(
            op_type="gridSOP",
            name="sizey",
            label="Size Y",
            value_kind="float",
            valid_range=(0.0, 10000.0),
            default_strategy="bounded_terrain_height",
            cook_risk="medium",
            validation_rule="non_negative_sop_size",
            official_source=_GRID_SOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseSOP",
            name="amp",
            label="Amplitude",
            value_kind="float",
            valid_range=(0.0, 10000.0),
            default_strategy="bounded_surface_displacement",
            cook_risk="medium",
            validation_rule="non_negative_displacement_amplitude",
            official_source=_NOISE_SOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="transformSOP",
                name=name,
                label=label,
                value_kind="float",
                valid_range=(-10000.0, 10000.0),
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule=validation_rule,
                official_source=_TRANSFORM_SOP_DOCS,
            )
            for name, label, default_strategy, validation_rule in (
                ("tx", "Translate X", "centered_sop_translation", "bounded_sop_translation"),
                ("ty", "Translate Y", "centered_sop_translation", "bounded_sop_translation"),
                ("tz", "Translate Z", "centered_sop_translation", "bounded_sop_translation"),
                ("rx", "Rotate X", "neutral_sop_rotation", "bounded_sop_rotation"),
                ("ry", "Rotate Y", "neutral_sop_rotation", "bounded_sop_rotation"),
                ("rz", "Rotate Z", "neutral_sop_rotation", "bounded_sop_rotation"),
                ("sx", "Scale X", "unit_sop_scale", "bounded_sop_scale"),
                ("sy", "Scale Y", "unit_sop_scale", "bounded_sop_scale"),
                ("sz", "Scale Z", "unit_sop_scale", "bounded_sop_scale"),
            )
        ],
        ParamSemantics(
            op_type="ndiinTOP",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enabled_explicit_network_input",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_NDI_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="clone",
            label="Clone Master",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="explicit_clone_master_only_when_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="opviewer",
            label="Operator Viewer",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="stable_internal_viewer_target",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="enablecloning",
            label="Enable Cloning",
            value_kind="bool",
            default_strategy="keep_disabled_unless_clone_master_is_defined",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="loadondemand",
            label="Load on Demand",
            value_kind="bool",
            default_strategy="off_for_generated_control_shells",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="parentshortcut",
            label="Parent Shortcut",
            value_kind="string",
            default_strategy="explicit_parent_shortcut_for_component_shells",
            cook_risk="low",
            validation_rule="shortcut_name_scope",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="opshortcut",
            label="Global OP Shortcut",
            value_kind="string",
            default_strategy="avoid_global_shortcuts_unless_requested",
            cook_risk="medium",
            validation_rule="shortcut_name_scope",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="iop0shortcut",
            label="Internal OP Shortcut",
            value_kind="string",
            default_strategy="explicit_internal_shortcut_for_generated_shells",
            cook_risk="low",
            validation_rule="shortcut_name_scope",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="iop0op",
            label="Internal OP",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="created_internal_operator_reference",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="enablecloningpulse",
            label="Enable Cloning Pulse",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_clone_refresh",
            cook_risk="high",
            validation_rule="pulse_action",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="enableexternaltox",
            label="Enable External .tox",
            value_kind="bool",
            default_strategy="off_for_local_generated_component_shells",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="enableexternaltoxpulse",
            label="Enable External .tox Pulse",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_external_tox_reload",
            cook_risk="high",
            validation_rule="pulse_action",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="externaltox",
            label="External .tox Path",
            value_kind="path",
            default_strategy="explicit_external_tox_path_only_when_requested",
            cook_risk="high",
            validation_rule="non_empty_file_path_when_set",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="reloadcustom",
            label="Reload Custom Parameters",
            value_kind="bool",
            default_strategy="preserve_generated_custom_parameter_values",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="reloadbuiltin",
            label="Reload Built-In Parameters",
            value_kind="bool",
            default_strategy="preserve_generated_builtin_parameter_values",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="savebackup",
            label="Save Backup of External",
            value_kind="bool",
            default_strategy="save_backup_only_for_external_tox_workflows",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="subcompname",
            label="Sub-Component to Load",
            value_kind="string",
            default_strategy="blank_for_top_level_external_tox_component",
            cook_risk="medium",
            validation_rule="component_name_scope",
            official_source=_BASE_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="baseCOMP",
            name="relpath",
            label="Relative File Path Behavior",
            value_kind="enum",
            enum_values=_COMP_REL_PATH_VALUES,
            default_strategy="inherit_parent_relative_path_behavior",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_BASE_COMP_DOCS,
        ),
        *_panel_component_layout_semantics("containerCOMP", _CONTAINER_COMP_DOCS),
        *_panel_component_interaction_semantics("containerCOMP", _CONTAINER_COMP_DOCS),
        ParamSemantics(
            op_type="containerCOMP",
            name="top",
            label="Background TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_background_top_if_visual_panel_surface_is_needed",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_CONTAINER_COMP_DOCS,
        ),
        *_panel_component_layout_semantics("sliderCOMP", _SLIDER_COMP_DOCS),
        *_panel_component_interaction_semantics("sliderCOMP", _SLIDER_COMP_DOCS),
        ParamSemantics(
            op_type="sliderCOMP",
            name="slidertype",
            label="Slider Type",
            value_kind="enum",
            enum_values=_SLIDER_COMP_TYPES,
            default_strategy="slideru_for_single_axis_control",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_SLIDER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="sliderCOMP",
            name="value0",
            label="Value",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="normalized_panel_control_default",
            cook_risk="low",
            validation_rule="normalized_slider_value",
            official_source=_SLIDER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="sliderCOMP",
            name="value1",
            label="Value 1",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="normalized_panel_control_default",
            cook_risk="low",
            validation_rule="normalized_slider_value",
            official_source=_SLIDER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="sliderCOMP",
            name="clampul",
            label="Clamp U Low",
            value_kind="bool",
            default_strategy="enabled_for_bounded_user_controls",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_SLIDER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="sliderCOMP",
            name="clampuh",
            label="Clamp U High",
            value_kind="bool",
            default_strategy="enabled_for_bounded_user_controls",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_SLIDER_COMP_DOCS,
        ),
        *_panel_component_layout_semantics("buttonCOMP", _BUTTON_COMP_DOCS),
        *_panel_component_interaction_semantics("buttonCOMP", _BUTTON_COMP_DOCS),
        ParamSemantics(
            op_type="buttonCOMP",
            name="buttontype",
            label="Button Type",
            value_kind="enum",
            enum_values=_BUTTON_COMP_TYPES,
            default_strategy="toggle_down_for_latching_controls",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_BUTTON_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="buttonCOMP",
            name="value0",
            label="Value",
            value_kind="bool",
            default_strategy="off_until_user_interaction_or_explicit_default",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_BUTTON_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="buttonCOMP",
            name="buttongroupdat",
            label="Button Group DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_table_dat_for_radio_button_groups",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_BUTTON_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="buttonCOMP",
            name="scaletofit",
            label="Scale Text to Fit",
            value_kind="enum",
            enum_values=_BUTTON_SCALE_TO_FIT_VALUES,
            default_strategy="only_shrink_for_readable_control_labels",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_BUTTON_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="component",
            label="Panel Component",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_panel_comp",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="select",
            label="Select",
            value_kind="string",
            default_strategy="explicit_panel_value_scope_or_all_values",
            cook_risk="low",
            validation_rule="panel_value_scope",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="rename",
            label="Rename",
            value_kind="string",
            default_strategy="explicit_panel_channel_renames_when_needed",
            cook_risk="low",
            validation_rule="channel_rename_scope",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="queue",
            label="Queue Overlapping Events",
            value_kind="bool",
            default_strategy="enable_when_instantaneous_panel_events_matter",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="queuesize",
            label="Queue Size",
            value_kind="int",
            valid_range=(1.0, 10000.0),
            default_strategy="small_bounded_panel_event_queue",
            cook_risk="medium",
            validation_rule="integer_event_queue_size",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="timeslice",
            label="Time Slice",
            value_kind="bool",
            default_strategy="match_control_readback_profile",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="scope",
            label="Scope",
            value_kind="string",
            default_strategy="explicit_export_channel_scope",
            cook_risk="low",
            validation_rule="channel_scope",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="srselect",
            label="Sample Rate Match",
            value_kind="enum",
            enum_values=_CHOP_SAMPLE_RATE_MATCH_VALUES,
            default_strategy="resample_at_first_input_rate_for_control_channels",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="exportmethod",
            label="Export Method",
            value_kind="enum",
            enum_values=_CHOP_EXPORT_METHOD_VALUES,
            default_strategy="dat_table_by_name_for_generated_exports",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="autoexportroot",
            label="Export Root",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_export_root_for_path_parameter_channels",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source=_PANEL_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="panelCHOP",
            name="exporttable",
            label="Export Table",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_export_table_dat_if_exports_are_used",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_PANEL_CHOP_DOCS,
        ),
        *_panel_component_layout_semantics("parameterCOMP", _PARAMETER_COMP_DOCS),
        *_panel_component_interaction_semantics("parameterCOMP", _PARAMETER_COMP_DOCS),
        ParamSemantics(
            op_type="parameterCOMP",
            name="top",
            label="Background TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_background_top_if_parameter_panel_surface_is_needed",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="op",
            label="Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_parameter_target_operator",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="header",
            label="Header",
            value_kind="bool",
            default_strategy="hide_for_compact_generated_panels",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="pagenames",
            label="Page Names",
            value_kind="bool",
            default_strategy="show_page_tabs_for_browsable_parameter_panels",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="labels",
            label="Labels",
            value_kind="bool",
            default_strategy="show_labels_for_generated_parameter_panels",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="separators",
            label="Separators",
            value_kind="bool",
            default_strategy="show_separators_for_readable_parameter_groups",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="inputeditor",
            label="Input Editor",
            value_kind="bool",
            default_strategy="hide_unless_multi_input_parameter_editor_is_needed",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="builtin",
            label="Built-In",
            value_kind="bool",
            default_strategy="off_when_exposing_only_generated_custom_controls",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="custom",
            label="Custom",
            value_kind="bool",
            default_strategy="on_for_custom_parameter_control_panels",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="combinescopes",
            label="Combine Scopes",
            value_kind="enum",
            enum_values=_PARAMETER_COMP_COMBINE_SCOPES,
            default_strategy="any_scope_for_explicit_generated_parameter_lists",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="pagescope",
            label="Page Scope",
            value_kind="string",
            default_strategy="explicit_page_scope_or_all_pages",
            cook_risk="low",
            validation_rule="pattern_scope",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="parscope",
            label="Parameter Scope",
            value_kind="string",
            default_strategy="explicit_parameter_scope_or_all_parameters",
            cook_risk="low",
            validation_rule="pattern_scope",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="parameterCOMP",
            name="allowexpand",
            label="Allow Expansion",
            value_kind="bool",
            default_strategy="allow_expansion_for_inspectable_parameter_panels",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_PARAMETER_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="infoCHOP",
            name="op",
            label="Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="stable_output_or_debug_target",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source="https://docs.derivative.ca/Info_CHOP",
        ),
        ParamSemantics(
            op_type="infoCHOP",
            name="passive",
            label="Passive",
            value_kind="bool",
            default_strategy="passive_debug_readback",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source="https://docs.derivative.ca/Info_CHOP",
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_debug_error_log",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_ERROR_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat_if_callbacks_are_needed",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_ERROR_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_CALLBACK_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="callbacks_dat_for_error_callbacks",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_ERROR_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_ERROR_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="source",
            label="Source",
            value_kind="path",
            default_strategy="explicit_debug_scope",
            cook_risk="medium",
            validation_rule="non_empty_path",
            official_source=_ERROR_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="clamp",
            label="Clamp Output",
            value_kind="bool",
            default_strategy="bounded_debug_log_output",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_ERROR_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="errorDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_debug_log_fifo",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_ERROR_DAT_DOCS,
        ),
        *_lfo_chop_semantics(),
        *_wave_chop_semantics(),
        *_noise_chop_semantics(),
        *_audio_file_in_chop_semantics(),
        *_audio_file_out_chop_semantics(),
        *_audio_device_in_chop_semantics(),
        *_audio_device_out_chop_semantics(),
        *_midi_in_chop_semantics(),
        *_analyze_chop_semantics(),
        *_math_chop_semantics(),
        *_filter_chop_semantics(),
        ParamSemantics(
            op_type="lagCHOP",
            name="lagmethod",
            label="Lag Method",
            value_kind="enum",
            enum_values=_LAG_CHOP_METHODS,
            default_strategy="lag_value_for_scalar_controls",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lagCHOP",
            name="lag",
            label="Lag",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="symmetric_up_down_lag",
            cook_risk="medium",
            validation_rule="two_value_up_down_tuple",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lagCHOP",
            name="lagunit",
            label="Lag Unit",
            value_kind="enum",
            enum_values=_CHOP_UNIT_MENU_VALUES,
            default_strategy="seconds_for_control_smoothing",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lagCHOP",
            name="overshoot",
            label="Overshoot",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="symmetric_up_down_overshoot",
            cook_risk="medium",
            validation_rule="two_value_up_down_tuple",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lagCHOP",
            name="overshootunit",
            label="Overshoot Unit",
            value_kind="enum",
            enum_values=_CHOP_UNIT_MENU_VALUES,
            default_strategy="match_lag_unit",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lagCHOP",
            name="slope",
            label="Max Slope",
            value_kind="tuple",
            tuple_size=2,
            unit="value_per_unit",
            default_strategy="symmetric_rise_fall_velocity_limit",
            cook_risk="medium",
            validation_rule="two_value_up_down_tuple",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lagCHOP",
            name="accel",
            label="Max Acceleration",
            value_kind="tuple",
            tuple_size=2,
            unit="value_per_unit_squared",
            default_strategy="symmetric_rise_fall_acceleration_limit",
            cook_risk="medium",
            validation_rule="two_value_up_down_tuple",
            official_source=_LAG_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="datexecuteDAT",
            name="dat",
            label="Monitored DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_table_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_DAT_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="datexecuteDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_when_callback_source_is_validated",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_DAT_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="datexecuteDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="this_node_for_local_callback_context",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_DAT_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="datexecuteDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_DAT_EXECUTE_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="datexecuteDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="prefer_tablechange_for_modern_dat_execute_callbacks",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_DAT_EXECUTE_DOCS,
            )
            for name, label in _DAT_EXECUTE_TRIGGER_PARAMS
        ],
        ParamSemantics(
            op_type="datexecuteDAT",
            name="execute",
            label="Execute",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_EXECUTE_VALUES,
            default_strategy="end_of_frame_for_callback_coalescing",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_DAT_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="chopexecuteDAT",
            name="chop",
            label="Watched CHOP",
            value_kind="op_ref",
            expected_family="CHOP",
            default_strategy="created_control_chop",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_CHOP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="chopexecuteDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_when_callback_source_is_validated",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_CHOP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="chopexecuteDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="this_node_for_local_callback_context",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_CHOP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="chopexecuteDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_CHOP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="chopexecuteDAT",
            name="channel",
            label="Channel",
            value_kind="string",
            default_strategy="explicit_channel_filter_or_all_channels",
            cook_risk="high",
            validation_rule="channel_name_scope",
            official_source=_CHOP_EXECUTE_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="chopexecuteDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_chop_execute_triggers",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_CHOP_EXECUTE_DOCS,
            )
            for name, label in _CHOP_EXECUTE_TRIGGER_PARAMS
        ],
        ParamSemantics(
            op_type="chopexecuteDAT",
            name="freq",
            label="While Off/On Frequency",
            value_kind="enum",
            enum_values=_CHOP_EXECUTE_FREQ_VALUES,
            default_strategy="once_per_frame_for_callback_safety",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_CHOP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_after_execute_callbacks_are_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="this_node_for_local_callback_context",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="executeDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_project_execute_events",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_EXECUTE_DAT_DOCS,
            )
            for name, label in _EXECUTE_DAT_TRIGGER_PARAMS
        ],
        ParamSemantics(
            op_type="executeDAT",
            name="edit",
            label="Edit",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_script_edit_request",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="file",
            label="File",
            value_kind="path",
            default_strategy="explicit_script_file_path_only_when_requested",
            cook_risk="high",
            validation_rule="non_empty_file_path_when_set",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="syncfile",
            label="Sync to File",
            value_kind="bool",
            default_strategy="off_unless_external_script_sync_is_requested",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="loadonstart",
            label="Load on Start",
            value_kind="bool",
            default_strategy="off_unless_external_script_reload_is_requested",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="loadonstartpulse",
            label="Load File",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_script_reload",
            cook_risk="high",
            validation_rule="pulse_action",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="write",
            label="Write on Toe Save",
            value_kind="bool",
            default_strategy="off_unless_external_script_write_is_requested",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="executeDAT",
            name="writepulse",
            label="Write File",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_script_write",
            cook_risk="high",
            validation_rule="pulse_action",
            official_source=_EXECUTE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="opexecuteDAT",
            name="op",
            label="Monitor OPs",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_operator_monitor_target",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_OP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="opexecuteDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="this_node_for_local_callback_context",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_OP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="opexecuteDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_OP_EXECUTE_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="opexecuteDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_op_execute_triggers",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_OP_EXECUTE_DOCS,
            )
            for name, label in _OP_EXECUTE_TRIGGER_PARAMS
        ],
        ParamSemantics(
            op_type="parameterexecuteDAT",
            name="op",
            label="OPs",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_parameter_owner_operator",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_PARAMETER_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="parameterexecuteDAT",
            name="pars",
            label="Parameters",
            value_kind="string",
            default_strategy="explicit_parameter_name_filter",
            cook_risk="high",
            validation_rule="non_empty_parameter_scope",
            official_source=_PARAMETER_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="parameterexecuteDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="this_node_for_local_callback_context",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_PARAMETER_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="parameterexecuteDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_PARAMETER_EXECUTE_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="parameterexecuteDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_parameter_execute_triggers",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_PARAMETER_EXECUTE_DOCS,
            )
            for name, label in _PARAMETER_EXECUTE_TRIGGER_PARAMS
        ],
        ParamSemantics(
            op_type="panelexecuteDAT",
            name="panels",
            label="Panels",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="explicit_panel_component_monitor_target",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_PANEL_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="panelexecuteDAT",
            name="panelvalue",
            label="Panel Value",
            value_kind="string",
            default_strategy="explicit_panel_value_filter",
            cook_risk="high",
            validation_rule="non_empty_panel_value_scope",
            official_source=_PANEL_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="panelexecuteDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="this_node_for_local_callback_context",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_PANEL_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="panelexecuteDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_PANEL_EXECUTE_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="panelexecuteDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_panel_execute_triggers",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_PANEL_EXECUTE_DOCS,
            )
            for name, label in _PANEL_EXECUTE_TRIGGER_PARAMS
        ],
        ParamSemantics(
            op_type="pargroupexecuteDAT",
            name="op",
            label="OPs",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_parameter_owner_operator",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_PARGROUP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="pargroupexecuteDAT",
            name="pars",
            label="Parameters",
            value_kind="string",
            default_strategy="explicit_parameter_name_filter",
            cook_risk="high",
            validation_rule="non_empty_parameter_scope",
            official_source=_PARGROUP_EXECUTE_DOCS,
        ),
        ParamSemantics(
            op_type="pargroupexecuteDAT",
            name="callbackmode",
            label="Callback Mode",
            value_kind="enum",
            enum_values=_PARGROUP_CALLBACK_MODE_VALUES,
            default_strategy="per_pargroup_change_for_single-change_callbacks",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_PARGROUP_EXECUTE_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="pargroupexecuteDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_pargroup_execute_triggers",
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_PARGROUP_EXECUTE_DOCS,
            )
            for name, label in _PARGROUP_EXECUTE_TRIGGER_PARAMS
        ],
        *_serial_dat_semantics(),
        ParamSemantics(
            op_type="oscinDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_network_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="protocol",
            label="Protocol",
            value_kind="enum",
            enum_values=_OSC_IN_PROTOCOL_VALUES,
            default_strategy="udp_messaging_default",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="address",
            label="Network Address",
            value_kind="string",
            default_strategy="explicit_multicast_or_udt_server_address",
            cook_risk="medium",
            validation_rule="network_address_scope",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="port",
            label="Port",
            value_kind="int",
            unit="port",
            valid_range=(1.0, 65535.0),
            default_strategy="explicit_osc_receive_port",
            cook_risk="medium",
            validation_rule="network_port_range",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="localaddress",
            label="Local Address",
            value_kind="string",
            default_strategy="explicit_local_nic_address_when_needed",
            cook_risk="medium",
            validation_rule="network_address_scope",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="shared",
            label="Shared Connection",
            value_kind="bool",
            default_strategy="share_only_when_matching_network_dats_are_declared",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="addscope",
            label="OSC Address Scope",
            value_kind="string",
            default_strategy="explicit_osc_address_filter_scope",
            cook_risk="medium",
            validation_rule="pattern_scope",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="typetag",
            label="Include Type Tag",
            value_kind="bool",
            default_strategy="enable_only_when_argument_type_diagnostics_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="splitbundle",
            label="Split Bundle into Messages",
            value_kind="bool",
            default_strategy="enable_only_for_per_message_bundle_rows",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="splitmessage",
            label="Split Message into Columns",
            value_kind="bool",
            default_strategy="enable_only_for_columnar_osc_tables",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="bundletimestamp",
            label="Bundle Timestamp Column",
            value_kind="bool",
            default_strategy="enable_only_when_bundle_time_column_is_needed",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_CALLBACK_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="callbacks_dat_for_received_message_callbacks",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="clamp",
            label="Clamp Output",
            value_kind="bool",
            default_strategy="bounded_osc_message_log_output",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_osc_message_log",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="clear",
            label="Clear Output",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_log_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="oscinDAT",
            name="bytes",
            label="Bytes Column",
            value_kind="bool",
            default_strategy="enable_only_when_raw_byte_diagnostics_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_OSC_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_websocket_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="netaddress",
            label="Network Address",
            value_kind="string",
            default_strategy="explicit_websocket_server_address",
            cook_risk="medium",
            validation_rule="network_address_scope",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="port",
            label="Network Port",
            value_kind="int",
            unit="port",
            valid_range=(1.0, 65535.0),
            default_strategy="explicit_websocket_port",
            cook_risk="medium",
            validation_rule="network_port_range",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="timeout",
            label="Connection Timeout",
            value_kind="int",
            unit="milliseconds",
            default_strategy="bounded_connection_timeout_ms",
            cook_risk="medium",
            validation_rule="integer_timeout_ms",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_CALLBACK_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="callbacks_dat_for_received_message_callbacks",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="clamp",
            label="Clamp Output",
            value_kind="bool",
            default_strategy="bounded_websocket_message_log_output",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_websocket_message_log",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="clear",
            label="Clear Output",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_log_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="websocketDAT",
            name="bytes",
            label="Bytes Column",
            value_kind="bool",
            default_strategy="enable_only_when_raw_byte_diagnostics_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_WEBSOCKET_DAT_DOCS,
        ),
        *_web_client_dat_semantics(),
        *_web_server_dat_semantics(),
        *_mqtt_client_dat_semantics(),
        *_udp_in_dat_semantics(),
    ]


def _web_client_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="webclientDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_http_client_use_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="reqmethod",
            label="Request Method",
            value_kind="enum",
            enum_values=_WEB_CLIENT_REQUEST_METHOD_VALUES,
            default_strategy="get_for_read_only_requests_unless_payload_method_is_declared",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="url",
            label="URL",
            value_kind="string",
            default_strategy="explicit_http_or_https_url",
            cook_risk="high",
            validation_rule="http_url_scope",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="uploadfile",
            label="Upload File",
            value_kind="path",
            default_strategy="explicit_upload_file_only_when_request_body_file_is_declared",
            cook_risk="high",
            validation_rule="non_empty_path_if_set",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="request",
            label="Request",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_http_request_execution",
            cook_risk="high",
            validation_rule="pulse_action",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="stop",
            label="Stop",
            value_kind="pulse",
            default_strategy="pulse_only_to_stop_declared_streaming_request",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="webclientDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="bool_toggle",
                official_source=_WEB_CLIENT_DAT_DOCS,
            )
            for name, label, default_strategy, cook_risk in (
                ("stream", "Stream", "enable_only_for_servers_that_support_streamed_responses", "high"),
                (
                    "verifycert",
                    "Verify Certificate",
                    "verify_tls_certificates_unless_controlled_test_server_is_declared",
                    "high",
                ),
                ("includeheader", "Include Header", "include_response_headers_only_when_needed", "medium"),
                ("clamp", "Clamp Output", "bounded_streaming_response_log_output", "medium"),
            )
        ],
        ParamSemantics(
            op_type="webclientDAT",
            name="timeout",
            label="Timeout",
            value_kind="int",
            unit="milliseconds",
            default_strategy="bounded_http_request_timeout_ms",
            cook_risk="medium",
            validation_rule="integer_timeout_ms",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="authtype",
            label="Authentication Type",
            value_kind="enum",
            enum_values=_WEB_CLIENT_AUTH_TYPE_VALUES,
            default_strategy="none_unless_authentication_mode_is_declared",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_streaming_response_log",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webclientDAT",
            name="clear",
            label="Clear Output",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_response_log_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_WEB_CLIENT_DAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="webclientDAT",
                name=name,
                label=label,
                value_kind="string",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule=validation_rule,
                official_source=_WEB_CLIENT_DAT_DOCS,
            )
            for name, label, default_strategy, cook_risk, validation_rule in (
                (
                    "username",
                    "Username",
                    "explicit_username_only_for_authenticated_requests",
                    "medium",
                    "credential_username_scope",
                ),
                (
                    "pw",
                    "Password",
                    "explicit_secret_only_when_user_provides_http_credentials",
                    "high",
                    "credential_secret_scope",
                ),
                (
                    "appkey",
                    "Application Key",
                    "explicit_oauth_application_key_only_for_oauth_requests",
                    "medium",
                    "client_id_scope",
                ),
                (
                    "appsecret",
                    "Application Secret",
                    "explicit_secret_only_when_user_provides_oauth_application_secret",
                    "high",
                    "credential_secret_scope",
                ),
                (
                    "oauthtoken",
                    "OAuth Token",
                    "explicit_oauth_token_only_for_oauth_requests",
                    "high",
                    "credential_secret_scope",
                ),
                (
                    "oauthsecret",
                    "OAuth Secret",
                    "explicit_oauth_secret_only_for_oauth1_requests",
                    "high",
                    "credential_secret_scope",
                ),
                (
                    "clientid",
                    "Client ID",
                    "explicit_oauth2_client_id_only_for_oauth2_requests",
                    "medium",
                    "client_id_scope",
                ),
                (
                    "token",
                    "Token",
                    "explicit_oauth2_token_only_when_user_provides_it",
                    "high",
                    "credential_secret_scope",
                ),
            )
        ],
    ]


def _web_server_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="webserverDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_embedded_web_server_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="restart",
            label="Restart",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_server_restart",
            cook_risk="high",
            validation_rule="pulse_action",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="port",
            label="Port",
            value_kind="int",
            unit="port",
            valid_range=(1.0, 65535.0),
            default_strategy="explicit_local_server_port",
            cook_risk="high",
            validation_rule="network_port_range",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="secure",
            label="Secure",
            value_kind="bool",
            default_strategy="enable_only_when_tls_key_and_certificate_are_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="privatekey",
            label="Private Key",
            value_kind="path",
            default_strategy="explicit_tls_private_key_path_only_when_secure_is_enabled",
            cook_risk="high",
            validation_rule="non_empty_path_if_set",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="certificate",
            label="Certificate",
            value_kind="path",
            default_strategy="explicit_tls_certificate_path_only_when_secure_is_enabled",
            cook_risk="high",
            validation_rule="non_empty_path_if_set",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="password",
            label="Certificate Password",
            value_kind="string",
            default_strategy="explicit_secret_only_when_tls_certificate_requires_password",
            cook_risk="high",
            validation_rule="credential_secret_scope",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="webserverDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat_for_http_and_websocket_handlers",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_WEB_SERVER_DAT_DOCS,
        ),
    ]


def _mqtt_client_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="mqttclientDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_mqtt_broker_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="netaddress",
            label="Network Address",
            value_kind="string",
            default_strategy="explicit_mqtt_broker_host",
            cook_risk="high",
            validation_rule="network_address_scope",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="specifyid",
            label="Specify Client ID",
            value_kind="bool",
            default_strategy="enable_only_when_persistent_client_identity_is_declared",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="usercid",
            label="Client ID",
            value_kind="string",
            default_strategy="explicit_client_id_when_specifyid_is_enabled",
            cook_risk="medium",
            validation_rule="client_id_scope",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="keepalive",
            label="Keep Alive",
            value_kind="int",
            unit="seconds",
            valid_range=(1.0, 86400.0),
            default_strategy="bounded_keepalive_seconds_for_broker_ping",
            cook_risk="medium",
            validation_rule="integer_timeout_seconds",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="maxinflight",
            label="Max Inflight",
            value_kind="int",
            valid_range=(1.0, 100000.0),
            default_strategy="bounded_inflight_message_count",
            cook_risk="medium",
            validation_rule="integer_message_limit",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="mqttclientDAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="bool_toggle",
                official_source=_MQTT_CLIENT_DAT_DOCS,
            )
            for name, label, default_strategy, cook_risk in (
                ("cleansession", "Clean Session", "explicit_session_persistence_policy", "medium"),
                (
                    "verifycert",
                    "Verify Certificate",
                    "verify_tls_certificates_unless_test_broker_is_declared",
                    "high",
                ),
                ("reconnect", "Reconnect", "auto_reconnect_for_live_mqtt_sources", "medium"),
                ("clamp", "Clamp Output", "bounded_mqtt_message_log_output", "medium"),
                ("bytes", "Bytes Column", "enable_only_when_raw_byte_diagnostics_are_requested", "medium"),
            )
        ],
        ParamSemantics(
            op_type="mqttclientDAT",
            name="username",
            label="Username",
            value_kind="string",
            default_strategy="explicit_username_only_for_authenticated_brokers",
            cook_risk="medium",
            validation_rule="credential_username_scope",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="password",
            label="Password",
            value_kind="string",
            default_strategy="explicit_secret_only_when_user_provides_broker_credentials",
            cook_risk="high",
            validation_rule="credential_secret_scope",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_CALLBACK_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="callbacks_dat_for_mqtt_events",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_mqtt_message_log",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="mqttclientDAT",
            name="clear",
            label="Clear Output",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_log_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_MQTT_CLIENT_DAT_DOCS,
        ),
    ]


def _udp_in_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="udpinDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_udp_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="protocol",
            label="Protocol",
            value_kind="enum",
            enum_values=_UDP_IN_PROTOCOL_VALUES,
            default_strategy="udp_messaging_default",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="address",
            label="Network Address",
            value_kind="string",
            default_strategy="explicit_multicast_address_when_multicast_is_selected",
            cook_risk="medium",
            validation_rule="network_address_scope",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="port",
            label="Port",
            value_kind="int",
            unit="port",
            valid_range=(1.0, 65535.0),
            default_strategy="explicit_udp_receive_port",
            cook_risk="medium",
            validation_rule="network_port_range",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="shared",
            label="Shared Connection",
            value_kind="bool",
            default_strategy="share_only_when_matching_udp_dats_are_declared",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="format",
            label="Row/Callback Format",
            value_kind="enum",
            enum_values=_UDP_IN_FORMAT_VALUES,
            default_strategy="per_message_for_packet_protocol_tables",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_CALLBACK_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="callbacks_dat_for_received_udp_messages",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="clamp",
            label="Clamp Output",
            value_kind="bool",
            default_strategy="bounded_udp_message_log_output",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_udp_message_log",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="clear",
            label="Clear Output",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_log_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_UDP_IN_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="udpinDAT",
            name="bytes",
            label="Bytes Column",
            value_kind="bool",
            default_strategy="enable_only_when_raw_byte_diagnostics_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_UDP_IN_DAT_DOCS,
        ),
    ]


def semantics_by_op_and_param(
    registry: Iterable[ParamSemantics] | None = None,
) -> dict[tuple[str, str], ParamSemantics]:
    """Index parameter semantics by canonical operator type and parameter name."""
    return {
        (_canonical_op_type(item.op_type), item.name): item
        for item in (registry if registry is not None else load_param_semantics_registry())
    }


def param_semantics_coverage_report(
    registry: Iterable[ParamSemantics] | None = None,
) -> dict[str, Any]:
    """Report coverage for master-plan priority parameter semantics bands."""
    records = list(registry if registry is not None else load_param_semantics_registry())
    by_operator: dict[str, list[ParamSemantics]] = {}
    invalid_sources: list[dict[str, str]] = []

    for semantic in records:
        op_type = _canonical_op_type(semantic.op_type)
        by_operator.setdefault(op_type, []).append(semantic)
        if not semantic.official_source.startswith("https://docs.derivative.ca/"):
            invalid_sources.append(
                {
                    "op_type": op_type,
                    "name": semantic.name,
                    "official_source": semantic.official_source,
                }
            )

    groups: dict[str, dict[str, Any]] = {}
    missing_all: list[str] = []
    priority_ops: list[str] = []
    for group_name, raw_ops in _PRIORITY_SEMANTICS_GROUPS.items():
        operators = [_canonical_op_type(op_type) for op_type in raw_ops]
        priority_ops.extend(operators)
        missing = sorted(op_type for op_type in operators if op_type not in by_operator)
        missing_all.extend(missing)
        groups[group_name] = {
            "operator_count": len(operators),
            "covered_operator_count": len(operators) - len(missing),
            "missing_operators": missing,
            "semantics_count_by_operator": {
                op_type: len(by_operator.get(op_type, [])) for op_type in operators
            },
        }

    missing_unique = sorted(set(missing_all))
    priority_unique = sorted(set(priority_ops))
    return {
        "schema_version": 1,
        "ok": not missing_unique and not invalid_sources,
        "priority_operator_count": len(priority_unique),
        "covered_operator_count": len(priority_unique) - len(missing_unique),
        "missing_operator_count": len(missing_unique),
        "missing_operators": missing_unique,
        "invalid_source_count": len(invalid_sources),
        "invalid_sources": invalid_sources,
        "priority_groups": groups,
    }


def _common_chop_semantics(op_type: str, official_source: str) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name="timeslice",
            label="Time Slice",
            value_kind="bool",
            default_strategy="off_unless_time_slice_audio_or_control_processing_is_needed",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="scope",
            label="Scope",
            value_kind="string",
            default_strategy="affect_all_input_channels_unless_channel_scope_is_explicit",
            cook_risk="low",
            validation_rule="channel_scope_pattern",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="srselect",
            label="Sample Rate Match",
            value_kind="enum",
            enum_values=_CHOP_SAMPLE_RATE_MATCH_VALUES,
            default_strategy="resample_at_first_input_rate_for_stable_control_chains",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="exportmethod",
            label="Export Method",
            value_kind="enum",
            enum_values=_CHOP_EXPORT_METHOD_VALUES,
            default_strategy="no_export_unless_explicit_parameter_binding_is_requested",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="autoexportroot",
            label="Export Root",
            value_kind="path",
            default_strategy="explicit_export_root_only_when_using_channel_path_exports",
            cook_risk="high",
            validation_rule="non_empty_path",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="exporttable",
            label="Export Table",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_export_table_dat_when_dat_exports_are_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="commonrenamefrom",
            label="Rename From",
            value_kind="string",
            default_strategy="leave_channel_names_unchanged_unless_explicit_rename_is_requested",
            cook_risk="medium",
            validation_rule="rename_pattern",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="commonrenameto",
            label="Rename To",
            value_kind="string",
            default_strategy="leave_channel_names_unchanged_unless_explicit_rename_is_requested",
            cook_risk="medium",
            validation_rule="rename_replacement",
            official_source=official_source,
        ),
    ]


def _analyze_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="analyzeCHOP",
            name="function",
            label="Analyze Function",
            value_kind="enum",
            enum_values=_ANALYZE_CHOP_FUNCTIONS,
            default_strategy="rms_power_or_peak_value_for_audio_reactive_control",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_ANALYZE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="analyzeCHOP",
            name="allowstart",
            label="Allow Start Peaks",
            value_kind="bool",
            default_strategy="off_unless_edge_peak_detection_is_explicitly_needed",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_ANALYZE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="analyzeCHOP",
            name="allowend",
            label="Allow End Peaks",
            value_kind="bool",
            default_strategy="off_unless_edge_peak_detection_is_explicitly_needed",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_ANALYZE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="analyzeCHOP",
            name="nopeakvalue",
            label="No Peak Value",
            value_kind="float",
            default_strategy="sentinel_for_downstream_no_peak_handling",
            cook_risk="medium",
            validation_rule="numeric_no_peak_sentinel",
            official_source=_ANALYZE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="analyzeCHOP",
            name="valleys",
            label="Analyze Valleys vs Peaks",
            value_kind="bool",
            default_strategy="off_for_peak_detection_unless_valleys_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_ANALYZE_CHOP_DOCS,
        ),
        *_common_chop_semantics("analyzeCHOP", _ANALYZE_CHOP_DOCS),
    ]


def _math_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="mathCHOP",
            name="preop",
            label="Channel Pre OP",
            value_kind="enum",
            enum_values=_MATH_CHOP_UNARY_OP_VALUES,
            default_strategy="off_until_pre_operation_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="chanop",
            label="Combine Channels",
            value_kind="enum",
            enum_values=_MATH_CHOP_COMBINE_VALUES,
            default_strategy="off_unless_multichannel_reduction_is_needed",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="chopop",
            label="Combine CHOPs",
            value_kind="enum",
            enum_values=_MATH_CHOP_COMBINE_VALUES,
            default_strategy="off_unless_multi_input_combination_is_needed",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="postop",
            label="Channel Post OP",
            value_kind="enum",
            enum_values=_MATH_CHOP_UNARY_OP_VALUES,
            default_strategy="off_until_post_operation_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="match",
            label="Match By",
            value_kind="enum",
            enum_values=_MATH_CHOP_MATCH_VALUES,
            default_strategy="channel_number_for_simple_generated_control_chains",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="align",
            label="Align",
            value_kind="enum",
            enum_values=_MATH_CHOP_ALIGN_VALUES,
            default_strategy="automatic_alignment_for_audio_or_control_inputs",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="interppars",
            label="Interp Pars per Sample",
            value_kind="bool",
            default_strategy="enable_for_high_frequency_audio_parameter_changes",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="integer",
            label="Integer",
            value_kind="enum",
            enum_values=_MATH_CHOP_INTEGER_VALUES,
            default_strategy="off_for_smooth_visual_control_ranges",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="preoff",
            label="Pre-Add",
            value_kind="float",
            default_strategy="zero_pre_add_for_normalized_control_mapping",
            cook_risk="medium",
            validation_rule="numeric_pre_add",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="gain",
            label="Multiply",
            value_kind="float",
            default_strategy="unit_gain_before_explicit_range_mapping",
            cook_risk="medium",
            validation_rule="numeric_gain",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="postoff",
            label="Post-Add",
            value_kind="float",
            default_strategy="zero_post_add_for_normalized_control_mapping",
            cook_risk="medium",
            validation_rule="numeric_post_add",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="fromrange",
            label="Input Range",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="normalize_expected_control_input_range",
            cook_risk="medium",
            validation_rule="range_tuple",
            official_source=_MATH_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="mathCHOP",
            name="torange",
            label="Output Range",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="map_to_safe_visual_control_range",
            cook_risk="medium",
            validation_rule="range_tuple",
            official_source=_MATH_CHOP_DOCS,
        ),
        *_common_chop_semantics("mathCHOP", _MATH_CHOP_DOCS),
    ]


def _filter_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="filterCHOP",
            name="type",
            label="Filter Type",
            value_kind="enum",
            enum_values=_FILTER_CHOP_TYPES,
            default_strategy="gaussian_or_one_euro_for_control_smoothing",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="effect",
            label="Effect",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="partial_smoothing_blend",
            cook_risk="medium",
            validation_rule="bounded_filter_effect",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="width",
            label="Filter Width",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="moderate_control_smoothing_width",
            cook_risk="medium",
            validation_rule="non_negative_filter_width",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="widthunit",
            label="Filter Width Unit",
            value_kind="enum",
            enum_values=_CHOP_UNIT_MENU_VALUES,
            default_strategy="seconds_for_time_based_control_smoothing",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="spike",
            label="Spike Tolerance",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="non_negative_despike_tolerance",
            cook_risk="medium",
            validation_rule="non_negative_spike_tolerance",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="passes",
            label="Number of Passes",
            value_kind="int",
            unit="passes",
            valid_range=(1.0, 100000.0),
            default_strategy="single_filter_pass_unless_extra_smoothing_is_requested",
            cook_risk="high",
            validation_rule="positive_pass_count",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="cutoff",
            label="Cutoff Frequency",
            value_kind="float",
            unit="hz",
            valid_range=(0.0, 100000.0),
            default_strategy="moderate_one_euro_cutoff_frequency",
            cook_risk="medium",
            validation_rule="non_negative_frequency",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="speedcoeff",
            label="Speed Coefficient",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="small_one_euro_speed_coefficient",
            cook_risk="medium",
            validation_rule="non_negative_speed_coefficient",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="slopecutoff",
            label="Slope Cutoff Frequency",
            value_kind="float",
            unit="hz",
            valid_range=(0.0, 100000.0),
            default_strategy="moderate_one_euro_slope_cutoff_frequency",
            cook_risk="medium",
            validation_rule="non_negative_frequency",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="slopedownreset",
            label="Slope Down Reset",
            value_kind="bool",
            default_strategy="off_unless_slope_reset_guard_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="slopeupreset",
            label="Slope Up Reset",
            value_kind="bool",
            default_strategy="off_unless_slope_reset_guard_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="reset",
            label="Reset",
            value_kind="bool",
            default_strategy="off_unless_filter_state_should_be_bypassed",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_FILTER_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="filterCHOP",
            name="filterpersample",
            label="Filter per Sample",
            value_kind="bool",
            default_strategy="off_for_standard_time_series_control_smoothing",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_FILTER_CHOP_DOCS,
        ),
        *_common_chop_semantics("filterCHOP", _FILTER_CHOP_DOCS),
    ]


def _movie_file_in_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="moviefileinTOP",
            name="file",
            label="File",
            value_kind="path",
            default_strategy="require_explicit_movie_or_image_sequence_path",
            cook_risk="high",
            validation_rule="non_empty_path",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="moviefileinTOP",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="bool_toggle",
                official_source=_MOVIE_FILE_IN_TOP_DOCS,
            )
            for name, label, default_strategy, cook_risk in (
                ("reload", "Reload", "off_unless_reloading_source_media_is_requested", "medium"),
                ("reloadpulse", "Reload Pulse", "pulse_only_for_explicit_media_reload", "medium"),
                ("play", "Play", "enabled_for_timeline_or_sequential_movie_playback", "medium"),
                ("hwdecode", "Hardware Decode", "use_default_hardware_decode_path_for_large_media", "high"),
            )
        ],
        ParamSemantics(
            op_type="moviefileinTOP",
            name="playmode",
            label="Play Mode",
            value_kind="enum",
            enum_values=_MOVIE_FILE_TOP_PLAY_MODE_VALUES,
            default_strategy="sequential_for_free_running_video_sources",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="moviefileinTOP",
            name="index",
            label="Index",
            value_kind="float",
            unit="frames",
            valid_range=(0.0, 1_000_000_000.0),
            default_strategy="non_negative_frame_index_when_specifying_movie_position",
            cook_risk="medium",
            validation_rule="non_negative_movie_index",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="moviefileinTOP",
            name="speed",
            label="Speed",
            value_kind="float",
            valid_range=(-1000.0, 1000.0),
            default_strategy="one_x_playback_until_time_warp_is_requested",
            cook_risk="medium",
            validation_rule="numeric_movie_speed",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="moviefileinTOP",
            name="imageindexing",
            label="Image Indexing",
            value_kind="enum",
            enum_values=_MOVIE_FILE_TOP_IMAGE_INDEXING_VALUES,
            default_strategy="native_indexing_for_image_sequences",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="moviefileinTOP",
            name="inputcolorspace",
            label="Input Color Space",
            value_kind="enum",
            enum_values=_TOP_COLOR_SPACE_VALUES,
            default_strategy="automatic_color_space_unless_media_pipeline_declares_one",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="moviefileinTOP",
            name="decodepixelformat",
            label="Decode Pixel Format",
            value_kind="enum",
            enum_values=_MOVIE_DECODE_PIXEL_FORMAT_VALUES,
            default_strategy="automatic_decode_format_unless_precision_is_declared",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="moviefileinTOP",
            name="prereadframes",
            label="Pre-Read Frames",
            value_kind="int",
            unit="frames",
            valid_range=(0.0, 10000.0),
            default_strategy="small_preread_window_for_responsive_movie_playback",
            cook_risk="high",
            validation_rule="non_negative_frame_count",
            official_source=_MOVIE_FILE_IN_TOP_DOCS,
        ),
    ]


def _video_device_in_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_video_device_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="driver",
            label="Driver",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_DRIVER_VALUES,
            default_strategy="default_driver_until_specific_capture_backend_is_declared",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="device",
            label="Device",
            value_kind="string",
            default_strategy="explicit_device_name_when_capture_source_is_declared",
            cook_risk="high",
            validation_rule="device_name_scope",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="ip",
            label="IP Address",
            value_kind="path",
            default_strategy="explicit_ip_only_for_network_capture_devices",
            cook_risk="high",
            validation_rule="non_empty_address",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="videodeviceinTOP",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy=default_strategy,
                cook_risk="high",
                validation_rule="bool_toggle",
                official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
            )
            for name, label, default_strategy in (
                ("specifyip", "Specify IP", "off_unless_network_capture_device_is_declared"),
                ("syncinputs", "Sync Inputs", "off_unless_multi_input_capture_sync_is_declared"),
                ("capture", "Capture", "enable_only_for_declared_live_capture_sources"),
            )
        ],
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="deinterlace",
            label="Deinterlace",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_DEINTERLACE_VALUES,
            default_strategy="off_for_progressive_sources",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="precedence",
            label="Precedence",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_PRECEDENCE_VALUES,
            default_strategy="newest_frame_for_live_capture_responsiveness",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="signalformat",
            label="Signal Format",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_SIGNAL_FORMAT_VALUES,
            default_strategy="automatic_signal_format_until_capture_standard_is_declared",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="inputpixelformat",
            label="Input Pixel Format",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_PIXEL_FORMAT_VALUES,
            default_strategy="automatic_pixel_format_until_capture_precision_is_declared",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="inputcolorspace",
            label="Input Color Space",
            value_kind="enum",
            enum_values=_TOP_COLOR_SPACE_VALUES,
            default_strategy="automatic_color_space_until_capture_pipeline_declares_one",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="inputreferencewhite",
            label="Input Reference White",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_REFERENCE_WHITE_VALUES,
            default_strategy="default_reference_white_for_standard_dynamic_range_capture",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="transfermode",
            label="Transfer Mode",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_TRANSFER_MODE_VALUES,
            default_strategy="automatic_transfer_mode_until_capture_backend_requires_gpu_direct",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="videodeviceinTOP",
            name="memorymode",
            label="Memory Mode",
            value_kind="enum",
            enum_values=_VIDEO_DEVICE_MEMORY_MODE_VALUES,
            default_strategy="automatic_memory_mode_until_gpu_memory_path_is_declared",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_VIDEO_DEVICE_IN_TOP_DOCS,
        ),
    ]


def _kinect_azure_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="kinectazureTOP",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_kinect_azure_sensor_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_KINECT_AZURE_TOP_DOCS,
        )
    ]


def _noise_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="noiseTOP",
            name="type",
            label="Noise Type",
            value_kind="enum",
            enum_values=_NOISE_TOP_TYPE_VALUES,
            default_strategy="simplex_or_perlin_unless_prompt_names_another_noise_type",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="seed",
            label="Seed",
            value_kind="int",
            default_strategy="stable_integer_seed_for_repeatable_noise_texture",
            cook_risk="low",
            validation_rule="integer_seed",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="period",
            label="Period",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_spatial_period_for_readable_noise_features",
            cook_risk="medium",
            validation_rule="non_negative_period",
            official_source=_NOISE_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="noiseTOP",
                name=name,
                label=label,
                value_kind=value_kind,
                valid_range=valid_range,
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule=validation_rule,
                official_source=_NOISE_TOP_DOCS,
            )
            for name, label, value_kind, valid_range, default_strategy, cook_risk, validation_rule in (
                (
                    "harmon",
                    "Harmonics",
                    "int",
                    (1.0, 100000.0),
                    "small_harmonic_count_for_realtime_texture",
                    "medium",
                    "positive_integer",
                ),
                (
                    "spread",
                    "Spread",
                    "float",
                    None,
                    "default_frequency_spread_between_harmonics",
                    "medium",
                    "numeric_noise_spread",
                ),
                (
                    "gain",
                    "Gain",
                    "float",
                    None,
                    "default_harmonic_gain_for_balanced_texture",
                    "medium",
                    "numeric_noise_gain",
                ),
                (
                    "rough",
                    "Roughness",
                    "float",
                    None,
                    "default_noise_roughness_for_smooth_texture",
                    "medium",
                    "numeric_noise_roughness",
                ),
                (
                    "exp",
                    "Exponent",
                    "float",
                    None,
                    "default_noise_exponent_for_linear_response",
                    "medium",
                    "numeric_noise_exponent",
                ),
                (
                    "amp",
                    "Amplitude",
                    "float",
                    (0.0, 100000.0),
                    "bounded_noise_texture_amplitude",
                    "medium",
                    "non_negative_amplitude",
                ),
                (
                    "offset",
                    "Offset",
                    "float",
                    None,
                    "zero_offset_unless_mask_bias_is_requested",
                    "medium",
                    "numeric_offset",
                ),
                (
                    "t4d",
                    "Translate 4D",
                    "float",
                    None,
                    "animate_fourth_coordinate_only_when_requested",
                    "medium",
                    "numeric_4d_translate",
                ),
                (
                    "s4d",
                    "Scale 4D",
                    "float",
                    None,
                    "default_fourth_coordinate_scale",
                    "medium",
                    "numeric_4d_scale",
                ),
                (
                    "inputscale",
                    "Input Scale",
                    "float",
                    None,
                    "neutral_input_mix_scale",
                    "medium",
                    "numeric_input_scale",
                ),
                (
                    "noisescale",
                    "Noise Scale",
                    "float",
                    None,
                    "neutral_noise_mix_scale",
                    "medium",
                    "numeric_noise_scale",
                ),
            )
        ],
        *[
            ParamSemantics(
                op_type="noiseTOP",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="bool_toggle",
                official_source=_NOISE_TOP_DOCS,
            )
            for name, label, default_strategy, cook_risk in (
                ("mono", "Monochrome", "enable_only_when_single_channel_masks_are_requested", "low"),
                ("aspectcorrect", "Aspect Correct", "preserve_square_noise_features_by_default", "low"),
                ("dither", "Dither", "off_unless_reducing_8bit_banding_is_requested", "medium"),
                ("gradient", "Gradient", "off_unless_slope_or_displacement_masks_are_requested", "high"),
                ("resmult", "Use Global Res Multiplier", "respect_project_resolution_multiplier", "medium"),
            )
        ],
        ParamSemantics(
            op_type="noiseTOP",
            name="xord",
            label="Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_predictable_noise_space_motion",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="rord",
            label="Rotate Order",
            value_kind="enum",
            enum_values=_ROTATE_ORDER_VALUES,
            default_strategy="xyz_rotation_order_for_predictable_noise_space_motion",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="noiseTOP",
                name=name,
                label=label,
                value_kind="tuple",
                tuple_size=3,
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="xyz_tuple",
                official_source=_NOISE_TOP_DOCS,
            )
            for name, label, default_strategy, cook_risk in (
                ("t", "Translate", "three_axis_noise_space_offset", "medium"),
                ("r", "Rotate", "three_axis_noise_space_rotation", "medium"),
                ("s", "Scale", "three_axis_noise_space_scale", "medium"),
                ("p", "Pivot", "three_axis_noise_space_pivot", "medium"),
            )
        ],
        ParamSemantics(
            op_type="noiseTOP",
            name="rgb",
            label="RGB Combine",
            value_kind="enum",
            enum_values=_NOISE_TOP_COMBINE_VALUES,
            default_strategy="noise_only_unless_input_texture_mixing_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="alpha",
            label="Alpha",
            value_kind="enum",
            enum_values=_NOISE_TOP_ALPHA_VALUES,
            default_strategy="opaque_or_noise_alpha_only_when_mask_output_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="mode",
            label="Mode",
            value_kind="enum",
            enum_values=_NOISE_TOP_MODE_VALUES,
            default_strategy="performance_mode_unless_quality_artifacts_are_visible",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="outputresolution",
            label="Output Resolution",
            value_kind="enum",
            enum_values=_TOP_OUTPUT_RESOLUTION_VALUES,
            default_strategy="use_input_or_project_resolution_for_noise_textures",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="resolution",
            label="Resolution",
            value_kind="tuple",
            tuple_size=2,
            unit="pixels",
            valid_range=(1.0, 8192.0),
            default_strategy="bounded_custom_noise_texture_resolution",
            cook_risk="high",
            validation_rule="warn_high_resolution",
            official_source=_NOISE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseTOP",
            name="npasses",
            label="Passes",
            value_kind="int",
            unit="passes",
            valid_range=(1.0, 1000.0),
            default_strategy="single_pass_unless_multi_pass_noise_is_explicit",
            cook_risk="high",
            validation_rule="positive_pass_count",
            official_source=_NOISE_TOP_DOCS,
        ),
    ]


def _feedback_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="feedbackTOP",
            name="top",
            label="Target TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="downstream_feedback_target",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="feedbackTOP",
            name="reset",
            label="Reset",
            value_kind="bool",
            default_strategy="keep_feedback_active_unless_explicitly_reset",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="feedbackTOP",
            name="resetpulse",
            label="Reset Pulse",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_feedback_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="feedbackTOP",
            name="outputresolution",
            label="Output Resolution",
            value_kind="enum",
            enum_values=_TOP_OUTPUT_RESOLUTION_VALUES,
            default_strategy="use_input_resolution_for_feedback_loops",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="feedbackTOP",
            name="resolution",
            label="Resolution",
            value_kind="tuple",
            tuple_size=2,
            unit="pixels",
            valid_range=(1.0, 8192.0),
            default_strategy="bounded_custom_feedback_resolution",
            cook_risk="high",
            validation_rule="warn_high_resolution",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="feedbackTOP",
            name="resmult",
            label="Use Global Res Multiplier",
            value_kind="bool",
            default_strategy="respect_global_resolution_multiplier",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="feedbackTOP",
            name="npasses",
            label="Passes",
            value_kind="int",
            unit="passes",
            valid_range=(1.0, 100000.0),
            default_strategy="single_pass_feedback_unless_explicitly_requested",
            cook_risk="high",
            validation_rule="positive_pass_count",
            official_source=_FEEDBACK_TOP_DOCS,
        ),
    ]


def _render_simple_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="ortho",
            label="Orthographic",
            value_kind="bool",
            default_strategy="perspective_unless_orthographic_preview_requested",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="fov",
            label="FOV",
            value_kind="float",
            unit="degrees",
            valid_range=(1.0, 179.0),
            default_strategy="moderate_render_preview_field_of_view",
            cook_risk="medium",
            validation_rule="numeric_field_of_view",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="orthowidth",
            label="Ortho Width",
            value_kind="float",
            unit="distance",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_orthographic_preview_width",
            cook_risk="medium",
            validation_rule="non_negative_orthographic_width",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="camdistance",
            label="Camera Distance",
            value_kind="float",
            unit="distance",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_camera_distance",
            cook_risk="medium",
            validation_rule="non_negative_camera_distance",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="normalizegeo",
            label="Normalize Geometry",
            value_kind="bool",
            default_strategy="normalize_pop_preview_bounds",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="bgcolor",
            label="Background Color",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="opaque_or_transparent_preview_background",
            cook_risk="low",
            validation_rule="rgba_tuple",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="pop",
            label="POP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="created_null_pop",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="rendersimpleTOP",
                name=name,
                label=label,
                value_kind="tuple",
                tuple_size=3,
                unit=unit,
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule="xyz_tuple",
                official_source=_RENDER_SIMPLE_TOP_DOCS,
            )
            for name, label, unit, default_strategy in [
                ("geotranslate", "Geometry Translate", "distance", "three_axis_geometry_translate"),
                ("georotate", "Geometry Rotate", "degrees", "three_axis_geometry_rotation"),
            ]
        ],
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="geoscale",
            label="Geometry Scale",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_uniform_geometry_scale",
            cook_risk="medium",
            validation_rule="non_negative_uniform_scale",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="materialsource",
            label="Material Source",
            value_kind="enum",
            enum_values=_RENDER_SIMPLE_MATERIAL_SOURCE_VALUES,
            default_strategy="internal_phong_unless_mat_node_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="wireframe",
            label="Wireframe",
            value_kind="bool",
            default_strategy="solid_preview_unless_wireframe_requested",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="rendersimpleTOP",
                name=name,
                label=label,
                value_kind="tuple",
                tuple_size=3,
                valid_range=(0.0, 1.0),
                default_strategy=default_strategy,
                cook_risk="low",
                validation_rule="rgb_tuple",
                official_source=_RENDER_SIMPLE_TOP_DOCS,
            )
            for name, label, default_strategy in [
                ("constant", "Constant", "neutral_internal_phong_constant_color"),
                ("diffuse", "Diffuse", "neutral_internal_phong_diffuse_color"),
            ]
        ],
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="colormap",
            label="Color Map",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_or_user_supplied_color_map_top",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="mat",
            label="MAT",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="created_material_when_materialsource_is_matnode",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="outputresolution",
            label="Output Resolution",
            value_kind="enum",
            enum_values=_TOP_OUTPUT_RESOLUTION_VALUES,
            default_strategy="use_input_or_safe_custom_preview_resolution",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="resolution",
            label="Resolution",
            value_kind="tuple",
            tuple_size=2,
            unit="pixels",
            valid_range=(1.0, 8192.0),
            default_strategy="bounded_custom_preview_resolution",
            cook_risk="high",
            validation_rule="warn_high_resolution",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="resmult",
            label="Use Global Res Multiplier",
            value_kind="bool",
            default_strategy="respect_global_resolution_multiplier",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="rendersimpleTOP",
            name="npasses",
            label="Passes",
            value_kind="int",
            unit="passes",
            valid_range=(1.0, 100000.0),
            default_strategy="single_pass_preview_render_unless_requested",
            cook_risk="high",
            validation_rule="positive_pass_count",
            official_source=_RENDER_SIMPLE_TOP_DOCS,
        ),
    ]


def _level_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="levelTOP",
            name="clampinput",
            label="Clamp Input",
            value_kind="enum",
            enum_values=_LEVEL_CLAMP_INPUT_VALUES,
            default_strategy="automatic_input_clamping",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LEVEL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="levelTOP",
            name="invert",
            label="Invert",
            value_kind="bool",
            default_strategy="leave_off_unless_inversion_requested",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_LEVEL_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="levelTOP",
                name=name,
                label=label,
                value_kind="float",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="numeric_level_adjustment",
                official_source=_LEVEL_TOP_DOCS,
            )
            for name, label, default_strategy, cook_risk in [
                ("blacklevel", "Black Level", "keep_default_black_level", "medium"),
                ("brightness1", "Brightness 1", "neutral_brightness_adjustment", "medium"),
                ("gamma1", "Gamma 1", "neutral_gamma_adjustment", "medium"),
                ("contrast", "Contrast", "neutral_contrast_adjustment", "medium"),
                ("inlow", "In Low", "default_input_low_range", "medium"),
                ("inhigh", "In High", "default_input_high_range", "medium"),
                ("outlow", "Out Low", "default_output_low_range", "medium"),
                ("outhigh", "Out High", "default_output_high_range", "medium"),
                ("threshold", "Threshold", "neutral_step_threshold", "medium"),
                ("clamp", "Clamp", "bounded_post_clamp", "medium"),
            ]
        ],
        ParamSemantics(
            op_type="levelTOP",
            name="stepping",
            label="Apply Stepping",
            value_kind="bool",
            default_strategy="leave_off_unless_posterizing_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LEVEL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="levelTOP",
            name="stepsize",
            label="Step Size",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="small_positive_step_size_when_posterizing",
            cook_risk="medium",
            validation_rule="non_negative_step_size",
            official_source=_LEVEL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="levelTOP",
            name="opacity",
            label="Opacity",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="safe_feedback_decay",
            cook_risk="medium",
            validation_rule="bounded_feedback_decay",
            official_source=_LEVEL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="levelTOP",
            name="premultrgbbyalpha",
            label="Pre-Multiply RGB by Alpha",
            value_kind="bool",
            default_strategy="leave_off_unless_premultiplied_alpha_is_required",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LEVEL_TOP_DOCS,
        ),
    ]


def _edge_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="edgeTOP",
            name="edgecolor",
            label="Edge Color",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="opaque_white_edges_for_clear_detection",
            cook_risk="low",
            validation_rule="rgba_tuple",
            official_source=_EDGE_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="edgeTOP",
                name=name,
                label=label,
                value_kind="float",
                valid_range=(0.0, 1.0),
                default_strategy="normalized_edge_color_channel",
                cook_risk="low",
                validation_rule="normalized_color_channel",
                official_source=_EDGE_TOP_DOCS,
            )
            for name, label in (
                ("edgecolorr", "Edge Color Red"),
                ("edgecolorg", "Edge Color Green"),
                ("edgecolorb", "Edge Color Blue"),
                ("edgecolora", "Edge Color Alpha"),
            )
        ],
    ]


def _blur_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="blurTOP",
            name="size",
            label="Filter Size",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="small_positive_filter_size_for_realtime_blur",
            cook_risk="medium",
            validation_rule="non_negative_blur_size",
            official_source=_BLUR_TOP_DOCS,
        ),
    ]


def _composite_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="compositeTOP",
            name="top",
            label="TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="explicit_top_pattern_or_created_top_inputs",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="previewgrid",
            label="Preview Grid",
            value_kind="bool",
            default_strategy="off_for_normal_compositing",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="selectinput",
            label="Select Input",
            value_kind="bool",
            default_strategy="off_for_normal_compositing",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="inputindex",
            label="Input Index",
            value_kind="int",
            default_strategy="first_input_when_select_input_is_enabled",
            cook_risk="low",
            validation_rule="integer_input_index",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="operand",
            label="Operation",
            value_kind="enum",
            enum_values=_COMPOSITE_OPERAND_VALUES,
            default_strategy="keep_default_or_over_for_feedback_merge",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="swaporder",
            label="Swap Operation Order",
            value_kind="bool",
            default_strategy="preserve_input_order",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="size",
            label="Fixed Layer",
            value_kind="enum",
            enum_values=_COMPOSITE_SIZE_VALUES,
            default_strategy="input_1_as_fixed_layer",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="prefit",
            label="Pre-Fit Overlay",
            value_kind="enum",
            enum_values=_COMPOSITE_PREFIT_VALUES,
            default_strategy="fit_best_overlay_when_explicitly_transforming",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="justifyh",
            label="Justify Horizontal",
            value_kind="enum",
            enum_values=_COMPOSITE_JUSTIFY_H_VALUES,
            default_strategy="center_overlay_horizontally",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="justifyv",
            label="Justify Vertical",
            value_kind="enum",
            enum_values=_COMPOSITE_JUSTIFY_V_VALUES,
            default_strategy="center_overlay_vertically",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="extend",
            label="Extend Overlay",
            value_kind="enum",
            enum_values=_TOP_EXTEND_VALUES,
            default_strategy="hold_overlay_edges",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="r",
            label="Rotate",
            value_kind="float",
            unit="degrees",
            default_strategy="no_overlay_rotation",
            cook_risk="medium",
            validation_rule="numeric_rotation",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="t",
            label="Translate",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="two_axis_overlay_translation",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="s",
            label="Scale",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="two_axis_overlay_scale",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="p",
            label="Pivot",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="two_axis_overlay_pivot",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="compositeTOP",
            name="legacyxform",
            label="Legacy Transform",
            value_kind="bool",
            default_strategy="disabled_for_current_transform_matrix",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_COMPOSITE_TOP_DOCS,
        ),
    ]


def _lfo_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="lfoCHOP",
            name="wavetype",
            label="Wave Type",
            value_kind="enum",
            enum_values=_LFO_CHOP_WAVE_TYPE_VALUES,
            default_strategy="sine_wave_unless_prompt_names_another_waveform",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="play",
            label="Play",
            value_kind="bool",
            default_strategy="enabled_for_continuous_modulation",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="frequency",
            label="Frequency",
            value_kind="float",
            unit="cycles_per_second",
            valid_range=(0.0, 100000.0),
            default_strategy="low_frequency_modulation_for_visual_controls",
            cook_risk="medium",
            validation_rule="non_negative_frequency",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="offset",
            label="Offset",
            value_kind="float",
            default_strategy="zero_offset_unless_phase_alignment_is_requested",
            cook_risk="medium",
            validation_rule="numeric_offset",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="amp",
            label="Amplitude",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="bounded_control_amplitude",
            cook_risk="medium",
            validation_rule="non_negative_amplitude",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="bias",
            label="Bias",
            value_kind="float",
            default_strategy="center_control_signal_unless_unipolar_modulation_is_requested",
            cook_risk="medium",
            validation_rule="numeric_bias",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="phase",
            label="Phase",
            value_kind="float",
            unit="cycles",
            default_strategy="zero_phase_unless_offset_modulation_is_requested",
            cook_risk="low",
            validation_rule="numeric_phase",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="resetcondition",
            label="Reset Condition",
            value_kind="enum",
            enum_values=_CHOP_RESET_CONDITION_VALUES,
            default_strategy="off_unless_explicit_reset_trigger_is_planned",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="reset",
            label="Reset",
            value_kind="bool",
            default_strategy="off_until_explicit_reset_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="resetpulse",
            label="Reset Pulse",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_lfo_phase_reset",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="channelname",
            label="Channel Name",
            value_kind="string",
            default_strategy="descriptive_control_channel_name",
            cook_risk="low",
            validation_rule="channel_name_pattern",
            official_source=_LFO_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="lfoCHOP",
            name="rate",
            label="Rate",
            value_kind="float",
            default_strategy="frequency_rate_mode_for_visual_modulation",
            cook_risk="medium",
            validation_rule="numeric_sample_rate",
            official_source=_LFO_CHOP_DOCS,
        ),
        *_common_chop_semantics("lfoCHOP", _LFO_CHOP_DOCS),
    ]


def _wave_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="waveCHOP",
            name="wavetype",
            label="Wave Type",
            value_kind="enum",
            enum_values=_WAVE_CHOP_WAVE_TYPE_VALUES,
            default_strategy="sine_wave_unless_prompt_names_another_waveform",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_WAVE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="waveCHOP",
            name="period",
            label="Period",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_period_for_control_wave",
            cook_risk="medium",
            validation_rule="non_negative_period",
            official_source=_WAVE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="waveCHOP",
            name="periodunit",
            label="Period Unit",
            value_kind="enum",
            enum_values=_CHOP_UNIT_MENU_VALUES,
            default_strategy="seconds_for_human_readable_wave_periods",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_WAVE_CHOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="waveCHOP",
                name=name,
                label=label,
                value_kind="float",
                valid_range=valid_range,
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule=validation_rule,
                official_source=_WAVE_CHOP_DOCS,
            )
            for name, label, valid_range, default_strategy, cook_risk, validation_rule in (
                ("phase", "Phase", None, "zero_phase_unless_alignment_is_requested", "low", "numeric_phase"),
                (
                    "bias",
                    "Bias",
                    None,
                    "center_control_signal_unless_unipolar_modulation_is_requested",
                    "medium",
                    "numeric_bias",
                ),
                (
                    "amp",
                    "Amplitude",
                    (0.0, 100000.0),
                    "bounded_control_amplitude",
                    "medium",
                    "non_negative_amplitude",
                ),
                (
                    "offset",
                    "Offset",
                    None,
                    "zero_offset_unless_positioning_is_requested",
                    "medium",
                    "numeric_offset",
                ),
                (
                    "decay",
                    "Decay",
                    (0.0, 100000.0),
                    "no_decay_unless_damped_wave_is_requested",
                    "medium",
                    "non_negative_decay",
                ),
                (
                    "rate",
                    "Rate",
                    (0.0, 100000.0),
                    "positive_sample_rate_when_specified",
                    "medium",
                    "numeric_sample_rate",
                ),
                ("left", "Left Limit", None, "default_left_wave_limit", "low", "numeric_wave_limit"),
                ("right", "Right Limit", None, "default_right_wave_limit", "low", "numeric_wave_limit"),
            )
        ],
        ParamSemantics(
            op_type="waveCHOP",
            name="channelname",
            label="Channel Name",
            value_kind="string",
            default_strategy="descriptive_wave_channel_name",
            cook_risk="low",
            validation_rule="channel_name_pattern",
            official_source=_WAVE_CHOP_DOCS,
        ),
        *_common_chop_semantics("waveCHOP", _WAVE_CHOP_DOCS),
    ]


def _noise_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="noiseCHOP",
            name="type",
            label="Noise Type",
            value_kind="enum",
            enum_values=_NOISE_CHOP_TYPE_VALUES,
            default_strategy="docs_verified_noise_type_menu",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseCHOP",
            name="seed",
            label="Seed",
            value_kind="int",
            default_strategy="stable_integer_seed_for_repeatable_noise",
            cook_risk="low",
            validation_rule="integer_seed",
            official_source=_NOISE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseCHOP",
            name="period",
            label="Period",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_noise_period",
            cook_risk="medium",
            validation_rule="non_negative_period",
            official_source=_NOISE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseCHOP",
            name="periodunit",
            label="Period Unit",
            value_kind="enum",
            enum_values=_NOISE_CHOP_PERIOD_UNIT_VALUES,
            default_strategy="seconds_or_fraction_as_docs_verified_period_unit",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_CHOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="noiseCHOP",
                name=name,
                label=label,
                value_kind=value_kind,
                valid_range=valid_range,
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule=validation_rule,
                official_source=_NOISE_CHOP_DOCS,
            )
            for name, label, value_kind, valid_range, default_strategy, cook_risk, validation_rule in (
                (
                    "harmon",
                    "Harmonics",
                    "int",
                    (1.0, 100000.0),
                    "positive_harmonic_count",
                    "medium",
                    "positive_integer",
                ),
                ("spread", "Spread", "float", None, "default_noise_spread", "medium", "numeric_noise_spread"),
                (
                    "rough",
                    "Roughness",
                    "float",
                    None,
                    "default_noise_roughness",
                    "medium",
                    "numeric_noise_roughness",
                ),
                (
                    "exp",
                    "Exponent",
                    "float",
                    None,
                    "default_noise_exponent",
                    "medium",
                    "numeric_noise_exponent",
                ),
                (
                    "numint",
                    "Number of Integrals",
                    "int",
                    (0.0, 100000.0),
                    "integer_integral_count",
                    "medium",
                    "non_negative_integer",
                ),
                (
                    "amp",
                    "Amplitude",
                    "float",
                    (0.0, 100000.0),
                    "bounded_noise_amplitude",
                    "medium",
                    "non_negative_amplitude",
                ),
                (
                    "sustain",
                    "Sustain",
                    "float",
                    (0.0, 100000.0),
                    "bounded_sustain_duration",
                    "medium",
                    "non_negative_duration",
                ),
                (
                    "minsustain",
                    "Minimum Sustain",
                    "float",
                    (0.0, 100000.0),
                    "bounded_minimum_sustain_duration",
                    "medium",
                    "non_negative_duration",
                ),
                (
                    "rate",
                    "Rate",
                    "float",
                    (0.0, 100000.0),
                    "positive_sample_rate_when_specified",
                    "medium",
                    "numeric_sample_rate",
                ),
            )
        ],
        ParamSemantics(
            op_type="noiseCHOP",
            name="reset",
            label="Reset",
            value_kind="bool",
            default_strategy="off_until_explicit_noise_reset_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_NOISE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseCHOP",
            name="resetpulse",
            label="Reset Pulse",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_noise_reset",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_NOISE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseCHOP",
            name="channame",
            label="Channel Name",
            value_kind="string",
            default_strategy="descriptive_noise_channel_name",
            cook_risk="low",
            validation_rule="channel_name_pattern",
            official_source=_NOISE_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="noiseCHOP",
            name="specifyrate",
            label="Specify Rate",
            value_kind="bool",
            default_strategy="off_unless_explicit_sample_rate_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_NOISE_CHOP_DOCS,
        ),
        *_common_chop_semantics("noiseCHOP", _NOISE_CHOP_DOCS),
    ]


def _audio_file_in_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="file",
            label="Audio File Path",
            value_kind="path",
            default_strategy="require_user_file_or_device_substitution",
            cook_risk="medium",
            validation_rule="non_empty_path_if_set",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="play",
            label="Play",
            value_kind="bool",
            default_strategy="enable_only_when_source_is_confirmed",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="playmode",
            label="Play Mode",
            value_kind="enum",
            enum_values=_AUDIO_FILE_PLAY_MODE_VALUES,
            default_strategy="sequential_for_live_audio_reactive_playback",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="speed",
            label="Speed",
            value_kind="float",
            default_strategy="normal_forward_playback_speed",
            cook_risk="medium",
            validation_rule="numeric_playback_speed",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="cue",
            label="Cue",
            value_kind="bool",
            default_strategy="leave_off_unless_explicit_cue_jump_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="cuepulse",
            label="Cue Pulse",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_transport_reset",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        *_audio_file_float_semantics(
            {
                "cuepoint": ("Cue Point", "audio_index"),
                "index": ("Index", "audio_index"),
                "trimstart": ("Trim Start", "audio_index"),
                "trimend": ("Trim End", "audio_index"),
                "opentimeout": ("Open Timeout", "milliseconds"),
                "volume": ("Volume", "gain"),
            }
        ),
        *_audio_file_unit_semantics(
            {
                "cuepointunit": "Cue Point Unit",
                "indexunit": "Index Unit",
                "trimstartunit": "Trim Start Unit",
                "trimendunit": "Trim End Unit",
            }
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="timecodeop",
            label="Timecode Object/CHOP/DAT",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_timecode_source_when_timecode_mode_is_requested",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="repeat",
            label="Repeat",
            value_kind="enum",
            enum_values=_AUDIO_REPEAT_VALUES,
            default_strategy="off_unless_looping_audio_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="trim",
            label="Trim",
            value_kind="bool",
            default_strategy="disabled_unless_in_out_points_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileinCHOP",
            name="mono",
            label="Mono",
            value_kind="bool",
            default_strategy="preserve_source_channels_unless_mono_analysis_is_requested",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        ),
    ]


def _audio_file_float_semantics(labels_and_units: dict[str, tuple[str, str]]) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="audiofileinCHOP",
            name=name,
            label=label,
            value_kind="float",
            unit=unit,
            default_strategy="explicit_transport_value_when_requested",
            cook_risk="medium",
            validation_rule="numeric_audio_transport_value",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        )
        for name, (label, unit) in labels_and_units.items()
    ]


def _audio_file_unit_semantics(labels_by_name: dict[str, str]) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="audiofileinCHOP",
            name=name,
            label=label,
            value_kind="enum",
            enum_values=_AUDIO_INDEX_UNIT_VALUES,
            default_strategy="seconds_for_human_readable_transport_values",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_AUDIO_FILE_IN_CHOP_DOCS,
        )
        for name, label in labels_by_name.items()
    ]


def _audio_file_out_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="filetype",
            label="File Type",
            value_kind="enum",
            enum_values=_AUDIO_FILE_OUT_TYPE_VALUES,
            default_strategy="wav_for_local_review_unless_user_requests_compressed_audio",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="uniquesuff",
            label="Unique Suffix",
            value_kind="bool",
            default_strategy="enabled_for_automated_recording_to_avoid_overwriting_takes",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="file",
            label="File",
            value_kind="path",
            default_strategy="explicit_output_file_before_recording",
            cook_risk="high",
            validation_rule="non_empty_path",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="codec",
            label="Codec",
            value_kind="string",
            default_strategy="codec_depends_on_selected_audio_file_type",
            cook_risk="medium",
            validation_rule="filetype_dependent_codec_menu",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="bitrate",
            label="Bitrate",
            value_kind="int",
            unit="bits_per_second",
            default_strategy="explicit_bitrate_only_for_compressed_output_formats",
            cook_risk="medium",
            validation_rule="integer_audio_bitrate",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="record",
            label="Record",
            value_kind="bool",
            default_strategy="off_until_output_path_and_source_audio_are_confirmed",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="pause",
            label="Pause",
            value_kind="bool",
            default_strategy="off_unless_user_requests_paused_recording_state",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiofileoutCHOP",
            name="headerdat",
            label="Header Source DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_metadata_table_dat_only_when_headers_are_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_AUDIO_FILE_OUT_CHOP_DOCS,
        ),
    ]


def _audio_device_in_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_device_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="driver",
            label="Driver",
            value_kind="enum",
            enum_values=_AUDIO_DEVICE_DRIVER_VALUES,
            default_strategy="default_coreaudio_or_directsound_unless_specific_driver_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="device",
            label="Device",
            value_kind="string",
            default_strategy="default_audio_input_or_explicit_user_device",
            cook_risk="high",
            validation_rule="device_name_scope",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="errormissing",
            label="Error if Missing",
            value_kind="bool",
            default_strategy="surface_missing_device_errors_for_live_audio_plans",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="inputs",
            label="Inputs",
            value_kind="string",
            default_strategy="explicit_input_channel_scope_for_asio_or_coreaudio",
            cook_risk="medium",
            validation_rule="input_channel_scope",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="format",
            label="Format",
            value_kind="enum",
            enum_values=_AUDIO_DEVICE_FORMAT_VALUES,
            default_strategy="stereo_for_general_audio_reactive_controls",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="rate",
            label="Rate",
            value_kind="float",
            unit="samples_per_second",
            default_strategy="device_default_sample_rate",
            cook_risk="medium",
            validation_rule="numeric_sample_rate",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="bufferlength",
            label="Buffer Length",
            value_kind="float",
            default_strategy="device_default_buffer_length",
            cook_risk="high",
            validation_rule="numeric_audio_buffer_length",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceinCHOP",
            name="numchan",
            label="Number of Channels",
            value_kind="int",
            default_strategy="explicit_channel_count_for_blackmagic_or_aja",
            cook_risk="medium",
            validation_rule="integer_channel_count",
            official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="audiodeviceinCHOP",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_directsound_input_channels",
                cook_risk="medium",
                validation_rule="bool_toggle",
                official_source=_AUDIO_DEVICE_IN_CHOP_DOCS,
            )
            for name, label in _AUDIO_DEVICE_CHANNEL_TOGGLES
        ],
    ]


def _audio_device_out_chop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="audiodeviceoutCHOP",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_audio_output_is_explicitly_requested",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_AUDIO_DEVICE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceoutCHOP",
            name="driver",
            label="Driver",
            value_kind="enum",
            enum_values=_AUDIO_DEVICE_DRIVER_VALUES,
            default_strategy="default_coreaudio_or_directsound_unless_specific_output_driver_is_requested",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_AUDIO_DEVICE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceoutCHOP",
            name="device",
            label="Device",
            value_kind="string",
            default_strategy="default_audio_output_or_explicit_user_device",
            cook_risk="high",
            validation_rule="device_name_scope",
            official_source=_AUDIO_DEVICE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceoutCHOP",
            name="outputs",
            label="Outputs",
            value_kind="string",
            default_strategy="explicit_output_channel_scope_for_asio_or_coreaudio",
            cook_risk="high",
            validation_rule="output_channel_scope",
            official_source=_AUDIO_DEVICE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceoutCHOP",
            name="adjustspeed",
            label="Adjust Speed",
            value_kind="bool",
            default_strategy="disabled_unless_clock_following_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_AUDIO_DEVICE_OUT_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="audiodeviceoutCHOP",
            name="clampoutput",
            label="Clamp Output",
            value_kind="bool",
            default_strategy="enabled_for_safer_live_audio_output",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_AUDIO_DEVICE_OUT_CHOP_DOCS,
        ),
    ]


def _midi_in_chop_semantics() -> list[ParamSemantics]:
    return [
        *_common_chop_semantics("midiinCHOP", _MIDI_IN_CHOP_DOCS),
        ParamSemantics(
            op_type="midiinCHOP",
            name="source",
            label="Source",
            value_kind="enum",
            enum_values=_MIDI_IN_SOURCE_VALUES,
            default_strategy="device_source_declared_before_live_midi_input",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="device",
            label="Device",
            value_kind="string",
            default_strategy="explicit_midi_device_name_when_declared",
            cook_risk="high",
            validation_rule="non_empty_device_name_when_set",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="file",
            label="File",
            value_kind="path",
            default_strategy="explicit_midi_file_only_for_file_source",
            cook_risk="medium",
            validation_rule="non_empty_path",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="midiinCHOP",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="enable_only_requested_midi_event_streams",
                cook_risk="medium",
                validation_rule="bool_toggle",
                official_source=_MIDI_IN_CHOP_DOCS,
            )
            for name, label in (
                ("simplified", "Simplified Output"),
                ("record", "Record"),
                ("timer", "Timer Events"),
                ("sys", "System Events"),
            )
        ],
        ParamSemantics(
            op_type="midiinCHOP",
            name="start",
            label="Output Range Start",
            value_kind="float",
            default_strategy="explicit_midi_output_range_start",
            cook_risk="medium",
            validation_rule="numeric_output_range_start",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="end",
            label="Output Range End",
            value_kind="float",
            default_strategy="explicit_midi_output_range_end",
            cook_risk="medium",
            validation_rule="numeric_output_range_end",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="rate",
            label="Sample Rate",
            value_kind="float",
            default_strategy="preserve_sufficient_sample_rate_for_midi_events",
            cook_risk="medium",
            validation_rule="numeric_sample_rate",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="controlname",
            label="Controller Channel Name",
            value_kind="string",
            default_strategy="explicit_controller_channel_pattern",
            cook_risk="low",
            validation_rule="channel_name_pattern",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="controltype",
            label="Controller Format",
            value_kind="string",
            default_strategy="leave_controller_format_default_unless_14bit_is_needed",
            cook_risk="medium",
            validation_rule="midi_controller_format",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="notename",
            label="Note Channel Name",
            value_kind="string",
            default_strategy="explicit_note_channel_pattern",
            cook_risk="low",
            validation_rule="channel_name_pattern",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
        ParamSemantics(
            op_type="midiinCHOP",
            name="chan",
            label="Channel Prefix",
            value_kind="string",
            default_strategy="explicit_channel_filter_or_prefix_when_needed",
            cook_risk="medium",
            validation_rule="midi_channel_scope",
            official_source=_MIDI_IN_CHOP_DOCS,
        ),
    ]


def _serial_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="serialDAT",
            name="active",
            label="Active",
            value_kind="bool",
            default_strategy="enable_only_when_serial_device_source_is_declared",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="format",
            label="Row/Callback Format",
            value_kind="enum",
            enum_values=_SERIAL_DAT_FORMAT_VALUES,
            default_strategy="per_line_for_text_protocol_messages",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="port",
            label="Port",
            value_kind="string",
            default_strategy="explicit_user_serial_port_or_device_source",
            cook_risk="high",
            validation_rule="serial_port_scope",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="baudrate",
            label="Baud Rate",
            value_kind="enum",
            enum_values=_SERIAL_DAT_BAUD_RATE_VALUES,
            default_strategy="match_declared_device_baud_rate",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="databits",
            label="Data Bits",
            value_kind="enum",
            enum_values=_SERIAL_DAT_DATA_BITS_VALUES,
            default_strategy="device_protocol_data_bits",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="parity",
            label="Parity",
            value_kind="enum",
            enum_values=_SERIAL_DAT_PARITY_VALUES,
            default_strategy="device_protocol_parity",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="stopbits",
            label="Stop Bits",
            value_kind="enum",
            enum_values=_SERIAL_DAT_STOP_BITS_VALUES,
            default_strategy="device_protocol_stop_bits",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="dtr",
            label="DTR",
            value_kind="enum",
            enum_values=_SERIAL_DAT_DTR_VALUES,
            default_strategy="leave_default_unless_device_flow_control_is_declared",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="rts",
            label="RTS",
            value_kind="enum",
            enum_values=_SERIAL_DAT_RTS_VALUES,
            default_strategy="leave_default_unless_device_flow_control_is_declared",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="callbacks",
            label="Callbacks DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_callback_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="executeloc",
            label="Execute From",
            value_kind="enum",
            enum_values=_CALLBACK_DAT_EXECUTE_LOCATION_VALUES,
            default_strategy="callbacks_dat_for_received_serial_messages",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="fromop",
            label="From Operator",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="explicit_callback_context_when_specified",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="clamp",
            label="Clamp Output",
            value_kind="bool",
            default_strategy="bounded_serial_message_log_output",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="maxlines",
            label="Maximum Lines",
            value_kind="int",
            unit="rows",
            default_strategy="small_bounded_serial_message_log",
            cook_risk="medium",
            validation_rule="integer_output_limit",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="clear",
            label="Clear Output",
            value_kind="pulse",
            default_strategy="pulse_only_for_explicit_log_clear",
            cook_risk="medium",
            validation_rule="pulse_action",
            official_source=_SERIAL_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="serialDAT",
            name="bytes",
            label="Bytes Column",
            value_kind="bool",
            default_strategy="enable_only_when_raw_byte_diagnostics_are_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_SERIAL_DAT_DOCS,
        ),
    ]


def _panel_component_layout_semantics(op_type: str, official_source: str) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name="x",
            label="X",
            value_kind="int",
            unit="pixels",
            default_strategy="explicit_panel_layout_position",
            cook_risk="low",
            validation_rule="integer_panel_position",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="y",
            label="Y",
            value_kind="int",
            unit="pixels",
            default_strategy="explicit_panel_layout_position",
            cook_risk="low",
            validation_rule="integer_panel_position",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="w",
            label="Width",
            value_kind="int",
            unit="pixels",
            valid_range=(1.0, 100000.0),
            default_strategy="positive_panel_width",
            cook_risk="medium",
            validation_rule="positive_panel_dimension",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="h",
            label="Height",
            value_kind="int",
            unit="pixels",
            valid_range=(1.0, 100000.0),
            default_strategy="positive_panel_height",
            cook_risk="medium",
            validation_rule="positive_panel_dimension",
            official_source=official_source,
        ),
    ]


def _panel_component_interaction_semantics(op_type: str, official_source: str) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name="display",
            label="Display",
            value_kind="bool",
            default_strategy="visible_for_generated_control_panels",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="enable",
            label="Enable",
            value_kind="bool",
            default_strategy="enabled_for_interactive_control_panels",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="helpdat",
            label="Help DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_help_text_dat_when_rollover_help_is_needed",
            cook_risk="low",
            validation_rule="created_reference_matches_family",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="opacity",
            label="Opacity",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="opaque_visible_panel",
            cook_risk="medium",
            validation_rule="bounded_panel_opacity",
            official_source=official_source,
        ),
    ]


def _mat_top_map_semantics(
    op_type: str,
    official_source: str,
    labels_by_name: dict[str, str],
) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name=name,
            label=label,
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_texture_top_or_explicit_user_supplied_map",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=official_source,
        )
        for name, label in labels_by_name.items()
    ]


def _mat_texture_map_semantics(
    op_type: str,
    official_source: str,
    name: str,
    label: str,
    *,
    include_sampling_controls: bool = False,
    include_sampling_mode: bool = False,
    include_channel_source: bool = False,
) -> list[ParamSemantics]:
    items = _mat_top_map_semantics(op_type, official_source, {name: label})
    if include_sampling_controls:
        items.extend(
            [
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}extendu",
                    label=f"{label} Extend U",
                    value_kind="enum",
                    enum_values=_TOP_EXTEND_VALUES,
                    default_strategy="hold_texture_edges_unless_tiling_is_requested",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}extendv",
                    label=f"{label} Extend V",
                    value_kind="enum",
                    enum_values=_TOP_EXTEND_VALUES,
                    default_strategy="hold_texture_edges_unless_tiling_is_requested",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}extendw",
                    label=f"{label} Extend W",
                    value_kind="enum",
                    enum_values=_TOP_EXTEND_VALUES,
                    default_strategy="hold_texture_edges_unless_tiling_is_requested",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}filter",
                    label=f"{label} Filter",
                    value_kind="enum",
                    enum_values=_GLSL_COMP_FILTER_VALUES,
                    default_strategy="linear_texture_filtering",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}anisotropy",
                    label=f"{label} Anisotropic Filter",
                    value_kind="enum",
                    enum_values=_GLSL_COMP_ANISOTROPY_VALUES,
                    default_strategy="off_unless_oblique_texture_filtering_is_needed",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}coord",
                    label=f"{label} SOP Texture Coord",
                    value_kind="enum",
                    enum_values=_MAT_TEXTURE_COORD_VALUES,
                    default_strategy="first_texture_coordinate_layer",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}coordattrib",
                    label=f"{label} POP Texture Coord Attribute",
                    value_kind="path",
                    default_strategy="explicit_pop_texture_attribute_when_using_pop_coords",
                    cook_risk="medium",
                    validation_rule="non_empty_attribute_name",
                    official_source=official_source,
                ),
                ParamSemantics(
                    op_type=op_type,
                    name=f"{name}coordinterp",
                    label=f"{label} Coord Interpolation",
                    value_kind="enum",
                    enum_values=_MAT_TEXTURE_COORD_INTERP_VALUES,
                    default_strategy="perspective_correct_texture_coordinates",
                    cook_risk="medium",
                    validation_rule="known_menu_value",
                    official_source=official_source,
                ),
            ]
        )
    if include_sampling_mode:
        items.append(
            ParamSemantics(
                op_type=op_type,
                name=f"{name}samplingmode",
                label=f"{label} Texture Sampling Mode",
                value_kind="enum",
                enum_values=_MAT_TEXTURE_SAMPLING_MODE_VALUES,
                default_strategy="regular_texture_coordinates",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=official_source,
            )
        )
    if include_channel_source:
        items.append(
            ParamSemantics(
                op_type=op_type,
                name=f"{name}channelsource",
                label=f"{label} Channel Source",
                value_kind="enum",
                enum_values=_MAT_CHANNEL_SOURCE_VALUES,
                default_strategy="luminance_for_single_channel_material_maps",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=official_source,
            )
        )
    return items


def _shared_mat_texture_sampling_mode(op_type: str, official_source: str) -> ParamSemantics:
    return ParamSemantics(
        op_type=op_type,
        name="texturesamplingmode",
        label="Texture Sampling Mode",
        value_kind="enum",
        enum_values=_MAT_TEXTURE_SAMPLING_MODE_VALUES,
        default_strategy="regular_texture_coordinates",
        cook_risk="medium",
        validation_rule="known_menu_value",
        official_source=official_source,
    )


def _pbr_mat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="pbrMAT",
            name="basecolor",
            label="Base Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="neutral_albedo_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_PBR_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="pbrMAT",
            name="alphafront",
            label="Alpha Front",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="opaque_material_alpha",
            cook_risk="medium",
            validation_rule="normalized_material_alpha",
            official_source=_PBR_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="pbrMAT",
            name="specularlevel",
            label="Specular Level",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="bounded_specular_level",
            cook_risk="medium",
            validation_rule="normalized_material_amount",
            official_source=_PBR_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="pbrMAT",
            name="metallic",
            label="Metallic",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="non_metallic_default",
            cook_risk="medium",
            validation_rule="normalized_material_amount",
            official_source=_PBR_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="pbrMAT",
            name="roughness",
            label="Roughness",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="moderate_surface_roughness",
            cook_risk="medium",
            validation_rule="normalized_material_amount",
            official_source=_PBR_MAT_DOCS,
        ),
        _shared_mat_texture_sampling_mode("pbrMAT", _PBR_MAT_DOCS),
        *_mat_texture_map_semantics(
            "pbrMAT",
            _PBR_MAT_DOCS,
            "basecolormap",
            "Base Color Map",
            include_sampling_controls=True,
        ),
        *_mat_texture_map_semantics(
            "pbrMAT",
            _PBR_MAT_DOCS,
            "roughnessmap",
            "Roughness Map",
            include_channel_source=True,
        ),
        *_mat_texture_map_semantics(
            "pbrMAT",
            _PBR_MAT_DOCS,
            "metallicmap",
            "Metallic Map",
            include_channel_source=True,
        ),
        *_mat_texture_map_semantics("pbrMAT", _PBR_MAT_DOCS, "normalmap", "Normal Map"),
        ParamSemantics(
            op_type="pbrMAT",
            name="heightmapenable",
            label="Enable Height Map",
            value_kind="bool",
            default_strategy="off_unless_parallax_height_mapping_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PBR_MAT_DOCS,
        ),
        *_mat_texture_map_semantics("pbrMAT", _PBR_MAT_DOCS, "heightmap", "Height Map"),
        ParamSemantics(
            op_type="pbrMAT",
            name="parallaxscale",
            label="Parallax Scale",
            value_kind="float",
            default_strategy="small_height_map_parallax_scale",
            cook_risk="medium",
            validation_rule="numeric_parallax_scale",
            official_source=_PBR_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="pbrMAT",
            name="parallaxocclusion",
            label="Parallax Occlusion",
            value_kind="bool",
            default_strategy="off_unless_height_map_occlusion_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PBR_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="pbrMAT",
            name="outputshader",
            label="Output Shader",
            value_kind="bool",
            default_strategy="leave_unpressed_during_generated_plans",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_PBR_MAT_DOCS,
        ),
    ]


def _phong_mat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="phongMAT",
            name="ambdiff",
            label="Ambient Diffuse",
            value_kind="bool",
            default_strategy="enabled_for_classic_lit_phong_materials",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="diff",
            label="Diffuse",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="neutral_diffuse_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="amb",
            label="Ambient",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="low_ambient_material_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="spec",
            label="Specular",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="bounded_specular_color",
            cook_risk="medium",
            validation_rule="rgb_tuple",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="emit",
            label="Emit",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="black_unlit_emission",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="shininess",
            label="Shininess",
            value_kind="float",
            default_strategy="moderate_specular_highlight",
            cook_risk="medium",
            validation_rule="numeric_shininess",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="alphafront",
            label="Alpha Front",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="opaque_material_alpha",
            cook_risk="medium",
            validation_rule="normalized_material_alpha",
            official_source=_PHONG_MAT_DOCS,
        ),
        _shared_mat_texture_sampling_mode("phongMAT", _PHONG_MAT_DOCS),
        *_mat_texture_map_semantics(
            "phongMAT",
            _PHONG_MAT_DOCS,
            "colormap",
            "Color Map",
            include_sampling_controls=True,
        ),
        *_mat_texture_map_semantics("phongMAT", _PHONG_MAT_DOCS, "diffusemap", "Diffuse Map"),
        *_mat_texture_map_semantics("phongMAT", _PHONG_MAT_DOCS, "specmap", "Specular Map"),
        *_mat_texture_map_semantics(
            "phongMAT",
            _PHONG_MAT_DOCS,
            "normalmap",
            "Normal Map",
            include_sampling_mode=True,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="heightmapenable",
            label="Enable Height Map",
            value_kind="bool",
            default_strategy="off_unless_parallax_height_mapping_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PHONG_MAT_DOCS,
        ),
        *_mat_texture_map_semantics("phongMAT", _PHONG_MAT_DOCS, "heightmap", "Height Map"),
        ParamSemantics(
            op_type="phongMAT",
            name="parallaxscale",
            label="Parallax Scale",
            value_kind="float",
            default_strategy="small_height_map_parallax_scale",
            cook_risk="medium",
            validation_rule="numeric_parallax_scale",
            official_source=_PHONG_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="phongMAT",
            name="parallaxocclusion",
            label="Parallax Occlusion",
            value_kind="bool",
            default_strategy="off_unless_height_map_occlusion_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_PHONG_MAT_DOCS,
        ),
        *_mat_texture_map_semantics("phongMAT", _PHONG_MAT_DOCS, "envmap", "Environment Map"),
        ParamSemantics(
            op_type="phongMAT",
            name="outputshader",
            label="Output Shader",
            value_kind="bool",
            default_strategy="leave_unpressed_during_generated_plans",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_PHONG_MAT_DOCS,
        ),
    ]


def _common_pop_semantics(op_type: str, official_source: str) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name="bypass",
            label="Bypass",
            value_kind="bool",
            default_strategy="leave_off_for_generated_pop_processing",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=official_source,
        ),
        ParamSemantics(
            op_type=op_type,
            name="delinputattrs",
            label="Delete Input Attributes",
            value_kind="bool",
            default_strategy="keep_input_attributes_unless_isolation_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=official_source,
        ),
    ]


def _circle_pop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="circlePOP",
            name="connectivity",
            label="Connectivity",
            value_kind="enum",
            enum_values=_CIRCLE_CONNECTIVITY_VALUES,
            default_strategy="line_strip_or_surface_for_renderable_circle",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CIRCLE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="orient",
            label="Orientation",
            value_kind="enum",
            enum_values=_CIRCLE_ORIENT_VALUES,
            default_strategy="xy_plane_for_2d_pop_sources",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_CIRCLE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="modifybounds",
            label="Modify Bounds",
            value_kind="bool",
            default_strategy="off_unless_input_bounds_drive_shape",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_CIRCLE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="rad",
            label="Radius",
            value_kind="tuple",
            tuple_size=2,
            valid_range=(0.0, 100000.0),
            default_strategy="positive_radius_tuple",
            cook_risk="medium",
            validation_rule="two_axis_radius_tuple",
            official_source=_CIRCLE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="divs",
            label="Divisions",
            value_kind="int",
            valid_range=(1.0, 100000.0),
            default_strategy="bounded_circle_divisions",
            cook_risk="high",
            validation_rule="positive_pop_element_count",
            official_source=_CIRCLE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="closed",
            label="Closed",
            value_kind="bool",
            default_strategy="closed_for_full_circles_open_for_arcs",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_CIRCLE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="angle",
            label="Arc Angles",
            value_kind="tuple",
            tuple_size=2,
            unit="degrees",
            default_strategy="full_circle_angle_range",
            cook_risk="low",
            validation_rule="two_angle_tuple",
            official_source=_CIRCLE_POP_DOCS,
        ),
        *_pop_tuple_semantics(
            "circlePOP",
            _CIRCLE_POP_DOCS,
            {
                "t": ("Translate", "translate_points"),
                "r": ("Rotate", "rotate_points_degrees"),
            },
            tuple_size=3,
            cook_risk="medium",
        ),
        ParamSemantics(
            op_type="circlePOP",
            name="scale",
            label="Uniform Scale",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="positive_uniform_scale",
            cook_risk="medium",
            validation_rule="non_negative_uniform_scale",
            official_source=_CIRCLE_POP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="circlePOP",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_CIRCLE_ATTRIBUTE_OUTPUT_VALUES,
                default_strategy="create_attributes_only_when_downstream_render_or_shader_needs_them",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=_CIRCLE_POP_DOCS,
            )
            for name, label in {
                "normal": "Normal",
                "tangent": "Tangent",
                "texture": "Texture Coordinates",
            }.items()
        ],
        *_common_pop_semantics("circlePOP", _CIRCLE_POP_DOCS),
    ]


def _noise_pop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="noisePOP",
            name="type",
            label="Type",
            value_kind="enum",
            enum_values=_NOISE_TYPE_VALUES,
            default_strategy="simplex_or_perlin_3d_for_spatial_fields",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="noisesize",
            label="Noise Size",
            value_kind="enum",
            enum_values=_NOISE_SIZE_VALUES,
            default_strategy="match_noise_output_components_to_target_attribute",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="harmon",
            label="Harmonics",
            value_kind="int",
            valid_range=(0.0, 10000.0),
            default_strategy="small_harmonic_count_for_stable_pop_motion",
            cook_risk="high",
            validation_rule="non_negative_harmonics",
            official_source=_NOISE_POP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="noisePOP",
                name=name,
                label=label,
                value_kind="float",
                valid_range=(0.0, 100000.0),
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule="non_negative_noise_parameter",
                official_source=_NOISE_POP_DOCS,
            )
            for name, label, default_strategy in [
                ("period", "Period", "positive_noise_period"),
                ("spread", "Harmonic Spread", "bounded_harmonic_spread"),
                ("gain", "Harmonic Gain", "bounded_harmonic_gain"),
                ("amp", "Amplitude", "bounded_noise_amplitude"),
                ("exp", "Exponent", "bounded_noise_exponent"),
                ("t4d", "Translate 4D", "numeric_fourth_dimension_offset"),
            ]
        ],
        ParamSemantics(
            op_type="noisePOP",
            name="attrclass",
            label="Attribute Class",
            value_kind="enum",
            enum_values=_POP_ATTRIBUTE_CLASS_VALUES,
            default_strategy="point_attributes_for_pop_motion",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="xord",
            label="Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_predictable_noise_space",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="rord",
            label="Rotate Order",
            value_kind="enum",
            enum_values=_ROTATE_ORDER_VALUES,
            default_strategy="xyz_rotation_order",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        *_pop_tuple_semantics(
            "noisePOP",
            _NOISE_POP_DOCS,
            {
                "t": ("Translate", "translate_noise_space"),
                "r": ("Rotate", "rotate_noise_space_degrees"),
                "s": ("Scale", "scale_noise_space"),
                "p": ("Pivot", "pivot_noise_space"),
            },
            tuple_size=3,
            cook_risk="medium",
        ),
        *[
            ParamSemantics(
                op_type="noisePOP",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy="off_unless_debug_or_attribute_output_is_required",
                cook_risk="medium",
                validation_rule="bool_toggle",
                official_source=_NOISE_POP_DOCS,
            )
            for name, label in {
                "noise": "Noise",
                "gradient": "Gradient",
                "curl3d": "Curl 3D",
                "curl2d": "Curl 2D",
                "computenormals": "Compute Point Normals",
            }.items()
        ],
        ParamSemantics(
            op_type="noisePOP",
            name="combineop",
            label="Combine Operation",
            value_kind="enum",
            enum_values=_NOISE_COMBINE_VALUES,
            default_strategy="add_noise_to_target_attribute",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="combineentity",
            label="Combine Entity",
            value_kind="enum",
            enum_values=_NOISE_COMBINE_ENTITY_VALUES,
            default_strategy="noise_entity_for_standard_displacement",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="attrnumcomps",
            label="Attribute Components",
            value_kind="enum",
            enum_values=_NOISE_SIZE_VALUES,
            default_strategy="match_output_attribute_component_count",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="attrtype",
            label="Attribute Type",
            value_kind="enum",
            enum_values=_NOISE_ATTR_TYPE_VALUES,
            default_strategy="float_for_generated_noise_attributes",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="mode",
            label="Mode",
            value_kind="enum",
            enum_values=_NOISE_MODE_VALUES,
            default_strategy="performance_for_preview_quality_for_final",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="map0op",
            label="Map Source OP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="input_pop_for_per_point_parameter_mapping",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="map0parm",
            label="Mapped Target Parameter",
            value_kind="enum",
            enum_values=_NOISE_MAP_PARM_VALUES,
            default_strategy="map_only_documented_noise_parameters",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="noisePOP",
            name="map0combineop",
            label="Map Combine Operation",
            value_kind="enum",
            enum_values=_MAP_COMBINE_VALUES,
            default_strategy="set_or_add_mapped_parameter_values",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_NOISE_POP_DOCS,
        ),
        *_common_pop_semantics("noisePOP", _NOISE_POP_DOCS),
    ]


def _math_mix_pop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="mathmixPOP",
            name="lengthmismatchnotif",
            label="Length Mismatch",
            value_kind="enum",
            enum_values=_LENGTH_MISMATCH_NOTIF_VALUES,
            default_strategy="warning_for_length_mismatch_until_validated",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="input0pop",
            label="Input POP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="created_pop_input_for_secondary_attributes",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="attrclass",
            label="Attribute Class",
            value_kind="enum",
            enum_values=_POP_ATTRIBUTE_CLASS_VALUES,
            default_strategy="point_attributes_for_generated_math",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="angleunit",
            label="Angle Units",
            value_kind="enum",
            enum_values=_ANGLE_UNIT_VALUES,
            default_strategy="degrees_for_artist_facing_controls",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="vec0type",
            label="Vector Uniform Type",
            value_kind="enum",
            enum_values=_MATH_MIX_VEC_TYPE_VALUES,
            default_strategy="float_or_float3_for_generated_pop_uniforms",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="vec0value",
            label="Vector Uniform Value",
            value_kind="tuple",
            tuple_size=4,
            default_strategy="four_component_uniform_value",
            cook_risk="medium",
            validation_rule="vec4_uniform_tuple",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="premultcolor",
            label="Pre-Multiply RGB by Alpha",
            value_kind="bool",
            default_strategy="off_unless_color_uniform_alpha_requires_premultiply",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="color0rgb",
            label="Color Uniform RGB",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_color_uniform",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="color0alpha",
            label="Color Uniform Alpha",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="opaque_color_uniform_alpha",
            cook_risk="low",
            validation_rule="normalized_alpha",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="comb0oper",
            label="Combine Operation",
            value_kind="enum",
            enum_values=_MATH_MIX_COMBINE_VALUES,
            default_strategy="documented_math_mix_operation",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        ParamSemantics(
            op_type="mathmixPOP",
            name="delnewattrs",
            label="Delete New Attributes",
            value_kind="bool",
            default_strategy="keep_generated_attributes_for_debuggability",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_MATH_MIX_POP_DOCS,
        ),
        *_common_pop_semantics("mathmixPOP", _MATH_MIX_POP_DOCS),
    ]


def _attribute_combine_pop_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="attributecombinePOP",
            name="attrclass",
            label="Attribute Class",
            value_kind="enum",
            enum_values=_POP_ATTRIBUTE_CLASS_VALUES,
            default_strategy="point_attributes_for_generated_combine",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_ATTRIBUTE_COMBINE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="attributecombinePOP",
            name="lengthmismatchnotif",
            label="Length Mismatch",
            value_kind="enum",
            enum_values=_LENGTH_MISMATCH_NOTIF_VALUES,
            default_strategy="warning_for_length_mismatch_until_validated",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_ATTRIBUTE_COMBINE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="attributecombinePOP",
            name="duplicateattrs",
            label="Duplicate Attributes",
            value_kind="enum",
            enum_values=_ATTRIBUTE_COMBINE_DUPLICATE_VALUES,
            default_strategy="auto_rename_to_preserve_sources",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_ATTRIBUTE_COMBINE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="attributecombinePOP",
            name="input0pop",
            label="Input POP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="created_pop_input_for_attribute_merge",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_ATTRIBUTE_COMBINE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="attributecombinePOP",
            name="input0attrs",
            label="Input Attributes",
            value_kind="string",
            default_strategy="explicit_attribute_scope_or_wildcard",
            cook_risk="medium",
            validation_rule="attribute_scope_string",
            official_source=_ATTRIBUTE_COMBINE_POP_DOCS,
        ),
        ParamSemantics(
            op_type="attributecombinePOP",
            name="input0renameto",
            label="Rename To",
            value_kind="string",
            default_strategy="rename_only_when_avoiding_attribute_collisions",
            cook_risk="medium",
            validation_rule="attribute_rename_string",
            official_source=_ATTRIBUTE_COMBINE_POP_DOCS,
        ),
        *_common_pop_semantics("attributecombinePOP", _ATTRIBUTE_COMBINE_POP_DOCS),
    ]


def _pop_tuple_semantics(
    op_type: str,
    official_source: str,
    labels_by_name: dict[str, tuple[str, str]],
    *,
    tuple_size: int,
    cook_risk: str,
) -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name=name,
            label=label,
            value_kind="tuple",
            tuple_size=tuple_size,
            default_strategy=default_strategy,
            cook_risk=cook_risk,
            validation_rule=f"{tuple_size}_component_tuple",
            official_source=official_source,
        )
        for name, (label, default_strategy) in labels_by_name.items()
    ]


def _geometry_comp_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="geometryCOMP",
            name="sop",
            label="Geometry SOP",
            value_kind="op_ref",
            expected_family="SOP",
            default_strategy="created_stable_sop_output",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="xord",
            label="Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_predictable_object_motion",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="rord",
            label="Rotate Order",
            value_kind="enum",
            enum_values=_ROTATION_ORDER_VALUES,
            default_strategy="xyz_rotation_order_for_generated_object_transforms",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="geometryCOMP",
                name=name,
                label=label,
                value_kind="tuple",
                tuple_size=3,
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule="xyz_tuple",
                official_source=_GEOMETRY_COMP_DOCS,
            )
            for name, label, default_strategy in (
                ("t", "Translate", "three_axis_object_translation"),
                ("r", "Rotate", "three_axis_object_rotation_degrees"),
                ("p", "Pivot", "three_axis_object_pivot"),
                ("up", "Orient Up Vector", "three_axis_path_or_lookat_up_vector"),
            )
        ],
        ParamSemantics(
            op_type="geometryCOMP",
            name="s",
            label="Scale",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.001, 100000.0),
            default_strategy="positive_three_axis_object_scale",
            cook_risk="medium",
            validation_rule="positive_xyz_scale_tuple",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="scale",
            label="Uniform Scale",
            value_kind="float",
            valid_range=(0.001, 100000.0),
            default_strategy="positive_uniform_object_scale",
            cook_risk="medium",
            validation_rule="positive_uniform_scale",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="parentxformsrc",
            label="Parent Transform Source",
            value_kind="enum",
            enum_values=_COMP_PARENT_XFORM_SOURCE_VALUES,
            default_strategy="inherit_parent_hierarchy_for_generated_object_comps",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="parentobject",
            label="Parent Object",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_parent_object_comp_when_constraint_is_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="lookat",
            label="Look At COMP",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_focus_or_target_comp_for_object_orientation",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="forwarddir",
            label="Forward Direction",
            value_kind="enum",
            enum_values=_COMP_FORWARD_DIRECTION_VALUES,
            default_strategy="positive_z_forward_for_generated_geometry",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="lookup",
            label="Look At Up Vector",
            value_kind="enum",
            enum_values=_COMP_LOOK_AT_UP_VALUES,
            default_strategy="disable_up_vector_unless_lookat_path_needs_roll_control",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="pathsop",
            label="Path SOP",
            value_kind="op_ref",
            expected_family="SOP",
            default_strategy="created_path_sop_when_path_animation_is_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="roll",
            label="Roll",
            value_kind="float",
            unit="degrees",
            default_strategy="zero_roll_unless_path_or_lookat_requires_banking",
            cook_risk="medium",
            validation_rule="numeric_roll_degrees",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="pos",
            label="Position Along Path",
            value_kind="float",
            valid_range=(0.0, 10.0),
            default_strategy="bounded_path_position",
            cook_risk="medium",
            validation_rule="bounded_path_position",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="pathorient",
            label="Orient Along Path",
            value_kind="bool",
            default_strategy="off_unless_path_sop_motion_should_drive_orientation",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="bank",
            label="Auto-Bank Factor",
            value_kind="float",
            default_strategy="zero_auto_bank_until_path_motion_requires_roll",
            cook_risk="medium",
            validation_rule="numeric_bank_factor",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="instancing",
            label="Instancing",
            value_kind="bool",
            default_strategy="off_until_instance_source_data_is_available",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="instancecountmode",
            label="Instance Count Mode",
            value_kind="enum",
            enum_values=_GEOMETRY_INSTANCE_COUNT_MODE_VALUES,
            default_strategy="derive_count_from_instance_ops_when_source_data_is_present",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="numinstances",
            label="Num Instances",
            value_kind="int",
            unit="instances",
            valid_range=(1.0, 1_000_000_000.0),
            default_strategy="small_manual_instance_count_until_source_data_is_verified",
            cook_risk="high",
            validation_rule="warn_large_instance_count",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="instanceop",
            label="Default Instance OP",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="created_chop_or_dat_instance_source",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="instancefirstrow",
            label="First Row Is",
            value_kind="enum",
            enum_values=_GEOMETRY_INSTANCE_FIRST_ROW_VALUES,
            default_strategy="names_when_instance_dat_has_header_row",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="instxord",
            label="Instance Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_instance_transforms",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="instrord",
            label="Instance Rotate Order",
            value_kind="enum",
            enum_values=_ROTATION_ORDER_VALUES,
            default_strategy="xyz_rotation_order_for_instance_transforms",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="geometryCOMP",
                name=name,
                label=label,
                value_kind="op_ref",
                expected_family="ANY",
                default_strategy="explicit_instance_attribute_source_or_default_instance_op",
                cook_risk="high",
                validation_rule="non_empty_operator_reference",
                official_source=_GEOMETRY_COMP_DOCS,
            )
            for name, label in (
                ("instancetop", "Translate OP"),
                ("instancerop", "Rotate OP"),
                ("instancesop", "Scale OP"),
                ("instancepop", "Pivot OP"),
            )
        ],
        ParamSemantics(
            op_type="geometryCOMP",
            name="material",
            label="Material MAT",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="created_material_mat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="render",
            label="Render",
            value_kind="bool",
            default_strategy="enabled_for_geometry_that_should_appear_in_render_top",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="drawpriority",
            label="Draw Priority",
            value_kind="float",
            default_strategy="default_draw_priority_until_explicit_ordering_is_required",
            cook_risk="medium",
            validation_rule="numeric_draw_priority",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="pickpriority",
            label="Pick Priority",
            value_kind="float",
            default_strategy="default_pick_priority_until_render_picking_needs_ordering",
            cook_risk="medium",
            validation_rule="numeric_pick_priority",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="wcolor",
            label="Wireframe Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_wireframe_display_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="geometryCOMP",
            name="lightmask",
            label="Light Mask",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="lightCOMP",
            default_strategy="created_light_comps_when_geometry_uses_light_mask",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_GEOMETRY_COMP_DOCS,
        ),
    ]


def _camera_comp_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="cameraCOMP",
            name="xord",
            label="Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_predictable_camera_motion",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="rord",
            label="Rotate Order",
            value_kind="enum",
            enum_values=_ROTATION_ORDER_VALUES,
            default_strategy="xyz_rotation_order_for_generated_camera_transforms",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="cameraCOMP",
                name=name,
                label=label,
                value_kind="tuple",
                tuple_size=3,
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule="xyz_tuple",
                official_source=_CAMERA_COMP_DOCS,
            )
            for name, label, default_strategy in (
                ("t", "Translate", "three_axis_camera_translation"),
                ("r", "Rotate", "three_axis_camera_rotation_degrees"),
                ("p", "Pivot", "three_axis_camera_pivot"),
                ("up", "Orient Up Vector", "three_axis_path_or_lookat_up_vector"),
            )
        ],
        ParamSemantics(
            op_type="cameraCOMP",
            name="s",
            label="Scale",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.001, 100000.0),
            default_strategy="positive_three_axis_camera_scale",
            cook_risk="high",
            validation_rule="positive_xyz_scale_tuple",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="scale",
            label="Uniform Scale",
            value_kind="float",
            valid_range=(0.001, 100000.0),
            default_strategy="positive_uniform_camera_scale",
            cook_risk="high",
            validation_rule="positive_uniform_scale",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="parentxformsrc",
            label="Parent Transform Source",
            value_kind="enum",
            enum_values=_COMP_PARENT_XFORM_SOURCE_VALUES,
            default_strategy="inherit_parent_hierarchy_for_generated_camera_comps",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="parentobject",
            label="Parent Object",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_parent_object_comp_when_camera_constraint_is_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="lookat",
            label="Look At COMP",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_null_or_geometry_comp_focus_target",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="forwarddir",
            label="Forward Direction",
            value_kind="enum",
            enum_values=_COMP_FORWARD_DIRECTION_VALUES,
            default_strategy="negative_z_forward_for_generated_cameras",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="lookup",
            label="Look At Up Vector",
            value_kind="enum",
            enum_values=_COMP_LOOK_AT_UP_VALUES,
            default_strategy="disable_up_vector_unless_lookat_path_needs_roll_control",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="pathsop",
            label="Path SOP",
            value_kind="op_ref",
            expected_family="SOP",
            default_strategy="created_camera_path_sop_when_path_animation_is_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="roll",
            label="Roll",
            value_kind="float",
            unit="degrees",
            default_strategy="zero_roll_unless_path_or_lookat_requires_banking",
            cook_risk="medium",
            validation_rule="numeric_roll_degrees",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="pos",
            label="Position Along Path",
            value_kind="float",
            valid_range=(0.0, 10.0),
            default_strategy="bounded_path_position",
            cook_risk="medium",
            validation_rule="bounded_path_position",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="pathorient",
            label="Orient Along Path",
            value_kind="bool",
            default_strategy="off_unless_path_sop_motion_should_drive_camera_orientation",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="bank",
            label="Auto-Bank Factor",
            value_kind="float",
            default_strategy="zero_auto_bank_until_path_motion_requires_roll",
            cook_risk="medium",
            validation_rule="numeric_bank_factor",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="projection",
            label="Projection",
            value_kind="enum",
            enum_values=_CAMERA_PROJECTION_VALUES,
            default_strategy="perspective_for_general_render_pipelines",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="projectionblend",
            label="Projection Blend",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="bounded_perspective_to_ortho_blend",
            cook_risk="medium",
            validation_rule="normalized_projection_blend",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="orthowidth",
            label="Ortho Width",
            value_kind="float",
            valid_range=(0.001, 100000.0),
            default_strategy="positive_orthographic_width",
            cook_risk="medium",
            validation_rule="positive_orthographic_width",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="viewanglemethod",
            label="Viewing Angle Method",
            value_kind="enum",
            enum_values=_CAMERA_VIEW_ANGLE_METHOD_VALUES,
            default_strategy="horizontal_fov_for_general_render_pipelines",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fov",
            label="FOV Angle",
            value_kind="float",
            unit="degrees",
            valid_range=(1.0, 179.0),
            default_strategy="moderate_camera_field_of_view",
            cook_risk="medium",
            validation_rule="numeric_field_of_view",
            official_source=_CAMERA_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="cameraCOMP",
                name=name,
                label=label,
                value_kind="float",
                unit=unit,
                valid_range=(0.001, 100000.0),
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule=validation_rule,
                official_source=_CAMERA_COMP_DOCS,
            )
            for name, label, unit, default_strategy, validation_rule in (
                ("focal", "Focal Length", "distance", "positive_focal_length", "numeric_focal_length"),
                ("aperture", "Aperture", "distance", "positive_camera_aperture", "numeric_aperture"),
                ("near", "Near", "distance", "positive_near_clipping_plane", "numeric_near_clip"),
                ("far", "Far", "distance", "positive_far_clipping_plane", "numeric_far_clip"),
            )
        ],
        ParamSemantics(
            op_type="cameraCOMP",
            name="winrollpivot",
            label="Window Roll Pivot",
            value_kind="enum",
            enum_values=_CAMERA_WIN_ROLL_PIVOT_VALUES,
            default_strategy="viewport_origin_for_window_roll",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="win",
            label="Window X/Y",
            value_kind="tuple",
            tuple_size=2,
            default_strategy="centered_render_window",
            cook_risk="medium",
            validation_rule="xy_tuple",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="winsize",
            label="Window Size",
            value_kind="float",
            valid_range=(0.001, 100000.0),
            default_strategy="positive_window_zoom_size",
            cook_risk="medium",
            validation_rule="positive_window_size",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="winroll",
            label="Window Roll",
            value_kind="float",
            unit="degrees",
            default_strategy="zero_window_roll_until_requested",
            cook_risk="medium",
            validation_rule="numeric_window_roll_degrees",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="ipdshift",
            label="IPD Shift",
            value_kind="float",
            unit="distance",
            default_strategy="zero_ipd_shift_for_mono_camera",
            cook_risk="medium",
            validation_rule="numeric_ipd_shift",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="projmatrixop",
            label="Proj Matrix/CHOP/DAT",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="created_projection_matrix_chop_or_dat_when_custom_matrix_is_requested",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="customproj",
            label="Custom Projection GLSL DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_custom_projection_text_dat_if_custom_projection_is_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="quadreprojsop",
            label="Quad Reproject SOP",
            value_kind="op_ref",
            expected_family="SOP",
            default_strategy="created_quad_reprojection_sop_when_reprojection_is_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="quadreprojpts",
            label="Quad Reproject Points",
            value_kind="tuple",
            tuple_size=4,
            default_strategy="four_point_quad_reprojection_order",
            cook_risk="high",
            validation_rule="quad_point_index_tuple",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="bgcolor",
            label="Background Color",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_camera_background_rgba",
            cook_risk="low",
            validation_rule="rgba_tuple",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="premultrgbbyalpha",
            label="Pre-Multiply RGB by Alpha",
            value_kind="bool",
            default_strategy="off_unless_premultiplied_camera_background_is_required",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fog",
            label="Fog",
            value_kind="enum",
            enum_values=_CAMERA_FOG_VALUES,
            default_strategy="off_unless_scene_fog_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fogdensity",
            label="Fog Density",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="non_negative_fog_density",
            cook_risk="medium",
            validation_rule="non_negative_fog_density",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fognear",
            label="Fog Near",
            value_kind="float",
            unit="distance",
            valid_range=(0.0, 100000.0),
            default_strategy="non_negative_linear_fog_start_distance",
            cook_risk="medium",
            validation_rule="non_negative_fog_near",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fogfar",
            label="Fog Far",
            value_kind="float",
            unit="distance",
            valid_range=(0.0, 100000.0),
            default_strategy="non_negative_linear_fog_end_distance",
            cook_risk="medium",
            validation_rule="non_negative_fog_far",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fogcolor",
            label="Fog Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_fog_rgb_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fogalpha",
            label="Fog Alpha",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="normalized_fog_alpha",
            cook_risk="medium",
            validation_rule="normalized_alpha",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="fogmap",
            label="Fog Map TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_top_texture_when_fog_map_is_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="camlightmask",
            label="Camera Light Mask",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="lightCOMP",
            default_strategy="created_light_comps_when_camera_uses_light_mask",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="material",
            label="Material MAT",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="created_material_mat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="render",
            label="Render",
            value_kind="bool",
            default_strategy="enabled_for_camera_component_geometry_that_should_render",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="drawpriority",
            label="Draw Priority",
            value_kind="float",
            default_strategy="default_draw_priority_until_explicit_ordering_is_required",
            cook_risk="medium",
            validation_rule="numeric_draw_priority",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="pickpriority",
            label="Pick Priority",
            value_kind="float",
            default_strategy="default_pick_priority_until_render_picking_needs_ordering",
            cook_risk="medium",
            validation_rule="numeric_pick_priority",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="wcolor",
            label="Wireframe Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_wireframe_display_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_CAMERA_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="cameraCOMP",
            name="lightmask",
            label="Light Mask",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="lightCOMP",
            default_strategy="created_light_comps_when_camera_component_geometry_uses_light_mask",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_CAMERA_COMP_DOCS,
        ),
    ]


def _light_comp_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="lightCOMP",
            name="xord",
            label="Transform Order",
            value_kind="enum",
            enum_values=_TRANSFORM_ORDER_VALUES,
            default_strategy="scale_rotate_translate_for_predictable_light_motion",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="rord",
            label="Rotate Order",
            value_kind="enum",
            enum_values=_ROTATION_ORDER_VALUES,
            default_strategy="xyz_rotation_order_for_generated_light_transforms",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="lightCOMP",
                name=name,
                label=label,
                value_kind="tuple",
                tuple_size=3,
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule="xyz_tuple",
                official_source=_LIGHT_COMP_DOCS,
            )
            for name, label, default_strategy in (
                ("t", "Translate", "three_axis_light_translation"),
                ("r", "Rotate", "three_axis_light_rotation_degrees"),
                ("p", "Pivot", "three_axis_light_pivot"),
                ("up", "Orient Up Vector", "three_axis_path_or_lookat_up_vector"),
            )
        ],
        ParamSemantics(
            op_type="lightCOMP",
            name="s",
            label="Scale",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.001, 100000.0),
            default_strategy="positive_three_axis_light_scale",
            cook_risk="high",
            validation_rule="positive_xyz_scale_tuple",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="scale",
            label="Uniform Scale",
            value_kind="float",
            valid_range=(0.001, 100000.0),
            default_strategy="positive_uniform_light_scale",
            cook_risk="high",
            validation_rule="positive_uniform_scale",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="parentxformsrc",
            label="Parent Transform Source",
            value_kind="enum",
            enum_values=_COMP_PARENT_XFORM_SOURCE_VALUES,
            default_strategy="inherit_parent_hierarchy_for_generated_light_comps",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="parentobject",
            label="Parent Object",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_parent_object_comp_when_light_constraint_is_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="lookat",
            label="Look At COMP",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_focus_or_target_comp_for_light_orientation",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="forwarddir",
            label="Forward Direction",
            value_kind="enum",
            enum_values=_COMP_FORWARD_DIRECTION_VALUES,
            default_strategy="positive_z_forward_for_generated_lights",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="lookup",
            label="Look At Up Vector",
            value_kind="enum",
            enum_values=_COMP_LOOK_AT_UP_VALUES,
            default_strategy="disable_up_vector_unless_lookat_path_needs_roll_control",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="pathsop",
            label="Path SOP",
            value_kind="op_ref",
            expected_family="SOP",
            default_strategy="created_light_path_sop_when_path_animation_is_requested",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="roll",
            label="Roll",
            value_kind="float",
            unit="degrees",
            default_strategy="zero_roll_unless_path_or_lookat_requires_banking",
            cook_risk="medium",
            validation_rule="numeric_roll_degrees",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="pos",
            label="Position Along Path",
            value_kind="float",
            valid_range=(0.0, 10.0),
            default_strategy="bounded_path_position",
            cook_risk="medium",
            validation_rule="bounded_path_position",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="pathorient",
            label="Orient Along Path",
            value_kind="bool",
            default_strategy="off_unless_path_sop_motion_should_drive_light_orientation",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="bank",
            label="Auto-Bank Factor",
            value_kind="float",
            default_strategy="zero_auto_bank_until_path_motion_requires_roll",
            cook_risk="medium",
            validation_rule="numeric_bank_factor",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="c",
            label="Light Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_light_rgb_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="dimmer",
            label="Dimmer",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="visible_light_with_safe_compute",
            cook_risk="medium",
            validation_rule="numeric_dimmer",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="lighttype",
            label="Light Type",
            value_kind="enum",
            enum_values=_LIGHT_COMP_TYPES,
            default_strategy="point_or_cone_for_small_scenes",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="coneangle",
            label="Cone Angle",
            value_kind="float",
            unit="degrees",
            valid_range=(0.0, 180.0),
            default_strategy="bounded_cone_spotlight_angle",
            cook_risk="medium",
            validation_rule="bounded_cone_angle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="conedelta",
            label="Cone Delta",
            value_kind="float",
            unit="degrees",
            valid_range=(0.0, 180.0),
            default_strategy="bounded_cone_falloff_angle",
            cook_risk="medium",
            validation_rule="bounded_cone_delta",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="coneroll",
            label="Cone Rolloff",
            value_kind="float",
            valid_range=(1.0, 10.0),
            default_strategy="moderate_cone_rolloff",
            cook_risk="medium",
            validation_rule="bounded_cone_rolloff",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="attenuated",
            label="Distance-Attenuated",
            value_kind="bool",
            default_strategy="off_unless_distance_falloff_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="lightCOMP",
                name=name,
                label=label,
                value_kind="float",
                unit="distance" if "attenuation" in name else None,
                valid_range=(0.0, 100000.0),
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule=validation_rule,
                official_source=_LIGHT_COMP_DOCS,
            )
            for name, label, default_strategy, validation_rule in (
                (
                    "attenuationstart",
                    "Attenuation Start",
                    "non_negative_light_attenuation_start",
                    "non_negative_attenuation_start",
                ),
                (
                    "attenuationend",
                    "Attenuation End",
                    "non_negative_light_attenuation_end",
                    "non_negative_attenuation_end",
                ),
                (
                    "attenuationexp",
                    "Attenuation Rolloff",
                    "non_negative_light_attenuation_rolloff",
                    "non_negative_attenuation_rolloff",
                ),
            )
        ],
        ParamSemantics(
            op_type="lightCOMP",
            name="projmaptype",
            label="Projector Map Type",
            value_kind="enum",
            enum_values=_LIGHT_PROJECTOR_MAP_TYPE_VALUES,
            default_strategy="spot_projector_map_for_cone_lights",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="projmap",
            label="Projector Map TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_projector_texture_top_when_needed",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="lightCOMP",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_TOP_EXTEND_VALUES,
                default_strategy="hold_projector_map_edges",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=_LIGHT_COMP_DOCS,
            )
            for name, label in (
                ("projmapextendu", "Projector Map Extend U"),
                ("projmapextendv", "Projector Map Extend V"),
                ("projmapextendw", "Projector Map Extend W"),
            )
        ],
        ParamSemantics(
            op_type="lightCOMP",
            name="projmapfilter",
            label="Projector Map Filter",
            value_kind="enum",
            enum_values=_GLSL_COMP_FILTER_VALUES,
            default_strategy="linear_projector_map_filtering",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="projmapanisotropy",
            label="Projector Map Anisotropic Filter",
            value_kind="enum",
            enum_values=_GLSL_COMP_ANISOTROPY_VALUES,
            default_strategy="off_unless_projector_map_needs_oblique_filtering",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="projmapmode",
            label="Projector Map Mode",
            value_kind="enum",
            enum_values=_LIGHT_PROJECTOR_MAP_MODE_VALUES,
            default_strategy="simple_horizontal_fov_until_view_settings_are_needed",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="projangle",
            label="Projector Angle",
            value_kind="float",
            unit="degrees",
            valid_range=(0.0, 180.0),
            default_strategy="bounded_projector_spread_angle",
            cook_risk="medium",
            validation_rule="bounded_projector_angle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="lightCOMP",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_LIGHT_FACE_LIT_VALUES,
                default_strategy="front_lit_normals_for_two_sided_lighting",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=_LIGHT_COMP_DOCS,
            )
            for name, label in (
                ("frontfacelit", "Polygon Front Faces"),
                ("backfacelit", "Polygon Back Faces"),
            )
        ],
        ParamSemantics(
            op_type="lightCOMP",
            name="shadowtype",
            label="Shadow Type",
            value_kind="enum",
            enum_values=_LIGHT_SHADOW_TYPE_VALUES,
            default_strategy="off_until_shadow_casters_and_resolution_are_selected",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="shadowcasters",
            label="Shadow Caster Geometry COMPs",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="geometryCOMP",
            default_strategy="created_geometry_comp_shadow_casters",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="lightsize",
            label="Light Size",
            value_kind="tuple",
            tuple_size=2,
            valid_range=(0.0, 100000.0),
            default_strategy="non_negative_soft_shadow_light_size",
            cook_risk="high",
            validation_rule="xy_tuple",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="maxshadowsoftness",
            label="Max Shadow Softness",
            value_kind="float",
            valid_range=(0.0, 100000.0),
            default_strategy="non_negative_shadow_softness",
            cook_risk="high",
            validation_rule="non_negative_shadow_softness",
            official_source=_LIGHT_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="lightCOMP",
                name=name,
                label=label,
                value_kind="int",
                valid_range=(1.0, 1024.0),
                default_strategy=default_strategy,
                cook_risk="high",
                validation_rule=validation_rule,
                official_source=_LIGHT_COMP_DOCS,
            )
            for name, label, default_strategy, validation_rule in (
                (
                    "filtersamples",
                    "Filter Samples",
                    "small_shadow_filter_sample_count",
                    "positive_shadow_filter_samples",
                ),
                (
                    "searchsteps",
                    "Search Steps",
                    "small_shadow_search_step_count",
                    "positive_shadow_search_steps",
                ),
            )
        ],
        ParamSemantics(
            op_type="lightCOMP",
            name="polygonoffsetfactor",
            label="Polygon Offset Factor",
            value_kind="float",
            default_strategy="default_shadow_polygon_offset_factor",
            cook_risk="medium",
            validation_rule="numeric_polygon_offset_factor",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="polygonoffsetunits",
            label="Polygon Offset Units",
            value_kind="float",
            default_strategy="default_shadow_polygon_offset_units",
            cook_risk="medium",
            validation_rule="numeric_polygon_offset_units",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="shadowresolution",
            label="Shadow Resolution",
            value_kind="tuple",
            tuple_size=2,
            valid_range=(1.0, 4096.0),
            default_strategy="bounded_shadow_map_resolution",
            cook_risk="high",
            validation_rule="warn_high_resolution",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="shadowmap",
            label="Custom Shadow Map TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_shadow_map_top_when_custom_shadows_are_enabled",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="projection",
            label="Projection",
            value_kind="enum",
            enum_values=_LIGHT_PROJECTION_VALUES,
            default_strategy="perspective_when_viewing_through_light",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="aspectcorrect",
            label="Aspect Correct Projection",
            value_kind="bool",
            default_strategy="enabled_for_light_camera_view",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="orthowidth",
            label="Ortho Width",
            value_kind="float",
            valid_range=(0.001, 100000.0),
            default_strategy="positive_light_orthographic_width",
            cook_risk="medium",
            validation_rule="positive_orthographic_width",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="useconeforfov",
            label="Use Cone Angle/Delta for FOV",
            value_kind="bool",
            default_strategy="off_unless_cone_light_fov_should_drive_view",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="viewanglemethod",
            label="Viewing Angle Method",
            value_kind="enum",
            enum_values=_CAMERA_VIEW_ANGLE_METHOD_VALUES,
            default_strategy="horizontal_fov_for_light_view",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="fov",
            label="FOV Angle",
            value_kind="float",
            unit="degrees",
            valid_range=(1.0, 179.0),
            default_strategy="moderate_light_view_field_of_view",
            cook_risk="medium",
            validation_rule="numeric_field_of_view",
            official_source=_LIGHT_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="lightCOMP",
                name=name,
                label=label,
                value_kind="float",
                unit="distance",
                valid_range=(0.001, 100000.0),
                default_strategy=default_strategy,
                cook_risk="medium",
                validation_rule=validation_rule,
                official_source=_LIGHT_COMP_DOCS,
            )
            for name, label, default_strategy, validation_rule in (
                ("focal", "Focal Length", "positive_light_view_focal_length", "numeric_focal_length"),
                ("aperture", "Aperture", "positive_light_view_aperture", "numeric_aperture"),
                ("near", "Near", "positive_light_view_near_clipping_plane", "numeric_near_clip"),
                ("far", "Far", "positive_light_view_far_clipping_plane", "numeric_far_clip"),
            )
        ],
        ParamSemantics(
            op_type="lightCOMP",
            name="projmatrixop",
            label="Proj Matrix/CHOP/DAT",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="created_projection_matrix_chop_or_dat_when_custom_matrix_is_requested",
            cook_risk="high",
            validation_rule="non_empty_operator_reference",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="customproj",
            label="Custom Projection GLSL DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_custom_projection_text_dat_if_custom_projection_is_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="bgcolor",
            label="Background Color",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_light_view_background_rgba",
            cook_risk="low",
            validation_rule="rgba_tuple",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="material",
            label="Material MAT",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="created_material_mat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="render",
            label="Render",
            value_kind="bool",
            default_strategy="enabled_for_light_component_geometry_that_should_render",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="drawpriority",
            label="Draw Priority",
            value_kind="float",
            default_strategy="default_draw_priority_until_explicit_ordering_is_required",
            cook_risk="medium",
            validation_rule="numeric_draw_priority",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="pickpriority",
            label="Pick Priority",
            value_kind="float",
            default_strategy="default_pick_priority_until_render_picking_needs_ordering",
            cook_risk="medium",
            validation_rule="numeric_pick_priority",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="wcolor",
            label="Wireframe Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_wireframe_display_color",
            cook_risk="low",
            validation_rule="rgb_tuple",
            official_source=_LIGHT_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="lightCOMP",
            name="lightmask",
            label="Light Mask",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="lightCOMP",
            default_strategy="created_light_comps_when_light_component_geometry_uses_light_mask",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_LIGHT_COMP_DOCS,
        ),
    ]


def _render_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="renderTOP",
            name="camera",
            label="Camera COMP",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="cameraCOMP",
            default_strategy="created_camera_comp",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="multicamerahint",
            label="Multi-Camera Hint",
            value_kind="enum",
            enum_values=_RENDER_MULTI_CAMERA_HINT_VALUES,
            default_strategy="automatic_multi_camera_hint",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="geometry",
            label="Geometry COMP",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="geometryCOMP",
            default_strategy="created_geometry_comp",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="lights",
            label="Light COMPs",
            value_kind="op_ref",
            expected_family="COMP",
            expected_op_type="lightCOMP",
            default_strategy="created_light_comp_or_safe_scene_light",
            cook_risk="high",
            validation_rule="created_reference_matches_type",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="antialias",
            label="Anti-Alias",
            value_kind="enum",
            enum_values=_RENDER_ANTI_ALIAS_VALUES,
            default_strategy="low_or_off_until_visual_quality_requires_more",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="bgcolor",
            label="Background Color",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="opaque_black",
            cook_risk="low",
            validation_rule="rgba_tuple",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="premultrgbbyalpha",
            label="Pre-Multiply RGB by Alpha",
            value_kind="bool",
            default_strategy="off_unless_compositing_requires_premultiplied_alpha",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="rendermode",
            label="Render Mode",
            value_kind="enum",
            enum_values=_RENDER_MODE_VALUES,
            default_strategy="standard_2d_render",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="transparency",
            label="Transparency",
            value_kind="enum",
            enum_values=_RENDER_TRANSPARENCY_VALUES,
            default_strategy="sorted_blending_for_simple_transparent_scenes",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="depthpeel",
            label="Depth Peel",
            value_kind="bool",
            default_strategy="off_unless_transparency_layers_are_requested",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="transpeellayers",
            label="Transparency/Peel Layers",
            value_kind="int",
            unit="passes",
            valid_range=(1.0, 100.0),
            default_strategy="single_peel_layer_unless_order_independent_transparency_requires_more",
            cook_risk="high",
            validation_rule="positive_bounded_render_pass_count",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="render",
            label="Render",
            value_kind="bool",
            default_strategy="enabled_for_realtime_render_outputs",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="dither",
            label="Dither",
            value_kind="bool",
            default_strategy="enabled_only_when_banding_is_visible",
            cook_risk="low",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="coloroutputneeded",
            label="Color Output Needed",
            value_kind="bool",
            default_strategy="on_for_visible_render_outputs",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="drawdepthonly",
            label="Draw Depth Only",
            value_kind="bool",
            default_strategy="off_unless_depth_buffer_output_is_requested",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="numcolorbufs",
            label="Number of Color Buffers",
            value_kind="int",
            unit="buffers",
            valid_range=(1.0, 16.0),
            default_strategy="single_color_buffer_unless_glsl_material_outputs_more",
            cook_risk="high",
            validation_rule="positive_bounded_color_buffer_count",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="depthformat",
            label="Depth Buffer Format",
            value_kind="enum",
            enum_values=_RENDER_DEPTH_FORMAT_VALUES,
            default_strategy="fixed_24_bit_depth_for_standard_rendering",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="cullface",
            label="Cull Face",
            value_kind="enum",
            enum_values=_RENDER_CULL_FACE_VALUES,
            default_strategy="neither_until_mesh_winding_is_verified",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="overridemat",
            label="Override Material",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="created_material_when_override_pass_is_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="polygonoffset",
            label="Polygon Depth Offset",
            value_kind="bool",
            default_strategy="off_unless_z_fighting_or_shadow_bias_requires_it",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="polygonoffsetfactor",
            label="Polygon Offset Factor",
            value_kind="float",
            unit="depth_offset",
            valid_range=(-10000.0, 10000.0),
            default_strategy="small_depth_bias_factor_when_offset_is_enabled",
            cook_risk="medium",
            validation_rule="numeric_polygon_offset_factor",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="polygonoffsetunits",
            label="Polygon Offset Units",
            value_kind="float",
            unit="depth_offset",
            valid_range=(-10000.0, 10000.0),
            default_strategy="small_constant_depth_bias_when_offset_is_enabled",
            cook_risk="medium",
            validation_rule="numeric_polygon_offset_units",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="overdraw",
            label="Display Overdraw",
            value_kind="bool",
            default_strategy="off_unless_debugging_overdraw",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="overdrawlimit",
            label="Overdraw Limit",
            value_kind="int",
            valid_range=(1.0, 100000.0),
            default_strategy="small_positive_overdraw_debug_limit",
            cook_risk="high",
            validation_rule="positive_bounded_overdraw_limit",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="sampler0top",
            label="Sampler TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_or_user_supplied_texture_sampler",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_RENDER_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="renderTOP",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_TOP_EXTEND_VALUES,
                default_strategy="hold_for_sampler_bounds",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=_RENDER_TOP_DOCS,
            )
            for name, label in (
                ("sampler0extendu", "Sampler Extend U"),
                ("sampler0extendv", "Sampler Extend V"),
                ("sampler0extendw", "Sampler Extend W"),
            )
        ],
        ParamSemantics(
            op_type="renderTOP",
            name="sampler0filter",
            label="Sampler Filter",
            value_kind="enum",
            enum_values=_GLSL_COMP_FILTER_VALUES,
            default_strategy="linear_sampler_filter_for_render_textures",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="sampler0anisotropy",
            label="Sampler Anisotropy",
            value_kind="enum",
            enum_values=_GLSL_COMP_ANISOTROPY_VALUES,
            default_strategy="off_unless_grazing_angle_texture_quality_requires_it",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="outputresolution",
            label="Output Resolution",
            value_kind="enum",
            enum_values=_TOP_OUTPUT_RESOLUTION_VALUES,
            default_strategy="use_input_until_custom_resolution_is_required",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="resolution",
            label="Render Resolution",
            value_kind="tuple",
            tuple_size=2,
            unit="pixels",
            valid_range=(1.0, 8192.0),
            default_strategy="inherit_or_hd_safe",
            cook_risk="high",
            validation_rule="warn_high_resolution",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="resmult",
            label="Use Global Resolution Multiplier",
            value_kind="bool",
            default_strategy="respect_project_resolution_multiplier",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_RENDER_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="renderTOP",
            name="npasses",
            label="Passes",
            value_kind="int",
            unit="passes",
            valid_range=(1.0, 100000.0),
            default_strategy="single_pass_unless_explicit_multipass_rendering_is_needed",
            cook_risk="high",
            validation_rule="positive_bounded_render_pass_count",
            official_source=_RENDER_TOP_DOCS,
        ),
    ]


def _glsl_mat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="glslMAT",
            name="glslversion",
            label="GLSL Version",
            value_kind="enum",
            enum_values=_GLSL_VERSION_VALUES,
            default_strategy="current_generated_material_shader_version",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslMAT",
                name=name,
                label=label,
                value_kind="op_ref",
                expected_family="DAT",
                default_strategy="created_text_dat_for_material_shader_stage",
                cook_risk="high",
                validation_rule="created_reference_matches_family",
                official_source=_GLSL_MAT_DOCS,
            )
            for name, label in (
                ("predat", "Preprocess Directives DAT"),
                ("vdat", "Vertex Shader DAT"),
                ("pdat", "Pixel Shader DAT"),
                ("gdat", "Geometry Shader DAT"),
            )
        ],
        *[
            ParamSemantics(
                op_type="glslMAT",
                name=name,
                label=label,
                value_kind="pulse",
                default_strategy="manual_uniform_name_action_only_when_shader_source_changes",
                cook_risk="medium",
                validation_rule="pulse_action",
                official_source=_GLSL_MAT_DOCS,
            )
            for name, label in (
                ("loaduniformnames", "Load Uniform Names"),
                ("clearuniformnames", "Clear Uniform Names"),
            )
        ],
        ParamSemantics(
            op_type="glslMAT",
            name="inherit",
            label="Inherit Uniforms/Samplers From",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="explicit_material_uniform_inheritance_only_when_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="lightingspace",
            label="Lighting Space",
            value_kind="enum",
            enum_values=_GLSL_MAT_LIGHTING_SPACE_VALUES,
            default_strategy="world_space_for_current_generated_materials",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="simplexnoise",
            label="TDSimplexNoise",
            value_kind="enum",
            enum_values=_GLSL_SIMPLEX_NOISE_VALUES,
            default_strategy="performance_mode_unless_quality_noise_is_required",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="inprim",
            label="Input Primitive Type",
            value_kind="enum",
            enum_values=_GLSL_MAT_INPUT_PRIMITIVE_VALUES,
            default_strategy="triangles_for_standard_geometry_shaders",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="outprim",
            label="Output Primitive Type",
            value_kind="enum",
            enum_values=_GLSL_MAT_OUTPUT_PRIMITIVE_VALUES,
            default_strategy="triangle_strip_for_standard_geometry_shader_output",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="numout",
            label="Num Output Vertices",
            value_kind="int",
            unit="vertices",
            valid_range=(1.0, 100000.0),
            default_strategy="small_positive_geometry_shader_output_bound",
            cook_risk="high",
            validation_rule="positive_geometry_shader_output_count",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="twocolor",
            label="Two Sided Coloring",
            value_kind="bool",
            default_strategy="off_unless_front_and_back_material_colors_are_generated",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="attr0name",
            label="Attribute Name",
            value_kind="string",
            default_strategy="explicit_shader_attribute_name",
            cook_risk="medium",
            validation_rule="shader_attribute_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="attr0type",
            label="Attribute Type",
            value_kind="enum",
            enum_values=_GLSL_MAT_ATTR_TYPE_VALUES,
            default_strategy="vec3_or_vec4_for_common_geometry_attributes",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="attr0size",
            label="Attribute Array Size",
            value_kind="int",
            valid_range=(1.0, 100000.0),
            default_strategy="single_attribute_value_unless_array_is_explicit",
            cook_risk="medium",
            validation_rule="positive_attribute_array_size",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="sampler0name",
            label="Sampler Name",
            value_kind="string",
            default_strategy="explicit_shader_sampler_name",
            cook_risk="medium",
            validation_rule="shader_sampler_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="sampler0top",
            label="Sampler TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_or_user_supplied_material_texture_top",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslMAT",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_TOP_EXTEND_VALUES,
                default_strategy="hold_for_material_sampler_bounds",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=_GLSL_MAT_DOCS,
            )
            for name, label in (
                ("sampler0extendu", "Sampler Extend U"),
                ("sampler0extendv", "Sampler Extend V"),
                ("sampler0extendw", "Sampler Extend W"),
            )
        ],
        ParamSemantics(
            op_type="glslMAT",
            name="sampler0filter",
            label="Sampler Filter",
            value_kind="enum",
            enum_values=_GLSL_COMP_FILTER_VALUES,
            default_strategy="linear_sampler_filter_for_material_textures",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="sampler0anisotropy",
            label="Sampler Anisotropy",
            value_kind="enum",
            enum_values=_GLSL_COMP_ANISOTROPY_VALUES,
            default_strategy="off_unless_material_texture_quality_requires_anisotropy",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="vec0name",
            label="Vector Uniform Name",
            value_kind="string",
            default_strategy="explicit_vector_uniform_name",
            cook_risk="medium",
            validation_rule="shader_uniform_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="vec0value",
            label="Vector Uniform Value",
            value_kind="tuple",
            tuple_size=4,
            default_strategy="four_component_vector_uniform_value",
            cook_risk="medium",
            validation_rule="vec4_uniform_tuple",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="matrix0name",
            label="Matrix Uniform Name",
            value_kind="string",
            default_strategy="explicit_matrix_uniform_name",
            cook_risk="medium",
            validation_rule="shader_uniform_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="matrix0value",
            label="Matrix Uniform Value",
            value_kind="tuple",
            tuple_size=16,
            default_strategy="sixteen_component_mat4_uniform_value",
            cook_risk="medium",
            validation_rule="mat4_uniform_tuple",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="rel0name",
            label="Relative Transform Name",
            value_kind="string",
            default_strategy="explicit_relative_transform_uniform_name",
            cook_risk="medium",
            validation_rule="shader_uniform_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="rel0from",
            label="Relative Transform From COMP",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_source_component_for_relative_transform",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="rel0to",
            label="Relative Transform To COMP",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_destination_component_for_relative_transform",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="const0name",
            label="Specialization Constant Name",
            value_kind="string",
            default_strategy="explicit_specialization_constant_name",
            cook_risk="medium",
            validation_rule="shader_constant_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="const0value",
            label="Specialization Constant Value",
            value_kind="float",
            default_strategy="numeric_specialization_constant_value",
            cook_risk="medium",
            validation_rule="numeric_constant_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="dodeform",
            label="Deform",
            value_kind="bool",
            default_strategy="off_unless_bone_deform_data_is_explicitly_available",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="deformdata",
            label="Get Bone Data",
            value_kind="enum",
            enum_values=_GLSL_MAT_DEFORM_DATA_VALUES,
            default_strategy="sop_capture_data_for_generated_deform_materials",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="targetsop",
            label="SOP With Capture Data",
            value_kind="op_ref",
            expected_family="SOP",
            default_strategy="created_capture_data_sop_when_deforming",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="pcaptpath",
            label="pCaptPath Attribute",
            value_kind="string",
            default_strategy="explicit_capture_path_attribute_name",
            cook_risk="high",
            validation_rule="capture_attribute_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="pcaptdata",
            label="pCaptData Attribute",
            value_kind="string",
            default_strategy="explicit_capture_data_attribute_name",
            cook_risk="high",
            validation_rule="capture_attribute_name",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="skelrootpath",
            label="Skeleton Root Path",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="created_skeleton_root_component_when_deforming",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="mat",
            label="Deform Source MAT",
            value_kind="op_ref",
            expected_family="MAT",
            default_strategy="created_deform_source_material_when_deformdata_uses_mat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MAT_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslMAT",
                name=name,
                label=label,
                value_kind="bool",
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="bool_toggle",
                official_source=_GLSL_MAT_DOCS,
            )
            for name, label, default_strategy, cook_risk in (
                ("blending", "Blending", "off_unless_transparency_or_additive_material_is_requested", "high"),
                (
                    "separatealphafunc",
                    "Separate Alpha Function",
                    "off_unless_alpha_blend_requires_separate_factors",
                    "high",
                ),
                (
                    "legacyalphabehavior",
                    "Legacy Alpha Behavior",
                    "off_for_current_generated_materials",
                    "medium",
                ),
                (
                    "postmultalpha",
                    "Post-Mult Color by Alpha",
                    "off_unless_post_material_alpha_multiply_is_requested",
                    "medium",
                ),
                ("depthtest", "Depth Test", "on_for_standard_3d_material_depth_occlusion", "high"),
                ("depthwriting", "Write Depth Values", "on_for_standard_opaque_3d_materials", "high"),
                (
                    "alphatest",
                    "Discard Pixels Based on Alpha",
                    "off_unless_alpha_cutout_is_requested",
                    "medium",
                ),
                (
                    "polygonoffset",
                    "Polygon Depth Offset",
                    "off_unless_z_fighting_or_shadow_bias_requires_it",
                    "medium",
                ),
            )
        ],
        *[
            ParamSemantics(
                op_type="glslMAT",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_GLSL_MAT_BLEND_OP_VALUES,
                default_strategy="additive_blend_operation_unless_other_compositing_is_explicit",
                cook_risk="high",
                validation_rule="known_menu_value",
                official_source=_GLSL_MAT_DOCS,
            )
            for name, label in (
                ("blendop", "Blend Operation"),
                ("blendopa", "Alpha Blend Operation"),
            )
        ],
        *[
            ParamSemantics(
                op_type="glslMAT",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_GLSL_MAT_BLEND_FACTOR_VALUES,
                default_strategy="standard_alpha_blend_factor_until_compositing_is_verified",
                cook_risk="high",
                validation_rule="known_menu_value",
                official_source=_GLSL_MAT_DOCS,
            )
            for name, label in (
                ("srcblend", "Source Color Blend"),
                ("destblend", "Destination Color Blend"),
                ("srcblenda", "Source Alpha Blend"),
                ("destblenda", "Destination Alpha Blend"),
            )
        ],
        ParamSemantics(
            op_type="glslMAT",
            name="blendconstant",
            label="Blend Constant Color",
            value_kind="tuple",
            tuple_size=3,
            valid_range=(0.0, 1.0),
            default_strategy="normalized_blend_constant_color",
            cook_risk="medium",
            validation_rule="rgb_tuple",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="blendconstanta",
            label="Blend Constant Alpha",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="normalized_blend_constant_alpha",
            cook_risk="medium",
            validation_rule="normalized_alpha",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="pointcolorpremult",
            label="Point Color Pre-Multiply",
            value_kind="enum",
            enum_values=_GLSL_MAT_POINT_COLOR_PREMULT_VALUES,
            default_strategy="already_premultiplied_unless_shader_generates_straight_alpha",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="depthfunc",
            label="Depth Test Function",
            value_kind="enum",
            enum_values=_GLSL_MAT_DEPTH_FUNC_VALUES,
            default_strategy="less_than_or_equal_for_standard_3d_depth",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="alphafunc",
            label="Keep Pixels with Alpha",
            value_kind="enum",
            enum_values=_GLSL_MAT_ALPHA_FUNC_VALUES,
            default_strategy="greater_than_for_alpha_cutout_thresholds",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="alphathreshold",
            label="Alpha Threshold",
            value_kind="float",
            valid_range=(0.0, 1.0),
            default_strategy="normalized_alpha_cutout_threshold",
            cook_risk="medium",
            validation_rule="normalized_alpha",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="wireframe",
            label="Wire Frame",
            value_kind="enum",
            enum_values=_GLSL_MAT_WIREFRAME_VALUES,
            default_strategy="off_unless_wireframe_material_is_requested",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="wirewidth",
            label="Line Width",
            value_kind="float",
            unit="pixels",
            valid_range=(0.001, 10000.0),
            default_strategy="positive_wire_width_when_wireframe_is_enabled",
            cook_risk="medium",
            validation_rule="positive_wire_width",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="cullface",
            label="Cull Face",
            value_kind="enum",
            enum_values=_GLSL_MAT_CULL_FACE_VALUES,
            default_strategy="use_render_setting_until_mesh_winding_is_verified",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="polygonoffsetfactor",
            label="Polygon Offset Factor",
            value_kind="float",
            unit="depth_offset",
            valid_range=(-10000.0, 10000.0),
            default_strategy="small_depth_bias_factor_when_offset_is_enabled",
            cook_risk="medium",
            validation_rule="numeric_polygon_offset_factor",
            official_source=_GLSL_MAT_DOCS,
        ),
        ParamSemantics(
            op_type="glslMAT",
            name="polygonoffsetunits",
            label="Polygon Offset Units",
            value_kind="float",
            unit="depth_offset",
            valid_range=(-10000.0, 10000.0),
            default_strategy="small_constant_depth_bias_when_offset_is_enabled",
            cook_risk="medium",
            validation_rule="numeric_polygon_offset_units",
            official_source=_GLSL_MAT_DOCS,
        ),
    ]


def _glsl_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="glslTOP",
            name="glslversion",
            label="GLSL Version",
            value_kind="enum",
            enum_values=_GLSL_VERSION_VALUES,
            default_strategy="current_generated_shader_version",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="mode",
            label="Mode",
            value_kind="enum",
            enum_values=_GLSL_SHADER_MODE_VALUES,
            default_strategy="vertex_pixel_for_image_shaders_compute_only_when_needed",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslTOP",
                name=name,
                label=label,
                value_kind="op_ref",
                expected_family="DAT",
                default_strategy="created_text_dat",
                cook_risk="high",
                validation_rule="created_reference_matches_family",
                official_source=_GLSL_TOP_DOCS,
            )
            for name, label in _GLSL_MULTI_DAT_PARAMS.items()
        ],
        ParamSemantics(
            op_type="glslTOP",
            name="compilebehavior",
            label="Compile Behavior",
            value_kind="enum",
            enum_values=_GLSL_COMPILE_BEHAVIOR_VALUES,
            default_strategy="threaded_previous_shader_for_interactive_edits",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="errorbehavior",
            label="Error Behavior",
            value_kind="enum",
            enum_values=_GLSL_ERROR_BEHAVIOR_VALUES,
            default_strategy="show_checkerboard_for_visible_shader_errors",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="autodispatchsize",
            label="Auto Dispatch Size",
            value_kind="bool",
            default_strategy="auto_dispatch_for_pixel_sized_compute_work",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslTOP",
                name=name,
                label=label,
                value_kind="int",
                unit=unit,
                valid_range=(minimum, 100000.0),
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="positive_bounded_shader_count",
                official_source=_GLSL_TOP_DOCS,
            )
            for name, (label, unit, minimum, default_strategy, cook_risk) in _GLSL_TOP_INT_PARAMS.items()
        ],
        ParamSemantics(
            op_type="glslTOP",
            name="outputaccess",
            label="Output Access",
            value_kind="enum",
            enum_values=_GLSL_TOP_OUTPUT_ACCESS_VALUES,
            default_strategy="write_only_unless_shader_reads_previous_output",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="type",
            label="Output Type",
            value_kind="enum",
            enum_values=_GLSL_MULTI_OUTPUT_TYPE_VALUES,
            default_strategy="two_dimensional_texture_for_standard_outputs",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="depth",
            label="Depth",
            value_kind="enum",
            enum_values=_INPUT_OR_CUSTOM_VALUES,
            default_strategy="input_depth_unless_custom_texture_depth_is_required",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="clearoutputs",
            label="Clear Outputs",
            value_kind="bool",
            default_strategy="clear_compute_outputs_unless_feedback_history_is_required",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="clearvalue",
            label="Clear Value",
            value_kind="tuple",
            tuple_size=4,
            valid_range=(0.0, 1.0),
            default_strategy="transparent_black_compute_clear_value",
            cook_risk="medium",
            validation_rule="rgba_tuple",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="inputmapping",
            label="Input Mapping",
            value_kind="enum",
            enum_values=_GLSL_MULTI_INPUT_MAPPING_VALUES,
            default_strategy="all_inputs_to_every_slice",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="inputextenduv",
            label="Input Extend Mode UV",
            value_kind="enum",
            enum_values=_TOP_EXTEND_VALUES,
            default_strategy="hold_for_sampler_bounds",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="inputextendw",
            label="Input Extend Mode W",
            value_kind="enum",
            enum_values=_TOP_EXTEND_VALUES,
            default_strategy="hold_for_sampler_bounds",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="simplexnoise",
            label="TDSimplexNoise",
            value_kind="enum",
            enum_values=_GLSL_SIMPLEX_NOISE_VALUES,
            default_strategy="performance_noise_for_realtime_shader_effects",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="array0chop",
            label="Array Uniform CHOP",
            value_kind="op_ref",
            expected_family="CHOP",
            default_strategy="created_control_chop",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="array0type",
            label="Array Uniform Type",
            value_kind="enum",
            enum_values=_GLSL_ARRAY_TYPE_VALUES,
            default_strategy="float_for_single_channel_control_arrays",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="array0arraytype",
            label="Array Storage Type",
            value_kind="enum",
            enum_values=_GLSL_ARRAY_STORAGE_VALUES,
            default_strategy="uniform_array_for_small_control_sets",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="buffer0pop",
            label="Buffer POP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="created_pop_attribute_source",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="buffer0attrclass",
            label="Buffer Attribute Class",
            value_kind="enum",
            enum_values=_POP_ATTRIBUTE_CLASS_VALUES,
            default_strategy="point_attributes_for_shader_buffers",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="buffer0attr",
            label="Buffer Attribute",
            value_kind="string",
            default_strategy="explicit_pop_attribute_name",
            cook_risk="medium",
            validation_rule="attribute_name_string",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="buffer0name",
            label="Buffer Shader Name",
            value_kind="string",
            default_strategy="explicit_shader_buffer_function_name",
            cook_risk="medium",
            validation_rule="shader_identifier_string",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="outputresolution",
            label="Output Resolution",
            value_kind="enum",
            enum_values=_TOP_OUTPUT_RESOLUTION_VALUES,
            default_strategy="use_input_until_custom_resolution_is_required",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="resolution",
            label="Resolution",
            value_kind="tuple",
            tuple_size=2,
            unit="pixels",
            valid_range=(1.0, 8192.0),
            default_strategy="bounded_custom_output_resolution",
            cook_risk="high",
            validation_rule="warn_high_resolution",
            official_source=_GLSL_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslTOP",
            name="resmult",
            label="Use Global Resolution Multiplier",
            value_kind="bool",
            default_strategy="respect_project_resolution_multiplier",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_GLSL_TOP_DOCS,
        ),
    ]


def _glsl_multi_top_semantics() -> list[ParamSemantics]:
    semantics = [
        ParamSemantics(
            op_type="glslmultiTOP",
            name="glslversion",
            label="GLSL Version",
            value_kind="enum",
            enum_values=_GLSL_VERSION_VALUES,
            default_strategy="current_generated_shader_version",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="mode",
            label="Mode",
            value_kind="enum",
            enum_values=_GLSL_SHADER_MODE_VALUES,
            default_strategy="vertex_pixel_for_image_shaders_compute_only_when_needed",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslmultiTOP",
                name=name,
                label=label,
                value_kind="op_ref",
                expected_family="DAT",
                default_strategy="created_text_dat",
                cook_risk="high",
                validation_rule="created_reference_matches_family",
                official_source=_GLSL_MULTI_TOP_DOCS,
            )
            for name, label in _GLSL_MULTI_DAT_PARAMS.items()
        ],
        ParamSemantics(
            op_type="glslmultiTOP",
            name="autodispatchsize",
            label="Auto Dispatch Size",
            value_kind="bool",
            default_strategy="auto_dispatch_for_pixel_sized_compute_work",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslmultiTOP",
                name=name,
                label=label,
                value_kind="int",
                unit=unit,
                valid_range=(minimum, 100000.0),
                default_strategy=default_strategy,
                cook_risk=cook_risk,
                validation_rule="positive_bounded_shader_count",
                official_source=_GLSL_MULTI_TOP_DOCS,
            )
            for name, (label, unit, minimum, default_strategy, cook_risk) in _GLSL_MULTI_INT_PARAMS.items()
        ],
        ParamSemantics(
            op_type="glslmultiTOP",
            name="outputaccess",
            label="Output Access",
            value_kind="enum",
            enum_values=_GLSL_OUTPUT_ACCESS_VALUES,
            default_strategy="write_only_unless_shader_reads_previous_output",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="type",
            label="Output Type",
            value_kind="enum",
            enum_values=_GLSL_MULTI_OUTPUT_TYPE_VALUES,
            default_strategy="two_dimensional_texture_for_standard_outputs",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="depth",
            label="Depth",
            value_kind="enum",
            enum_values=_INPUT_OR_CUSTOM_VALUES,
            default_strategy="input_depth_unless_custom_texture_depth_is_required",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="clearoutputs",
            label="Clear Outputs",
            value_kind="bool",
            default_strategy="clear_compute_outputs_unless_feedback_history_is_required",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="inputmapping",
            label="Input Mapping",
            value_kind="enum",
            enum_values=_GLSL_MULTI_INPUT_MAPPING_VALUES,
            default_strategy="all_inputs_to_every_slice",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="inputextenduv",
            label="Input Extend Mode UV",
            value_kind="enum",
            enum_values=_TOP_EXTEND_VALUES,
            default_strategy="hold_for_sampler_bounds",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="inputextendw",
            label="Input Extend Mode W",
            value_kind="enum",
            enum_values=_TOP_EXTEND_VALUES,
            default_strategy="hold_for_sampler_bounds",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="array0type",
            label="Array Uniform Type",
            value_kind="enum",
            enum_values=_GLSL_ARRAY_TYPE_VALUES,
            default_strategy="float_for_single_channel_control_arrays",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="array0chop",
            label="Array Uniform CHOP",
            value_kind="op_ref",
            expected_family="CHOP",
            default_strategy="created_control_chop",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="array0arraytype",
            label="Array Storage Type",
            value_kind="enum",
            enum_values=_GLSL_ARRAY_STORAGE_VALUES,
            default_strategy="uniform_array_for_small_control_sets",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="ac0initvalue",
            label="Atomic Counter Initial Value Type",
            value_kind="enum",
            enum_values=_GLSL_ATOMIC_COUNTER_INIT_VALUES,
            default_strategy="single_value_for_deterministic_counters",
            cook_risk="high",
            validation_rule="known_menu_value",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="ac0singlevalue",
            label="Atomic Counter Single Initial Value",
            value_kind="int",
            valid_range=(0.0, 100000.0),
            default_strategy="zero_or_small_counter_seed",
            cook_risk="high",
            validation_rule="non_negative_atomic_counter_seed",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="ac0chopvalue",
            label="Atomic Counter Initial Values CHOP",
            value_kind="op_ref",
            expected_family="CHOP",
            default_strategy="created_counter_seed_chop_when_needed",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="const0value",
            label="Specialization Constant Value",
            value_kind="float",
            default_strategy="numeric_constant_only_when_declared",
            cook_risk="medium",
            validation_rule="numeric_specialization_constant",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
        ParamSemantics(
            op_type="glslmultiTOP",
            name="resmult",
            label="Use Global Resolution Multiplier",
            value_kind="bool",
            default_strategy="respect_project_resolution_multiplier",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_GLSL_MULTI_TOP_DOCS,
        ),
    ]
    return semantics


def _glsl_comp_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="glslCOMP",
            name="vertexdat",
            label="Vertex Shader DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="pixeldat",
            label="Pixel Shader DAT",
            value_kind="op_ref",
            expected_family="DAT",
            default_strategy="created_text_dat",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="sampler0top",
            label="Sampler TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_sampler_top",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_COMP_DOCS,
        ),
        *[
            ParamSemantics(
                op_type="glslCOMP",
                name=name,
                label=label,
                value_kind="enum",
                enum_values=_TOP_EXTEND_VALUES,
                default_strategy="hold_for_sampler_bounds",
                cook_risk="medium",
                validation_rule="known_menu_value",
                official_source=_GLSL_COMP_DOCS,
            )
            for name, label in {
                "sampler0extendu": "Sampler Extend U",
                "sampler0extendv": "Sampler Extend V",
                "sampler0extendw": "Sampler Extend W",
            }.items()
        ],
        ParamSemantics(
            op_type="glslCOMP",
            name="sampler0filter",
            label="Sampler Filter",
            value_kind="enum",
            enum_values=_GLSL_COMP_FILTER_VALUES,
            default_strategy="linear_for_panel_shader_sampling",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="sampler0anisotropy",
            label="Sampler Anisotropic Filter",
            value_kind="enum",
            enum_values=_GLSL_COMP_ANISOTROPY_VALUES,
            default_strategy="off_unless_angle_sampling_requires_it",
            cook_risk="medium",
            validation_rule="known_menu_value",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="vec0value",
            label="Vector Uniform Value",
            value_kind="tuple",
            tuple_size=4,
            default_strategy="four_component_uniform_value",
            cook_risk="medium",
            validation_rule="vec4_uniform_tuple",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="const0value",
            label="Specialization Constant Value",
            value_kind="float",
            default_strategy="numeric_constant_only_when_declared",
            cook_risk="medium",
            validation_rule="numeric_specialization_constant",
            official_source=_GLSL_COMP_DOCS,
        ),
        *_panel_component_layout_semantics("glslCOMP", _GLSL_COMP_DOCS),
        ParamSemantics(
            op_type="glslCOMP",
            name="fixedaspect",
            label="Fixed Aspect",
            value_kind="enum",
            enum_values=_GLSL_COMP_FIXED_ASPECT_VALUES,
            default_strategy="off_for_flexible_generated_panels",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="aspect",
            label="Aspect Ratio",
            value_kind="float",
            default_strategy="numeric_width_height_ratio",
            cook_risk="low",
            validation_rule="numeric_aspect_ratio",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="layer",
            label="Depth Layer",
            value_kind="int",
            default_strategy="default_panel_depth_layer",
            cook_risk="low",
            validation_rule="integer_panel_layer",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="hmode",
            label="Horizontal Mode",
            value_kind="enum",
            enum_values=_GLSL_COMP_LAYOUT_MODE_VALUES,
            default_strategy="fixed_or_fill_width_for_generated_panels",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="vmode",
            label="Vertical Mode",
            value_kind="enum",
            enum_values=_GLSL_COMP_LAYOUT_MODE_VALUES,
            default_strategy="fixed_or_fill_height_for_generated_panels",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source=_GLSL_COMP_DOCS,
        ),
        *_panel_component_interaction_semantics("glslCOMP", _GLSL_COMP_DOCS),
        ParamSemantics(
            op_type="glslCOMP",
            name="top",
            label="Background TOP",
            value_kind="op_ref",
            expected_family="TOP",
            default_strategy="created_background_top_if_visual_panel_surface_is_needed",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="opviewer",
            label="Operator Viewer",
            value_kind="op_ref",
            expected_family="ANY",
            default_strategy="stable_internal_viewer_target",
            cook_risk="medium",
            validation_rule="non_empty_operator_reference",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="clone",
            label="Clone Master",
            value_kind="op_ref",
            expected_family="COMP",
            default_strategy="explicit_clone_master_only_when_requested",
            cook_risk="high",
            validation_rule="created_reference_matches_family",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="enablecloning",
            label="Enable Cloning",
            value_kind="bool",
            default_strategy="keep_disabled_unless_clone_master_is_defined",
            cook_risk="high",
            validation_rule="bool_toggle",
            official_source=_GLSL_COMP_DOCS,
        ),
        ParamSemantics(
            op_type="glslCOMP",
            name="loadondemand",
            label="Load on Demand",
            value_kind="bool",
            default_strategy="off_for_generated_panel_shaders",
            cook_risk="medium",
            validation_rule="bool_toggle",
            official_source=_GLSL_COMP_DOCS,
        ),
    ]


def _switch_top_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="switchTOP",
            name="index",
            label="Index",
            value_kind="int",
            valid_range=(0.0, 1.0),
            default_strategy="bounded_table_driven_render_switch_input",
            cook_risk="low",
            validation_rule="bounded_switch_index_or_table_expression",
            official_source=_SWITCH_TOP_DOCS,
        )
    ]


def _table_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="tableDAT",
            name="rows",
            label="Rows",
            value_kind="int",
            valid_range=(1.0, 100000.0),
            default_strategy="small_positive_cue_table_row_count",
            cook_risk="medium",
            validation_rule="positive_table_dimension",
            official_source=_TABLE_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="tableDAT",
            name="cols",
            label="Columns",
            value_kind="int",
            valid_range=(1.0, 10000.0),
            default_strategy="small_positive_cue_table_column_count",
            cook_risk="medium",
            validation_rule="positive_table_dimension",
            official_source=_TABLE_DAT_DOCS,
        ),
    ]


def _select_dat_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="selectDAT",
            name="rowselect",
            label="Row Select",
            value_kind="string",
            default_strategy="explicit_row_selector_or_table_control_expression",
            cook_risk="low",
            validation_rule="non_empty_selector_string",
            official_source=_SELECT_DAT_DOCS,
        ),
        ParamSemantics(
            op_type="selectDAT",
            name="colselect",
            label="Column Select",
            value_kind="string",
            default_strategy="explicit_column_selector_or_table_control_expression",
            cook_risk="low",
            validation_rule="non_empty_selector_string",
            official_source=_SELECT_DAT_DOCS,
        ),
    ]


def _glsl_advanced_pop_capacity_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="glsladvancedPOP",
            name=name,
            label=label,
            value_kind="int",
            unit=unit,
            valid_range=(0.0, _MAX_POP_CAPACITY_GUARD),
            default_strategy="prefer_input_or_small_custom_capacity",
            cook_risk="high",
            validation_rule="warn_large_pop_capacity",
            official_source=_GLSL_ADVANCED_POP_DOCS,
        )
        for name, (label, unit) in _GLSL_ADVANCED_POP_CAPACITY_PARAMS.items()
    ]


def _glsl_pop_thread_int_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type="glslPOP",
            name=name,
            label=label,
            value_kind="int",
            unit=unit,
            valid_range=(minimum, _MAX_POP_CAPACITY_GUARD),
            default_strategy=default_strategy,
            cook_risk=cook_risk,
            validation_rule=validation_rule,
            official_source=_GLSL_POP_DOCS,
        )
        for name, (
            label,
            unit,
            minimum,
            default_strategy,
            cook_risk,
            validation_rule,
        ) in _GLSL_POP_THREAD_INT_PARAMS.items()
    ]


def validate_patch_plan_parameter_contract(
    plan: PatchPlan,
    *,
    registry: Iterable[ParamSemantics] | None = None,
    require_semantics_for_set_params: bool = False,
) -> list[ValidationIssue]:
    """Validate generated parameter bindings before any TD mutation is attempted."""
    semantics = semantics_by_op_and_param(registry)
    created_types = _created_node_types(plan)
    issues: list[ValidationIssue] = []
    for target, params in _params_by_target(plan).items():
        op_type = created_types.get(target)
        if op_type is None:
            continue
        for name, value in params.items():
            semantic = semantics.get((op_type, str(name)))
            if semantic is None:
                alias_target = _PARAM_NAME_ALIASES.get((op_type, str(name)))
                if alias_target:
                    issues.append(
                        _issue(
                            code="unknown_param_alias",
                            message=(
                                f"{op_type}.{name} is not a live TouchDesigner parameter; "
                                f"use {op_type}.{alias_target}."
                            ),
                            path=target,
                        )
                    )
                    continue
                if require_semantics_for_set_params:
                    issues.append(
                        _issue(
                            code="missing_param_semantics",
                            message=f"No docs-grounded parameter semantics are registered for {op_type}.{name}.",
                            path=target,
                        )
                    )
                continue
            issues.extend(
                _validate_semantic_value(
                    path=target, semantic=semantic, value=value, created_types=created_types
                )
            )
    issues.extend(validate_reference_params_for_plan(plan))
    return _dedupe_issues(issues)


def parameter_risk_flags_for_plan(
    plan: PatchPlan,
    *,
    registry: Iterable[ParamSemantics] | None = None,
) -> list[str]:
    """Return non-blocking parameter risk flags for review before mutation."""
    semantics = semantics_by_op_and_param(registry)
    created_types = _created_node_types(plan)
    flags: list[str] = []
    for target, params in _params_by_target(plan).items():
        op_type = created_types.get(target)
        if op_type is None:
            continue
        for name, value in params.items():
            semantic = semantics.get((op_type, str(name)))
            if semantic is None:
                continue
            flags.extend(_semantic_risk_flags(semantic=semantic, value=value))
    return list(dict.fromkeys(flags))


def canonical_op_type(raw_type: str, family: str | None = None) -> str:
    """Return the docs/semantics canonical operator type for TD detail payloads."""
    compact = raw_type.strip()
    if family:
        suffix = family.strip().upper()
        if suffix and not compact.upper().endswith(suffix):
            compact = f"{compact}{suffix}"
    return _canonical_op_type(_normalize_op_type_case(compact))


def direct_param_semantics_warnings(
    *,
    path: str,
    op_type: str,
    params: dict[str, Any],
    registry: Iterable[ParamSemantics] | None = None,
    warn_on_missing_semantics: bool = True,
) -> list[ValidationIssue]:
    """Return warn-only docs-grounded parameter findings for direct MCP writes."""
    canonical = canonical_op_type(op_type)
    semantics = semantics_by_op_and_param(registry)
    known_for_operator = {name for known_op, name in semantics if known_op == canonical}
    issues: list[ValidationIssue] = []
    for name, raw_value in params.items():
        value, should_validate = _direct_semantic_value(raw_value)
        if not should_validate:
            continue
        semantic = semantics.get((canonical, str(name)))
        if semantic is None:
            alias_target = _PARAM_NAME_ALIASES.get((canonical, str(name)))
            if alias_target:
                issues.append(
                    _warning_issue(
                        code="unknown_param_alias",
                        message=(
                            f"{canonical}.{name} is not a live TouchDesigner parameter; "
                            f"use {canonical}.{alias_target}. Direct tool write executed warn-only."
                        ),
                        path=path,
                    )
                )
                continue
            if warn_on_missing_semantics and known_for_operator:
                issues.append(
                    _warning_issue(
                        code="missing_param_semantics",
                        message=(
                            f"No docs-grounded parameter semantics are registered for {canonical}.{name}; "
                            "direct tool write executed warn-only."
                        ),
                        path=path,
                    )
                )
            continue
        for issue in _validate_semantic_value(
            path=path,
            semantic=semantic,
            value=value,
            created_types={},
        ):
            issues.append(_as_direct_warning(issue))
        for flag in _semantic_risk_flags(semantic=semantic, value=value):
            issues.append(
                _warning_issue(
                    code="param_semantics_risk",
                    message=f"{path} ({canonical}) parameter {name} triggered {flag}.",
                    path=path,
                )
            )
    return _dedupe_issues(issues)


def audit_high_cook_risk_direct_param_coverage(
    registry: Iterable[ParamSemantics] | None = None,
) -> dict[str, Any]:
    """Classify high cook-risk semantics as direct-risk or validation-only."""
    direct_risk_parameters: list[dict[str, Any]] = []
    validation_only_parameters: list[dict[str, Any]] = []
    unclassified_parameters: list[dict[str, Any]] = []

    loaded_registry = list(registry) if registry is not None else load_param_semantics_registry()
    high_risk_semantics = sorted(
        (semantic for semantic in loaded_registry if str(semantic.cook_risk or "").lower() == "high"),
        key=lambda item: (item.op_type, item.name),
    )
    for semantic in high_risk_semantics:
        flags: list[str] = []
        for value in _audit_sample_values(semantic):
            flags.extend(_semantic_risk_flags(semantic=semantic, value=value))
        flags = list(dict.fromkeys(flags))
        base_entry = {
            "op_type": semantic.op_type,
            "name": semantic.name,
            "cook_risk": semantic.cook_risk,
            "validation_rule": semantic.validation_rule,
        }
        if flags:
            direct_risk_parameters.append({**base_entry, "behavior": "direct-risk", "risk_flags": flags})
        elif _has_validation_only_contract(semantic):
            validation_only_parameters.append(
                {
                    **base_entry,
                    "behavior": "validation-only",
                    "reason": _validation_only_reason(semantic),
                }
            )
        else:
            unclassified_parameters.append({**base_entry, "behavior": "unclassified"})

    return {
        "schema_version": 1,
        "contract": "high_cook_risk_direct_param_coverage_v1",
        "ok": not unclassified_parameters,
        "high_cook_risk_count": len(high_risk_semantics),
        "direct_risk_count": len(direct_risk_parameters),
        "validation_only_count": len(validation_only_parameters),
        "unclassified_count": len(unclassified_parameters),
        "direct_risk_parameters": direct_risk_parameters,
        "validation_only_parameters": validation_only_parameters,
        "unclassified_high_cook_risk_parameters": unclassified_parameters,
    }


def _validate_semantic_value(
    *,
    path: str,
    semantic: ParamSemantics,
    value: Any,
    created_types: dict[str, str],
) -> list[ValidationIssue]:
    if isinstance(value, dict) and "expr" in value:
        if semantic.op_type == "levelTOP" and semantic.validation_rule == "numeric_level_adjustment":
            return _validate_chop_reference_expression(
                path=path,
                semantic=semantic,
                value=value,
                created_types=created_types,
            )
        if semantic.validation_rule == "bounded_switch_index_or_table_expression":
            return _validate_switch_index_expression(
                path=path,
                semantic=semantic,
                value=value,
                created_types=created_types,
            )
        return [
            _issue(
                code="unsupported_param_expression",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} does not have "
                    "a docs-grounded expression contract."
                ),
                path=path,
            )
        ]

    issues: list[ValidationIssue] = []
    if semantic.value_kind == "enum":
        issues.extend(_validate_enum(path=path, semantic=semantic, value=value))
    if semantic.value_kind == "bool":
        issues.extend(_validate_bool(path=path, semantic=semantic, value=value))
    if semantic.value_kind == "int":
        issues.extend(_validate_int(path=path, semantic=semantic, value=value))
    if semantic.value_kind == "float":
        issues.extend(_validate_float(path=path, semantic=semantic, value=value))
    if semantic.tuple_size is not None:
        issues.extend(_validate_tuple_size(path=path, semantic=semantic, value=value))
    if semantic.valid_range is not None:
        issues.extend(_validate_range(path=path, semantic=semantic, value=value))
    if semantic.value_kind == "path":
        issues.extend(_validate_path(path=path, semantic=semantic, value=value))
    if semantic.value_kind == "op_ref":
        issues.extend(
            _validate_op_reference(path=path, semantic=semantic, value=value, created_types=created_types)
        )
    return issues


def _validate_chop_reference_expression(
    *,
    path: str,
    semantic: ParamSemantics,
    value: dict[str, Any],
    created_types: dict[str, str],
) -> list[ValidationIssue]:
    if set(value) != {"expr"} or not isinstance(value.get("expr"), str):
        return [
            _issue(
                code="unsafe_param_expression",
                message=f"{path} ({semantic.op_type}) parameter {semantic.name} has an unsupported expression payload.",
                path=path,
            )
        ]
    expression = value["expr"].strip()
    match = _CHOP_REFERENCE_EXPR.fullmatch(expression)
    if match is None:
        return [
            _issue(
                code="unsafe_param_expression",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} expression must be a direct "
                    "single-operator CHOP channel reference."
                ),
                path=path,
            )
        ]
    ref_path = match.group("path")
    ref_type = created_types.get(ref_path)
    if ref_type is None:
        return [
            _issue(
                code="param_expression_unknown_reference",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} expression references "
                    f"{ref_path}, which is not created in this PatchPlan."
                ),
                path=path,
            )
        ]
    if not ref_type.endswith("CHOP"):
        return [
            _issue(
                code="param_expression_reference_type_mismatch",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} expression references "
                    f"{ref_path} ({ref_type}), expected CHOP family."
                ),
                path=path,
            )
        ]
    return []


def _validate_switch_index_expression(
    *,
    path: str,
    semantic: ParamSemantics,
    value: dict[str, Any],
    created_types: dict[str, str],
) -> list[ValidationIssue]:
    if set(value) != {"expr"} or not isinstance(value.get("expr"), str):
        return [
            _issue(
                code="unsafe_param_expression",
                message=f"{path} ({semantic.op_type}) parameter {semantic.name} has an unsupported expression payload.",
                path=path,
            )
        ]
    expression = value["expr"].strip()
    match = _SWITCH_INDEX_TABLE_EXPR.fullmatch(expression)
    if match is None:
        return [
            _issue(
                code="unsafe_param_expression",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} expression is not the "
                    "bounded table-index form supported by TDPilot."
                ),
                path=path,
            )
        ]
    table_path = match.group("path")
    table_type = created_types.get(table_path)
    if table_type is None:
        return [
            _issue(
                code="param_expression_reference_missing",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} expression references "
                    f"{table_path}, which is not created by this PatchPlan."
                ),
                path=path,
            )
        ]
    if table_type != "tableDAT":
        return [
            _issue(
                code="param_expression_reference_type_mismatch",
                message=(
                    f"{path} ({semantic.op_type}) parameter {semantic.name} expression references "
                    f"{table_path} ({table_type}), expected tableDAT."
                ),
                path=path,
            )
        ]
    return []


def _semantic_risk_flags(*, semantic: ParamSemantics, value: Any) -> list[str]:
    flags: list[str] = []
    live_activation_flags = {
        ("audiodeviceinCHOP", "active"): "live-audio-input",
        ("videodeviceinTOP", "active"): "live-video-input",
        ("videodeviceinTOP", "capture"): "live-video-capture",
        ("kinectazureTOP", "active"): "kinect-azure-sensor-input",
        ("serialDAT", "active"): "serial-device-listener",
        ("oscinDAT", "active"): "osc-network-listener",
        ("websocketDAT", "active"): "websocket-network-client",
        ("mqttclientDAT", "active"): "mqtt-broker-client",
        ("udpinDAT", "active"): "udp-network-listener",
    }
    live_activation_flag = live_activation_flags.get((semantic.op_type, semantic.name))
    if live_activation_flag and _is_enabled_toggle_value(value):
        flags.append(f"param-semantics:{live_activation_flag}:{semantic.op_type}.{semantic.name}")
    if semantic.op_type == "midiinCHOP" and semantic.name == "source" and _is_midi_device_source_value(value):
        flags.append("param-semantics:midi-device-input:midiinCHOP.source")
    if (
        semantic.op_type == "audiofileoutCHOP"
        and semantic.name == "record"
        and _is_enabled_toggle_value(value)
    ):
        flags.append("param-semantics:audio-file-recording:audiofileoutCHOP.record")
    if (
        semantic.op_type == "audiodeviceoutCHOP"
        and semantic.name == "active"
        and _is_enabled_toggle_value(value)
    ):
        flags.append("param-semantics:live-audio-output:audiodeviceoutCHOP.active")
    if semantic.op_type == "webclientDAT" and semantic.name == "active" and _is_enabled_toggle_value(value):
        flags.append("param-semantics:http-client-active:webclientDAT.active")
    if semantic.op_type == "webclientDAT" and semantic.name == "request" and _is_pulse_action_value(value):
        flags.append("param-semantics:http-request:webclientDAT.request")
    if semantic.op_type == "webclientDAT" and semantic.name == "stream" and _is_enabled_toggle_value(value):
        flags.append("param-semantics:http-streaming-response:webclientDAT.stream")
    if semantic.op_type == "webserverDAT" and semantic.name == "active" and _is_enabled_toggle_value(value):
        flags.append("param-semantics:web-server-listener:webserverDAT.active")
    if semantic.op_type == "webserverDAT" and semantic.name == "restart" and _is_pulse_action_value(value):
        flags.append("param-semantics:web-server-restart:webserverDAT.restart")
    if _is_callback_execution_semantic(semantic):
        if semantic.name == "callbacks" and _has_nonempty_reference_value(value):
            flags.append(f"param-semantics:callback-dat-binding:{semantic.op_type}.{semantic.name}")
        if semantic.name == "executeloc" and _is_known_enum_value(semantic, value):
            flags.append(f"param-semantics:callback-execute-location:{semantic.op_type}.{semantic.name}")
        if semantic.name == "fromop" and _has_nonempty_reference_value(value):
            flags.append(f"param-semantics:callback-context-operator:{semantic.op_type}.{semantic.name}")
        if (
            semantic.op_type in {"datexecuteDAT", "chopexecuteDAT", "executeDAT"}
            and semantic.name == "active"
            and _is_enabled_toggle_value(value)
        ):
            flags.append(f"param-semantics:callback-execution-enabled:{semantic.op_type}.{semantic.name}")
        if semantic.name in _callback_trigger_param_names(semantic.op_type) and _is_enabled_toggle_value(
            value
        ):
            flags.append(f"param-semantics:callback-trigger-enabled:{semantic.op_type}.{semantic.name}")
        if semantic.name == "execute" and _is_known_enum_value(semantic, value):
            flags.append(f"param-semantics:callback-execution-timing:{semantic.op_type}.{semantic.name}")
        if semantic.name == "freq" and _is_known_enum_value(semantic, value):
            flags.append(f"param-semantics:callback-execution-frequency:{semantic.op_type}.{semantic.name}")
        if semantic.name == "callbackmode" and _is_known_enum_value(semantic, value):
            flags.append(f"param-semantics:callback-mode:{semantic.op_type}.{semantic.name}")
    if semantic.op_type == "executeDAT":
        if semantic.name in {"syncfile", "loadonstart", "write"} and _is_enabled_toggle_value(value):
            flags.append(f"param-semantics:script-file-sync:{semantic.op_type}.{semantic.name}")
        if semantic.name == "loadonstartpulse" and _is_pulse_action_value(value):
            flags.append(f"param-semantics:script-file-load:{semantic.op_type}.{semantic.name}")
        if semantic.name == "writepulse" and _is_pulse_action_value(value):
            flags.append(f"param-semantics:script-file-write:{semantic.op_type}.{semantic.name}")
    if (
        semantic.op_type == "mqttclientDAT"
        and semantic.name == "username"
        and _has_nonempty_text_value(value)
    ):
        flags.append("param-semantics:mqtt-credential-username:mqttclientDAT.username")
    if (
        semantic.op_type == "mqttclientDAT"
        and semantic.name == "password"
        and _has_nonempty_text_value(value)
    ):
        flags.append("param-semantics:mqtt-credential-secret:mqttclientDAT.password")
    if (
        semantic.op_type == "mqttclientDAT"
        and semantic.name == "verifycert"
        and _is_disabled_toggle_value(value)
    ):
        flags.append("param-semantics:mqtt-tls-verification-disabled:mqttclientDAT.verifycert")
    if semantic.op_type == "webclientDAT" and semantic.name == "username" and _has_nonempty_text_value(value):
        flags.append("param-semantics:http-credential-username:webclientDAT.username")
    if (
        semantic.op_type == "webclientDAT"
        and semantic.name in _WEB_CLIENT_SECRET_PARAMS
        and _has_nonempty_text_value(value)
    ):
        flags.append(f"param-semantics:http-credential-secret:webclientDAT.{semantic.name}")
    if (
        semantic.op_type == "webclientDAT"
        and semantic.name == "verifycert"
        and _is_disabled_toggle_value(value)
    ):
        flags.append("param-semantics:http-tls-verification-disabled:webclientDAT.verifycert")
    if (
        semantic.op_type == "webserverDAT"
        and semantic.name == "privatekey"
        and _has_nonempty_text_value(value)
    ):
        flags.append("param-semantics:web-server-tls-private-key:webserverDAT.privatekey")
    if (
        semantic.op_type == "webserverDAT"
        and semantic.name == "certificate"
        and _has_nonempty_text_value(value)
    ):
        flags.append("param-semantics:web-server-tls-certificate:webserverDAT.certificate")
    if semantic.op_type == "webserverDAT" and semantic.name == "password" and _has_nonempty_text_value(value):
        flags.append("param-semantics:web-server-tls-credential-secret:webserverDAT.password")
    if semantic.validation_rule == "warn_high_resolution":
        values = _numeric_values(value)
        if len(values) >= 2 and values[0] * values[1] > 3840 * 2160:
            flags.append(f"param-semantics:high-resolution:{semantic.op_type}.{semantic.name}")
    if semantic.validation_rule == "warn_large_pop_capacity":
        values = _numeric_values(value)
        if values and max(values) > _LARGE_POP_CAPACITY_THRESHOLD:
            flags.append(f"param-semantics:large-pop-capacity:{semantic.op_type}.{semantic.name}")
    if semantic.validation_rule == "warn_large_instance_count":
        values = _numeric_values(value)
        if values and max(values) > _LARGE_GEOMETRY_INSTANCE_THRESHOLD:
            flags.append(f"param-semantics:large-instance-count:{semantic.op_type}.{semantic.name}")
    return flags


def _audit_sample_values(semantic: ParamSemantics) -> list[Any]:
    if semantic.validation_rule == "warn_high_resolution":
        return [(7680, 4320)]
    if semantic.validation_rule in {"warn_large_pop_capacity", "warn_large_instance_count"}:
        return [1_000_001]
    if semantic.value_kind == "bool":
        return [True, False]
    if semantic.value_kind == "pulse":
        return [True]
    if semantic.value_kind == "enum":
        return list(semantic.enum_values or [])
    if semantic.value_kind == "int":
        return [int(min(float(semantic.valid_range[1]) if semantic.valid_range else 1.0, 1_000_001.0))]
    if semantic.value_kind == "float":
        return [1.0]
    if semantic.value_kind == "tuple":
        return [(1.0,) * int(semantic.tuple_size or 2)]
    if semantic.value_kind == "op_ref":
        return ["/project1/callbacks"]
    if semantic.value_kind == "path":
        return ["/tmp/tdpilot_param_semantics_audit"]
    return ["tdpilot-audit-value"]


def _has_validation_only_contract(semantic: ParamSemantics) -> bool:
    return bool(
        semantic.validation_rule
        or semantic.value_kind
        or semantic.enum_values
        or semantic.valid_range
        or semantic.tuple_size
    )


def _validation_only_reason(semantic: ParamSemantics) -> str:
    if semantic.validation_rule:
        return f"validation_rule:{semantic.validation_rule}"
    if semantic.valid_range is not None:
        return f"generic_validation:{semantic.value_kind}:range"
    if semantic.enum_values:
        return "generic_validation:enum"
    if semantic.tuple_size is not None:
        return f"generic_validation:tuple_size:{semantic.tuple_size}"
    return f"generic_validation:{semantic.value_kind}"


def _is_callback_execution_semantic(semantic: ParamSemantics) -> bool:
    callback_op_types = {
        "datexecuteDAT",
        "chopexecuteDAT",
        "executeDAT",
        "opexecuteDAT",
        "parameterexecuteDAT",
        "panelexecuteDAT",
        "pargroupexecuteDAT",
        "errorDAT",
        "serialDAT",
        "oscinDAT",
        "websocketDAT",
        "webclientDAT",
        "webserverDAT",
        "mqttclientDAT",
        "udpinDAT",
    }
    return semantic.op_type in callback_op_types


def _callback_trigger_param_names(op_type: str) -> set[str]:
    trigger_params_by_type = {
        "datexecuteDAT": _DAT_EXECUTE_TRIGGER_PARAMS,
        "chopexecuteDAT": _CHOP_EXECUTE_TRIGGER_PARAMS,
        "executeDAT": _EXECUTE_DAT_TRIGGER_PARAMS,
        "opexecuteDAT": _OP_EXECUTE_TRIGGER_PARAMS,
        "parameterexecuteDAT": _PARAMETER_EXECUTE_TRIGGER_PARAMS,
        "panelexecuteDAT": _PANEL_EXECUTE_TRIGGER_PARAMS,
        "pargroupexecuteDAT": _PARGROUP_EXECUTE_TRIGGER_PARAMS,
    }
    return {name for name, _label in trigger_params_by_type.get(op_type, [])}


def _has_nonempty_reference_value(value: Any) -> bool:
    return bool(_reference_tokens(value))


def _has_nonempty_text_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_known_enum_value(semantic: ParamSemantics, value: Any) -> bool:
    return str(value).lower() in {item.lower() for item in semantic.enum_values}


def _is_enabled_toggle_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 1
    return False


def _is_disabled_toggle_value(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 0
    return False


def _is_pulse_action_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "pulse", "press", "request"}
    return False


def _is_midi_device_source_value(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "device"


def _validate_enum(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    allowed = {item.lower() for item in semantic.enum_values}
    if str(value).lower() in allowed:
        return []
    return [
        _issue(
            code="invalid_enum_param",
            message=f"{path} ({semantic.op_type}) parameter {semantic.name} has unsupported value {value!r}.",
            path=path,
        )
    ]


def _validate_bool(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int) and value in {0, 1}:
        return []
    return [
        _issue(
            code="invalid_bool_param",
            message=f"{path} ({semantic.op_type}) parameter {semantic.name} expects a bool toggle.",
            path=path,
        )
    ]


def _validate_int(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    if isinstance(value, int) and not isinstance(value, bool):
        return []
    return [
        _issue(
            code="invalid_int_param",
            message=f"{path} ({semantic.op_type}) parameter {semantic.name} expects an integer value.",
            path=path,
        )
    ]


def _validate_float(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return []
    return [
        _issue(
            code="invalid_float_param",
            message=f"{path} ({semantic.op_type}) parameter {semantic.name} expects a numeric value.",
            path=path,
        )
    ]


def _validate_tuple_size(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    if not isinstance(value, list | tuple):
        return [
            _issue(
                code="param_tuple_size_mismatch",
                message=f"{path} ({semantic.op_type}) parameter {semantic.name} expects {semantic.tuple_size} values.",
                path=path,
            )
        ]
    if len(value) == semantic.tuple_size:
        return []
    return [
        _issue(
            code="param_tuple_size_mismatch",
            message=(
                f"{path} ({semantic.op_type}) parameter {semantic.name} has {len(value)} values, "
                f"expected {semantic.tuple_size}."
            ),
            path=path,
        )
    ]


def _validate_range(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    values = _numeric_values(value)
    if not values:
        return []
    low, high = semantic.valid_range or (0.0, 0.0)
    out_of_range = [item for item in values if item < low or item > high]
    if not out_of_range:
        return []
    return [
        _issue(
            code="param_out_of_range",
            message=(
                f"{path} ({semantic.op_type}) parameter {semantic.name} value {out_of_range[0]!r} "
                f"is outside [{low}, {high}]."
            ),
            path=path,
        )
    ]


def _validate_path(*, path: str, semantic: ParamSemantics, value: Any) -> list[ValidationIssue]:
    if isinstance(value, str) and value.strip():
        return []
    return [
        _issue(
            code="empty_path_param",
            message=f"{path} ({semantic.op_type}) parameter {semantic.name} requires a non-empty path when set.",
            path=path,
        )
    ]


def _validate_op_reference(
    *,
    path: str,
    semantic: ParamSemantics,
    value: Any,
    created_types: dict[str, str],
) -> list[ValidationIssue]:
    refs = _reference_tokens(value)
    if not refs:
        return [
            _issue(
                code="missing_reference_param",
                message=f"{path} ({semantic.op_type}) parameter {semantic.name} requires an OP reference.",
                path=path,
            )
        ]
    issues: list[ValidationIssue] = []
    for ref in refs:
        ref_type = created_types.get(ref)
        if ref_type is None:
            continue
        if semantic.expected_op_type and ref_type != semantic.expected_op_type:
            issues.append(
                _issue(
                    code="param_reference_type_mismatch",
                    message=(
                        f"{path} ({semantic.op_type}) parameter {semantic.name} references {ref} "
                        f"({ref_type}), expected {semantic.expected_op_type}."
                    ),
                    path=path,
                )
            )
            continue
        if (
            semantic.expected_family
            and semantic.expected_family != "ANY"
            and not ref_type.endswith(str(semantic.expected_family))
        ):
            issues.append(
                _issue(
                    code="param_reference_type_mismatch",
                    message=(
                        f"{path} ({semantic.op_type}) parameter {semantic.name} references {ref} "
                        f"({ref_type}), expected {semantic.expected_family} family."
                    ),
                    path=path,
                )
            )
    return issues


def _numeric_values(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, list | tuple):
        values: list[float] = []
        for item in value:
            values.extend(_numeric_values(item))
        return values
    return []


def _created_node_types(plan: PatchPlan) -> dict[str, str]:
    created: dict[str, str] = {}
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        name = operation.args.get("name")
        raw_type = operation.args.get("op_type")
        if not name or not raw_type:
            continue
        parent = operation.target or plan.target_root
        created[_join_path(parent, str(name))] = _canonical_op_type(str(raw_type))
    return created


def _params_by_target(plan: PatchPlan) -> dict[str, dict[str, Any]]:
    params: dict[str, dict[str, Any]] = {}
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        payload = operation.args.get("params")
        if not isinstance(payload, dict):
            continue
        params.setdefault(str(operation.target), {}).update(payload)
    return params


def _reference_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        return [token for token in value.split() if token]
    if isinstance(value, list | tuple | set):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_reference_tokens(item))
        return tokens
    return []


def _canonical_op_type(raw_type: str) -> str:
    compact = raw_type.strip()
    return _CREATE_TYPE_ALIASES.get(compact.lower(), compact)


def _normalize_op_type_case(raw_type: str) -> str:
    compact = raw_type.strip()
    for suffix in ("CHOP", "COMP", "POPX", "TOP", "SOP", "DAT", "MAT", "POP"):
        if compact.upper().endswith(suffix):
            base = compact[: -len(suffix)]
            return base.lower() + suffix
    return compact


def _direct_semantic_value(value: Any) -> tuple[Any, bool]:
    if not isinstance(value, dict):
        return value, True
    if "expr" in value:
        return value, True
    if "val" in value:
        return value["val"], True
    if value.get("reset") is True:
        return None, False
    if value.get("mode") == "constant" and "val" in value:
        return value["val"], True
    return value, True


def _warning_issue(*, code: str, message: str, path: str) -> ValidationIssue:
    return ValidationIssue(
        severity="warning", code=code, message=message, path=path, source="tdpilot-direct-tool"
    )


def _as_direct_warning(issue: ValidationIssue) -> ValidationIssue:
    return ValidationIssue(
        severity="warning",
        code=issue.code,
        message=issue.message + " Direct tool write executed warn-only.",
        path=issue.path,
        source="tdpilot-direct-tool",
    )


def _join_path(parent: str, name: str) -> str:
    return f"{parent.rstrip('/')}/{name}".replace("//", "/")


def _issue(*, code: str, message: str, path: str) -> ValidationIssue:
    return ValidationIssue(severity="error", code=code, message=message, path=path, source="tdpilot-brain")


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple[str, str, str | None, str]] = set()
    deduped: list[ValidationIssue] = []
    for issue in issues:
        key = (issue.severity, issue.code, issue.path, issue.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped
