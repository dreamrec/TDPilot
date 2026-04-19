"""TouchDesigner MCP Server — AI-powered control of TouchDesigner via MCP."""

__version__ = "1.4.1"

TOX_FILENAME = "tdpilot_v1_3.tox"


def normalize_transport(raw: str) -> str:
    """Normalize transport name: strip, lowercase, underscores to hyphens."""
    return raw.strip().lower().replace("_", "-")
