"""TouchDesigner MCP Server — AI-powered control of TouchDesigner via MCP."""

__version__ = "1.6.0"

# v1.4.7: renamed from ``tdpilot_v1_3.tox`` (legacy v1.3-era filename) to a
# version-less, stable filename. The TD component's API_VERSION lives inside
# the .tox itself (see ``td_component/mcp_webserver_callbacks.py``), so the
# filename doesn't need to carry a version marker — and the old ``v1_3`` was
# misleading as soon as v1.4 shipped. LEGACY_TOX_FILENAMES is consulted as a
# fallback so existing v1.3/v1.4.x installs (where ``~/.tdpilot/td_component/``
# still holds the old name) keep working until their next ``install.sh`` run
# copies the renamed file over.
TOX_FILENAME = "tdpilot.tox"
LEGACY_TOX_FILENAMES: tuple[str, ...] = ("tdpilot_v1_3.tox",)


def normalize_transport(raw: str) -> str:
    """Normalize transport name: strip, lowercase, underscores to hyphens."""
    return raw.strip().lower().replace("_", "-")
