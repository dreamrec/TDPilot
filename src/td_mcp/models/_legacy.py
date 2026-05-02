"""
Pydantic Input Models for TouchDesigner MCP Tools
==================================================
All input validation, constraints, and descriptions for every tool.

TODO(tech-debt): This file is 1,100+ lines / 70+ Input classes and wants to be
a package (``models/nodes.py``, ``models/params.py``, ``models/memory.py``,
``models/vision.py``, ...). Deferred because ``tool_registry.py`` imports all
of them explicitly and every tool's registration would need to move in one
atomic change. See audit report #8. When splitting, keep ``models/__init__.py``
re-exporting the current flat namespace so external callers don't break.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


class MacroType(str, Enum):
    """Supported built-in macro templates."""

    FEEDBACK_LOOP = "feedback_loop"
    FEEDBACK_DISPLACEMENT = "feedback_displacement"
    AUDIO_REACTIVE = "audio_reactive"
    PARTICLE_GPU = "particle_gpu"
    POST_PROCESSING = "post_processing"


# ─────────────────────────────────────────────────────────────
# Environment / Info
# ─────────────────────────────────────────────────────────────


class EmptyInput(BaseModel):
    """No input required."""

    model_config = ConfigDict(extra="forbid")


# ─────────────────────────────────────────────────────────────
# Node Navigation & Inspection
# ─────────────────────────────────────────────────────────────


class GetNodesInput(BaseModel):
    """Input for listing child nodes at a path."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        default="/",
        description="Absolute path to a COMP node whose children to list (e.g. '/', '/project1', '/project1/myComp')",
    )
    family: str | None = Field(
        default=None, description="Filter by operator family: TOP, CHOP, SOP, DAT, COMP, MAT, or PANEL"
    )
    type: str | None = Field(
        default=None, description="Filter by specific operator type (e.g. 'noiseTOP', 'waveCHOP', 'textDAT')"
    )
    include_params: bool = Field(
        default=False, description="If true, include all parameters for each node (slower for large networks)"
    )
    limit: int = Field(default=100, ge=1, le=500, description="Max number of nodes to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Output format")


class NodePathInput(BaseModel):
    """Input requiring a single node path."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        ...,
        description="Absolute path to the node (e.g. '/project1/noise1', '/project1/geo1/sphere1')",
        min_length=1,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Output format")


class GetParamsInput(BaseModel):
    """Input for getting node parameters."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Absolute node path", min_length=1)
    page: str | None = Field(default=None, description="Filter by parameter page name")
    names: list[str] | None = Field(default=None, description="Filter to specific parameter names")
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Output format")


class SetParamsInput(BaseModel):
    """Input for setting node parameters (static values or live expressions)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Absolute node path", min_length=1)
    params: dict[str, Any] = Field(
        ...,
        description=(
            "Dictionary of parameter names to values. Supports five modes:\n"
            "• Static value (plain): {'seed': 42, 'colorr': 1.0}\n"
            "• Expression (reactive, updates every frame): {'seed': {'expr': 'absTime.seconds * 10'}, 'tx': {'expr': \"op('noise1')['chan1']\"}}\n"
            "• Explicit static: {'seed': {'val': 42}}\n"
            "• Reset to default: {'seed': {'reset': true}} — resets value and clears expression\n"
            "• Clear expression: {'seed': {'mode': 'constant', 'val': 42}} — force constant mode\n\n"
            "Expressions make networks ALIVE — use them for anything that should move, react, or change over time."
        ),
        min_length=1,
    )


# ─────────────────────────────────────────────────────────────
# Node Creation / Deletion / Copy / Rename
# ─────────────────────────────────────────────────────────────


class CreateNodeInput(BaseModel):
    """Input for creating a new node."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    parent_path: str = Field(
        default="/project1", description="Path to the parent COMP where the node will be created"
    )
    node_type: str = Field(
        ...,
        description=(
            "TouchDesigner operator type to create. Examples: "
            "TOPs: 'noiseTOP', 'levelTOP', 'nullTOP', 'compositeTOP', 'feedbackTOP', 'moviefileinTOP' | "
            "CHOPs: 'waveCHOP', 'noiseCHOP', 'nullCHOP', 'mathCHOP', 'constantCHOP', 'selectCHOP' | "
            "SOPs: 'sphereSOP', 'boxSOP', 'gridSOP', 'lineSOP', 'nullSOP', 'transformSOP', 'noiseSOP' | "
            "DATs: 'textDAT', 'tableDAT', 'scriptDAT', 'nullDAT', 'selectDAT', 'chopexecDAT' | "
            "COMPs: 'baseCOMP', 'containerCOMP', 'geometryCOMP', 'cameraCOMP', 'lightCOMP' | "
            "MATs: 'pbrMAT', 'phongMAT', 'wireframeMAT', 'constMAT'"
        ),
        min_length=1,
    )
    name: str | None = Field(
        default=None, description="Custom name for the new node. If None, TD assigns a default name."
    )
    nodeX: int | None = Field(
        default=None,
        description="Horizontal position in the network editor (pixels). Use multiples of 200 for clean spacing between nodes.",
    )
    nodeY: int | None = Field(
        default=None,
        description="Vertical position in the network editor (pixels). Use multiples of 200 for clean spacing between rows.",
    )

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        """Validate the operator type ends with a known family suffix.

        Note: POPX is listed before POP so that callers parsing family out of
        node_type match the LONGER suffix first — `noisePOPX` is a POPX op,
        not a POP op. `endswith` alone is safe since `noisePOP` doesn't
        endswith POPX and `noisePOPX` doesn't endswith POP.
        """
        families = ("TOP", "CHOP", "SOP", "DAT", "COMP", "MAT", "POPX", "POP")
        if not any(v.upper().endswith(f) for f in families):
            raise ValueError(
                f"node_type '{v}' should end with a family suffix: {', '.join(families)}. "
                f"Example: 'noiseTOP', 'waveCHOP', 'boxSOP', 'noiseFalloffPOPX'"
            )
        return v


class DeleteNodeInput(BaseModel):
    """Input for deleting a node."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Absolute path of the node to delete", min_length=1)


class CopyNodeInput(BaseModel):
    """Input for copying/duplicating a node."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_path: str = Field(..., description="Path of the node to copy", min_length=1)
    dest_parent: str | None = Field(
        default=None, description="Path of the destination parent COMP. If None, copies into same parent."
    )
    new_name: str | None = Field(default=None, description="Name for the copy")


class RenameNodeInput(BaseModel):
    """Input for renaming a node."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Current absolute path of the node", min_length=1)
    new_name: str = Field(..., description="New name for the node", min_length=1, max_length=100)


# ─────────────────────────────────────────────────────────────
# Connections / Wiring
# ─────────────────────────────────────────────────────────────


class ConnectNodesInput(BaseModel):
    """Input for connecting two nodes."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_path: str = Field(..., description="Path of the source (output) node", min_length=1)
    target_path: str = Field(..., description="Path of the target (input) node", min_length=1)
    source_index: int = Field(
        default=0, ge=0, description="Output connector index on the source node (0 = first output)"
    )
    target_index: int = Field(
        default=0, ge=0, description="Input connector index on the target node (0 = first input)"
    )


class DisconnectInput(BaseModel):
    """Input for disconnecting a node connector."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path of the node to disconnect", min_length=1)
    connector_type: str = Field(default="input", description="Which connector: 'input' or 'output'")
    index: int = Field(default=0, ge=0, description="Connector index to disconnect")

    @field_validator("connector_type")
    @classmethod
    def validate_connector_type(cls, v: str) -> str:
        if v not in ("input", "output"):
            raise ValueError("connector_type must be 'input' or 'output'")
        return v


# ─────────────────────────────────────────────────────────────
# DAT Content
# ─────────────────────────────────────────────────────────────


class GetContentInput(BaseModel):
    """Input for reading DAT text/table content."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a DAT node", min_length=1)


class SetContentInput(BaseModel):
    """Input for writing DAT text/table content."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a DAT node", min_length=1)
    text: str | None = Field(
        default=None, description="Text content to write (for Text DATs, Script DATs, etc.)"
    )
    table: list[list[str]] | None = Field(
        default=None, description="Table content as 2D array of strings (for Table DATs)"
    )


# ─────────────────────────────────────────────────────────────
# Python Execution
# ─────────────────────────────────────────────────────────────


class ExecPythonInput(BaseModel):
    """Input for executing Python code inside TouchDesigner."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: str = Field(
        ...,
        description=(
            "Python code to execute in TouchDesigner's Python environment. "
            "Has access to: op(), ops(), project, app, absTime, me, parent(), mod, ui, tdu. "
            "Set __result__ = <value> to return a value to the caller. "
            "Example: '__result__ = op(\"/project1/noise1\").par.type.eval()'"
        ),
        min_length=1,
        max_length=50000,
    )
    timeout_ms: int | None = Field(
        default=None,
        description=(
            "Optional per-call execution timeout in milliseconds. "
            "When omitted, TouchDesigner uses its configured default. "
            "Bounds: 100-60000 ms."
        ),
        ge=100,
        le=60000,
    )


# ─────────────────────────────────────────────────────────────
# Screenshot / Visual
# ─────────────────────────────────────────────────────────────


class ScreenshotInput(BaseModel):
    """Input for capturing a TOP node as a JPEG image."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        ...,
        description="Path to a TOP node to capture as an image (e.g. '/project1/null1', '/project1/render1')",
        min_length=1,
    )
    quality: float = Field(
        default=0.5,
        description="JPEG quality from 0.0 (smallest) to 1.0 (best). Default 0.5 gives good diagnostic quality at ~85KB.",
        ge=0.0,
        le=1.0,
    )


# ─────────────────────────────────────────────────────────────
# CHOP / Geometry Data
# ─────────────────────────────────────────────────────────────


class CHOPDataInput(BaseModel):
    """Input for reading CHOP channel data."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a CHOP node", min_length=1)
    channels: list[str] | None = Field(
        default=None, description="List of channel names to read. If None, reads all channels."
    )
    range: list[int] | None = Field(
        default=None,
        description="Sample range [start, end] to read. If None, reads all samples.",
        min_length=2,
        max_length=2,
    )


class GeometryDataInput(BaseModel):
    """Input for reading SOP/POP geometry data."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a SOP or POP node", min_length=1)
    include_points: bool = Field(default=True, description="Include point position data")
    include_prims: bool = Field(default=False, description="Include primitive data")
    limit: int = Field(default=500, ge=1, le=10000, description="Max points/prims to return")


class POPInspectInput(BaseModel):
    """Input for reading structured POP metadata and attribute samples."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a POP node", min_length=1)
    include_bounds: bool = Field(default=True, description="Include POP bounds and dimension metadata")
    include_attributes: bool = Field(default=True, description="Include point/prim/vert attribute metadata")
    point_attributes: list[str] | None = Field(
        default=None,
        description="Specific point attributes to sample. If omitted, the tool samples common attributes such as P, PartVel, PartAge, Noise, and PartForce when present.",
    )
    prim_attributes: list[str] | None = Field(
        default=None,
        description="Specific primitive attributes to sample. If omitted, no primitive attribute samples are returned unless requested.",
    )
    vert_attributes: list[str] | None = Field(
        default=None,
        description="Specific vertex attributes to sample. If omitted, no vertex attribute samples are returned unless requested.",
    )
    start: int = Field(default=0, ge=0, description="Starting element index for attribute sampling")
    count: int = Field(
        default=32, ge=1, le=2048, description="Max elements to sample per requested attribute"
    )
    delayed: bool = Field(
        default=False,
        description="Use TouchDesigner's delayed GPU readback mode where supported to reduce stalls",
    )


# ─────────────────────────────────────────────────────────────
# Cooking / Performance
# ─────────────────────────────────────────────────────────────


class CookingInfoInput(BaseModel):
    """Input for getting cooking/performance info."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(default="/", description="Root path to inspect")
    recurse: bool = Field(default=False, description="Recursively inspect children")
    sort_by: str = Field(default="cookTime", description="Sort by: 'cookTime' or 'cpuCookTime'")
    limit: int = Field(default=20, ge=1, le=100, description="Max nodes to return")


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────


class SearchNodesInput(BaseModel):
    """Input for searching nodes.

    v1.6.0 added ``scopes`` as a list-shaped superset of ``search_type``.
    When ``scopes`` is provided it wins; otherwise ``search_type`` is mapped
    to a single-element scope list for backward compat. The legacy scopes
    (``name``/``type``/``family``/``all``) forward to the existing TD-side
    ``/api/search`` endpoint. New scopes (``dat_text``, ``param_exprs``) are
    served host-side via the existing ``/api/exec`` endpoint, so they ship
    without a ``.tox`` rebuild requirement.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(..., description="Search string (case-insensitive)", min_length=1)
    path: str = Field(default="/", description="Root path to search from")
    search_type: str | None = Field(
        default=None,
        description=(
            "DEPRECATED — prefer ``scopes``. One of 'name', 'type', 'family', 'all'. "
            "When omitted, defaults to 'all' (or whatever ``scopes`` requests)."
        ),
    )
    scopes: list[str] | None = Field(
        default=None,
        description=(
            "Search scopes (v1.6.0+). Any of: 'name', 'type', 'family', 'all', "
            "'dat_text', 'param_exprs'. Multiple scopes are merged. Defaults to "
            "['all'] when neither scopes nor search_type is set."
        ),
    )
    limit: int = Field(default=50, ge=1, le=200, description="Max results")

    LEGACY_SCOPES: tuple[str, ...] = ("name", "type", "family", "all")
    NEW_SCOPES: tuple[str, ...] = ("dat_text", "param_exprs")

    @field_validator("search_type")
    @classmethod
    def validate_search_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ("name", "type", "family", "all"):
            raise ValueError("search_type must be 'name', 'type', 'family', or 'all'")
        return v

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        allowed = set(cls.LEGACY_SCOPES) | set(cls.NEW_SCOPES)
        bad = [s for s in v if s not in allowed]
        if bad:
            raise ValueError(f"Unknown scope(s) {bad}; allowed: {sorted(allowed)}")
        if not v:
            raise ValueError("scopes must contain at least one entry")
        return v

    def effective_scopes(self) -> list[str]:
        """Resolve the actual scope list to honor.

        Precedence: explicit ``scopes`` > ``search_type`` > default ``["all"]``.
        ``"all"`` is shorthand for the three legacy scopes.
        """
        if self.scopes:
            scopes = list(self.scopes)
        elif self.search_type:
            scopes = [self.search_type]
        else:
            scopes = ["all"]
        if "all" in scopes:
            expanded = ["name", "type", "family"]
            scopes = [s for s in scopes if s != "all"] + expanded
        # Stable de-dup
        seen: set[str] = set()
        result: list[str] = []
        for s in scopes:
            if s not in seen:
                result.append(s)
                seen.add(s)
        return result


# ─────────────────────────────────────────────────────────────
# Python Help / Introspection
# ─────────────────────────────────────────────────────────────


class PythonHelpInput(BaseModel):
    """Input for getting Python help documentation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    target: str = Field(
        ...,
        description="Python object/class to get help for (e.g. 'td', 'td.OP', 'tdu', 'td.TOP')",
        min_length=1,
    )


# ─────────────────────────────────────────────────────────────
# Custom Parameters / Project Lifecycle
# ─────────────────────────────────────────────────────────────


class CustomParameterSpec(BaseModel):
    """Specification for a single custom parameter to create on a COMP."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    kind: str = Field(
        ...,
        description=(
            "Custom parameter kind. Supported values: float, int, toggle, menu, str, rgb, rgba, pulse, "
            "file, filesave, folder, chop, comp, dat, mat, header"
        ),
        min_length=1,
    )
    name: str = Field(..., description="Parameter name", min_length=1, max_length=64)
    label: str | None = Field(default=None, description="Displayed parameter label")
    size: int = Field(default=1, ge=1, le=4, description="Tuple size for float/int params when supported")
    order: int | None = Field(default=None, description="Explicit display order on the page")
    replace: bool = Field(default=True, description="Replace existing parameter definition if it exists")
    menu_names: list[str] | None = Field(default=None, description="Internal menu values for menu params")
    menu_labels: list[str] | None = Field(default=None, description="Displayed menu labels for menu params")
    default: Any | None = Field(default=None, description="Default value (scalar or list for grouped params)")
    min: float | None = Field(default=None, description="Minimum numeric value where supported")
    max: float | None = Field(default=None, description="Maximum numeric value where supported")
    norm_min: float | None = Field(default=None, description="Normalized minimum UI range where supported")
    norm_max: float | None = Field(default=None, description="Normalized maximum UI range where supported")
    clamp_min: bool | None = Field(default=None, description="Clamp to the minimum value")
    clamp_max: bool | None = Field(default=None, description="Clamp to the maximum value")

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        allowed = {
            "float",
            "int",
            "toggle",
            "menu",
            "str",
            "string",
            "rgb",
            "rgba",
            "pulse",
            "file",
            "filesave",
            "folder",
            "chop",
            "comp",
            "dat",
            "mat",
            "header",
        }
        value = v.lower()
        if value not in allowed:
            raise ValueError(f"Unsupported custom parameter kind '{v}'")
        return value


class CustomParametersInput(BaseModel):
    """Create or update a custom parameter page on a COMP."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a COMP with custom parameters", min_length=1)
    page: str = Field(..., description="Custom page name", min_length=1, max_length=64)
    params: list[CustomParameterSpec] = Field(
        ...,
        min_length=1,
        description="One or more parameter specifications to create on the page",
    )


class ProjectLifecycleInput(BaseModel):
    """Input for save/load/undo/redo project lifecycle operations."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action: str = Field(
        ...,
        description=(
            "Lifecycle action: status, save, load, undo, redo, start_undo_block, end_undo_block, clear_undo"
        ),
        min_length=1,
    )
    path: str | None = Field(
        default=None,
        description="Project path for save/load. For save with no path, TouchDesigner will perform its default incremental save behavior.",
    )
    save_external_toxs: bool = Field(default=False, description="Also save external tox contents on save")
    name: str | None = Field(default=None, description="Undo block name when action=start_undo_block")
    enable: bool = Field(default=True, description="Whether a started undo block should record undo state")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {
            "status",
            "save",
            "load",
            "undo",
            "redo",
            "start_undo_block",
            "end_undo_block",
            "clear_undo",
        }
        value = v.lower()
        if value not in allowed:
            raise ValueError(f"Unknown project lifecycle action '{v}'")
        return value


# ─────────────────────────────────────────────────────────────
# Timeline
# ─────────────────────────────────────────────────────────────


class TimelineSetInput(BaseModel):
    """Input for controlling timeline playback."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action: str | None = Field(
        default=None, description="Timeline action: 'play', 'pause', or 'frame' (set specific frame)"
    )
    frame: int | None = Field(default=None, ge=0, description="Frame number to jump to (when action='frame')")
    fps: float | None = Field(default=None, gt=0, le=240, description="Set cook rate / FPS")


# ─────────────────────────────────────────────────────────────
# Pulse Parameter
# ─────────────────────────────────────────────────────────────


class PulseParamInput(BaseModel):
    """Input for pulsing a pulse-type parameter."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Node path", min_length=1)
    param: str = Field(..., description="Parameter name to pulse", min_length=1)


# ─────────────────────────────────────────────────────────────
# Error Checking
# ─────────────────────────────────────────────────────────────


class GetErrorsInput(BaseModel):
    """Input for checking node errors."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(default="/", description="Node path to check")
    recurse: bool = Field(default=True, description="Recursively check children")
    max_depth: int = Field(
        default=10, ge=1, le=50, description="Max recursion depth (prevents runaway on huge projects)"
    )


# ─────────────────────────────────────────────────────────────
# Macros
# ─────────────────────────────────────────────────────────────


class CreateMacroInput(BaseModel):
    """Input for creating a macro template network."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    parent_path: str = Field(
        default="/project1",
        description="Parent COMP path where the macro will be instantiated.",
    )
    macro_type: MacroType = Field(..., description="Macro template to create.")
    name: str | None = Field(
        default=None,
        description="Optional name prefix for all nodes created by this macro.",
    )
    nodeX: int = Field(
        default=0,
        description="Macro origin X position in the network editor.",
    )
    nodeY: int = Field(
        default=0,
        description="Macro origin Y position in the network editor.",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Override template parameter defaults with custom values.",
    )


class GetMacroParamsInput(BaseModel):
    """Input for inspecting parameter schema for a macro."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    macro_type: MacroType = Field(..., description="Macro template to inspect.")


# ─────────────────────────────────────────────────────────────
# Events / Subscriptions
# ─────────────────────────────────────────────────────────────


class SubscribeInput(BaseModel):
    """Input for subscribing to runtime TD events."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="TD node path to monitor, e.g. '/project1/audio1'.")
    event_types: list[str] = Field(
        default=["chop_change", "par_change"],
        description="Event types: chop_change, par_change, cook_complete, node_error, timeline.",
    )
    channels: list[str] | None = Field(
        default=None,
        description="Specific CHOP channels to monitor. None means all channels.",
    )
    params: list[str] | None = Field(
        default=None,
        description="Specific parameters to monitor. None means all tracked params.",
    )
    threshold: float | None = Field(
        default=None,
        description="Only emit events when delta exceeds this threshold.",
    )
    rate_limit: float = Field(
        default=0.016,
        ge=0.001,
        le=10.0,
        description="Minimum seconds between repeated events from same source.",
    )

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, values: list[str]) -> list[str]:
        allowed = {"chop_change", "par_change", "cook_complete", "node_error", "timeline"}
        invalid = [value for value in values if value not in allowed]
        if invalid:
            raise ValueError(f"Unsupported event types: {', '.join(invalid)}")
        return values


class UnsubscribeInput(BaseModel):
    """Input for removing a node subscription."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., description="TD node path to stop monitoring.")


class GetEventsInput(BaseModel):
    """Input for reading recent event history."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    event_type: str | None = Field(
        default=None,
        description="Optional event type filter.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of events to return.",
    )


# ─────────────────────────────────────────────────────────────
# Vision
# ─────────────────────────────────────────────────────────────


class CaptureAndAnalyzeInput(BaseModel):
    """Input for screenshot capture with optional AI analysis."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to TOP node to capture.")
    quality: float = Field(default=0.5, ge=0.0, le=1.0, description="JPEG quality 0.0–1.0.")
    confirm_image_capture: bool = Field(
        default=False,
        description=(
            "Must be true to execute the capture. "
            "This is an explicit acknowledgement that image payloads can consume tokens."
        ),
    )
    analyze: bool = Field(default=False, description="Request AI analysis if sampling is supported.")
    analysis_prompt: str | None = Field(default=None, description="Custom analysis prompt.")
    compare_with: str | None = Field(default=None, description="Optional resource URI to compare against.")


class VisualMonitorInput(BaseModel):
    """Input for periodic visual monitoring."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="TOP path to monitor.")
    interval: float = Field(default=2.0, ge=0.5, le=30.0, description="Capture interval seconds.")
    quality: float = Field(default=0.3, ge=0.0, le=1.0, description="JPEG quality.")
    include_image: bool = Field(
        default=False,
        description=(
            "When false (default), monitor events omit base64 image data to reduce token usage. "
            "Set true only when you explicitly want frame payloads in context."
        ),
    )
    confirm_high_token_mode: bool = Field(
        default=False,
        description=(
            "Must be true when include_image=true. This is an explicit acknowledgement that "
            "continuous image payloads can consume many tokens."
        ),
    )
    auto_analyze: bool = Field(default=False, description="Auto analyze each capture if sampling available.")
    analysis_prompt: str | None = Field(default=None, description="Optional analysis prompt.")


class StopMonitorInput(BaseModel):
    """Input for stopping visual monitor."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., description="TOP path being monitored.")


class StreamTopInput(BaseModel):
    """Input for continuous TOP stream."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="TOP path to stream continuously.")
    fps: float = Field(
        default=8.0,
        ge=0.5,
        le=60.0,
        description="Target stream frame rate.",
    )
    quality: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="JPEG quality for stream frames.",
    )
    include_image: bool = Field(
        default=False,
        description=(
            "When false (default), streamed resource updates omit base64 image data to reduce token usage. "
            "Set true only when you explicitly want frame payloads in context."
        ),
    )
    confirm_high_token_mode: bool = Field(
        default=False,
        description=(
            "Must be true when include_image=true. This is an explicit acknowledgement that "
            "continuous image payloads can consume many tokens."
        ),
    )
    emit_unchanged: bool = Field(
        default=False,
        description="When false, identical consecutive frames are suppressed.",
    )


class StopStreamTopInput(BaseModel):
    """Input for stopping a TOP stream."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(..., description="TOP path being streamed.")


# ─────────────────────────────────────────────────────────────
# Goal Optimizer
# ─────────────────────────────────────────────────────────────


class AdjustableParamInput(BaseModel):
    """Single parameter definition for optimizer search space."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Node path containing the parameter.")
    param: str = Field(..., description="Parameter name to adjust.")
    min_val: float = Field(..., description="Minimum allowed value.")
    max_val: float = Field(..., description="Maximum allowed value.")
    step: float = Field(default=0.05, gt=0.0, description="Step size per iteration.")

    @field_validator("max_val")
    @classmethod
    def validate_range(cls, value: float, info):
        minimum = info.data.get("min_val")
        if minimum is not None and value < minimum:
            raise ValueError("max_val must be >= min_val")
        return value


class OptimizeVisualInput(BaseModel):
    """Input for autonomous visual goal optimization."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    goal: str = Field(..., min_length=3, description="Natural-language optimization goal.")
    profile: str | None = Field(
        default=None,
        description="Optional optimizer profile: balanced | complexity | motion_rhythm | stability_guard",
    )
    objective_weights: dict[str, float] | None = Field(
        default=None,
        description="Optional explicit objective weights, e.g. {'motion_rhythm': 0.8, 'stability': 0.4}.",
    )
    output_top: str = Field(..., description="TOP path used as output reference.")
    adjustable_params: list[AdjustableParamInput] = Field(..., min_length=1, max_length=200)
    max_iterations: int = Field(default=10, ge=1, le=50)
    convergence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    safety_profile: str = Field(
        default="balanced",
        description="Optimizer safety profile: conservative | balanced | aggressive",
    )
    root_path: str = Field(
        default="/project1", description="Root scope for instability checks and snapshots."
    )
    snapshot_before: bool = Field(
        default=True, description="Capture snapshot before optimization loop starts."
    )

    @field_validator("safety_profile")
    @classmethod
    def validate_safety_profile(cls, value: str) -> str:
        if value not in {"conservative", "balanced", "aggressive"}:
            raise ValueError("safety_profile must be one of: conservative, balanced, aggressive")
        return value

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"balanced", "complexity", "motion_rhythm", "stability_guard"}:
            raise ValueError("profile must be one of: balanced, complexity, motion_rhythm, stability_guard")
        return value


# ─────────────────────────────────────────────────────────────
# Safety + Memory
# ─────────────────────────────────────────────────────────────


class ParamBound(BaseModel):
    """Single parameter safety bound."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Node path.")
    param: str = Field(..., description="Parameter name.")
    min_val: float | None = Field(default=None)
    max_val: float | None = Field(default=None)
    max_rate: float | None = Field(default=None, ge=0.0, description="Max value change per second.")


class SetBoundsInput(BaseModel):
    """Input for setting bounds."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bounds: list[ParamBound] = Field(..., min_length=1, max_length=500)
    enforce_mode: str = Field(default="clamp", description="clamp | reject | warn")

    @field_validator("enforce_mode")
    @classmethod
    def validate_enforce_mode(cls, value: str) -> str:
        if value not in {"clamp", "reject", "warn"}:
            raise ValueError("enforce_mode must be one of: clamp, reject, warn")
        return value


class ClearBoundsInput(BaseModel):
    """Input for clearing bounds."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    paths: list[str] | None = Field(default=None, description="Clear bounds for specific node paths.")


class DetectInstabilityInput(BaseModel):
    """Input for instability check."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(default="/project1", description="Root path to inspect.")


class SnapshotInput(BaseModel):
    """Input for scene snapshot."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str | None = Field(default=None, description="Optional snapshot label.")
    path: str = Field(default="/project1", description="Root path to snapshot.")
    include_visual: bool = Field(default=False, description="Include screenshot payload.")


class ListSnapshotsInput(BaseModel):
    """Input for listing snapshots."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    limit: int = Field(default=20, ge=1, le=100)


class RestoreSnapshotInput(BaseModel):
    """Input for restoring snapshot values."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    snapshot_id: str = Field(..., min_length=1)
    partial: list[str] | None = Field(default=None, description="Optional subset of node paths.")
    dry_run: bool = Field(default=False, description="Return diff only without applying.")


class DiffSnapshotsInput(BaseModel):
    """Input for snapshot diff."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    snapshot_a: str = Field(..., min_length=1)
    snapshot_b: str | None = Field(default=None, description="If omitted, diff snapshot_a vs live state.")


# ─────────────────────────────────────────────────────────────
# State/Timescale Semantics
# ─────────────────────────────────────────────────────────────


class StateVectorInput(BaseModel):
    """Input for aggregated scene state vector."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    path: str = Field(default="/project1", description="Root path for aggregated diagnostics.")
    force_refresh: bool = Field(default=False, description="Bypass cache and fetch fresh state.")


class TimescaleStateInput(BaseModel):
    """Input for beat/phrase derived timeline state."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    bpm_hint: float | None = Field(
        default=None,
        gt=0.0,
        le=400.0,
        description="Optional BPM hint. Defaults to 120 when omitted.",
    )
    beats_per_bar: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Musical beats per bar for phase calculations.",
    )


# ─────────────────────────────────────────────────────────────
# Runtime Architecture
# ─────────────────────────────────────────────────────────────


class TemporalAnalysisInput(BaseModel):
    """Input for asynchronous temporal dynamics observation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(default="/project1", description="Root path to observe.")
    observation_window: float = Field(
        default=3.0,
        ge=0.5,
        le=30.0,
        description="Observation duration in seconds.",
    )
    sample_rate: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Samples per second while observing.",
    )


# ─────────────────────────────────────────────────────────────
# Technique Memory
# ─────────────────────────────────────────────────────────────


class MemoryLearnInput(BaseModel):
    """Input for td_memory_learn — analyze a network subtree to extract a technique recipe."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Root path of the network subtree to analyze.")
    name: str = Field(default="", description="Human-readable name for this technique.")
    description: str = Field(default="", description="What this technique does.")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization.")
    max_depth: int = Field(default=3, ge=1, le=10, description="Max child depth to walk.")


class MemorySaveInput(BaseModel):
    """Input for td_memory_save — persist a technique dict to the library."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    technique: dict = Field(..., description="Technique dict (from td_memory_learn output).")
    scope: str = Field(default="project", description="'project' or 'global'.")
    name: str = Field(default="", description="Override technique name.")
    description: str = Field(default="", description="Override description.")
    tags: list[str] = Field(default_factory=list, description="Additional tags.")
    notes: str = Field(default="", description="Freeform notes about this technique.")


class MemoryRecallInput(BaseModel):
    """Input for td_memory_recall — search the technique library."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(default="", description="Text search across names, descriptions, tags.")
    tags: list[str] = Field(default_factory=list, description="Filter by tags.")
    scope: str = Field(default="all", description="'project', 'global', or 'all'.")
    limit: int = Field(default=20, ge=1, le=100, description="Max results.")


class MemoryReplayInput(BaseModel):
    """Input for td_memory_replay — rebuild a saved technique in a new location."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    technique_id: str = Field(..., description="ID of the saved technique to replay.")
    parent_path: str = Field(..., description="Parent COMP path where the technique will be rebuilt.")
    name_prefix: str = Field(default="", description="Optional prefix for created node names.")
    scope: str = Field(default="project", description="'project' or 'global'.")
    force: bool = Field(default=False, description="Skip build compatibility checks and replay anyway.")
    recreate_root: bool = Field(
        default=False,
        description=(
            "v1.4.7 Bug V opt-in. If True and the recipe's '/' entry has family='COMP', "
            "the replay creates that wrapper COMP under parent_path first and builds all "
            "children inside it. Default False preserves the existing flat-replay "
            "behavior where '/' is aliased to parent_path (children land as siblings). "
            "Set to True when you want a faithful clone of a COMP-wrapped technique."
        ),
    )


class MemoryFavoriteInput(BaseModel):
    """Input for td_memory_favorite — mark/rate a technique."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    technique_id: str = Field(..., description="ID of the technique.")
    favorite: bool = Field(default=True, description="Set favorite status.")
    rating: int = Field(default=-1, ge=-1, le=5, description="Rating 0-5, or -1 to skip.")
    scope: str = Field(default="project", description="'project' or 'global'.")


class MemoryPromoteInput(BaseModel):
    """Input for td_memory_promote — copy a project technique to the global library."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    technique_id: str = Field(..., description="Project technique ID to promote.")


class MemoryExportInput(BaseModel):
    """Input for td_memory_export — export technique library as JSON."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    scope: str = Field(default="project", description="'project' or 'global'.")


class MemoryImportInput(BaseModel):
    """Input for td_memory_import — import techniques from exported JSON."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    data: dict[str, Any] = Field(..., description="Exported library data (from td_memory_export).")
    scope: str = Field(default="project", description="'project' or 'global'.")
    overwrite: bool = Field(default=False, description="Overwrite existing techniques with same ID.")


class MemoryPreferencesInput(BaseModel):
    """Input for td_memory_preferences — get/set/list/delete preferences."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action: str = Field(..., description="One of: 'get', 'set', 'list', 'delete'.")
    key: str = Field(default="", description="Preference key (required for get/set/delete).")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = ("get", "set", "list", "delete")
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed} — got '{v}'")
        return v

    value: Any = Field(default=None, description="Value to set (required for 'set').")
    scope: str = Field(default="project", description="'project' or 'global'.")


class MemoryListInput(BaseModel):
    """Input for td_memory_list — list techniques with filters."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    scope: str = Field(default="all", description="'project', 'global', or 'all'.")
    tags: list[str] = Field(default_factory=list, description="Filter by tags.")
    favorites_only: bool = Field(default=False, description="Only return favorites.")
    limit: int = Field(default=50, ge=1, le=200, description="Max results.")


# ─────────────────────────────────────────────────────────────
# Planning & Validation
# ─────────────────────────────────────────────────────────────


class PlanPatchInput(BaseModel):
    """Input for generating a structured patch plan."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    intent: str = Field(..., description="What you want to achieve", min_length=1)
    target_path: str = Field(default="/project1", description="Target path to plan changes for")
    recipe_id: str | None = Field(default=None, description="Optional recipe ID to base plan on")


class PreflightPatchInput(BaseModel):
    """Input for validating a plan before execution."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    plan: dict[str, Any] = Field(..., description="Plan dict from td_plan_patch to validate")


class ValidateRecipeInput(BaseModel):
    """Input for validating a technique recipe."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recipe_id: str | None = Field(default=None, description="Recipe ID to validate")
    recipe: dict[str, Any] | None = Field(default=None, description="Inline recipe dict to validate")
    scope: str = Field(default="project", description="'project' or 'global'")


class AuditProjectInput(BaseModel):
    """Input for auditing a project subtree."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    root_path: str = Field(default="/project1", description="Root path to audit")


# ─────────────────────────────────────────────────────────────
# Vision Diagnostics (tools 76-77)
# ─────────────────────────────────────────────────────────────


class CaptureFrameInput(BaseModel):
    """Input for capturing a single frame from a TOP node."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a TOP node to capture")
    quality: float = Field(default=0.8, ge=0.0, le=1.0, description="JPEG quality 0.0-1.0")
    confirm: bool = Field(default=False, description="If True, include base64 image in response")


class AnalyzeFrameInput(BaseModel):
    """Input for analyzing pixel data of a TOP node."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to a TOP node to analyze")
    modes: list[str] = Field(
        default=["histogram", "luminance"],
        description="Analysis modes: histogram, luminance, alpha_coverage, color_dominant, roi_diff",
    )
    roi: list[int] | None = Field(
        default=None, description="Region of interest [x, y, w, h] for roi_diff mode"
    )
    reference_path: str | None = Field(default=None, description="Reference TOP path for roi_diff mode")


# ─────────────────────────────────────────────────────────────
# TD 2025 Native System Tools
# ─────────────────────────────────────────────────────────────


class TDResourcesInspectInput(BaseModel):
    """Input for inspecting TDResources."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: str | None = Field(
        default=None, description="Category: fonts, icons, defaults, or None for all"
    )


class ComponentStandardizeInput(BaseModel):
    """Input for auditing/fixing COMP standardization."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to COMP to audit", min_length=1)
    fix: bool = Field(default=False, description="If True, auto-fix issues (wrapped in undo block)")


class ColorPipelineInput(BaseModel):
    """Input for color pipeline inspection."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# ── Official Recommendation Tools (tools 84-86) ──────────────


class RecommendOfficialInput(BaseModel):
    """Input for recommending official palette/operator components."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    goal: str = Field(..., description="What you want to achieve", min_length=1)


class FindOfficialExampleInput(BaseModel):
    """Input for finding official examples and snippets."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(..., description="Search query for official examples", min_length=1)
    family: str | None = Field(default=None, description="Filter by operator family: TOP, CHOP, SOP, etc.")


class ExplainBetterWayInput(BaseModel):
    """Input for suggesting better official alternatives."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    intent: str = Field(..., description="What you intend to do", min_length=1)
    current_plan: str | None = Field(default=None, description="Current approach to evaluate")
