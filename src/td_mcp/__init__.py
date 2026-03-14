"""TouchDesigner MCP Server — AI-powered control of TouchDesigner via MCP."""

__version__ = "1.2.0"

TOX_FILENAME = "tdpilot_v1_2.tox"


def normalize_transport(raw: str) -> str:
    """Normalize transport name: strip, lowercase, underscores to hyphens."""
    return raw.strip().lower().replace("_", "-")
