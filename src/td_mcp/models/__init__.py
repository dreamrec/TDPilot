"""Pydantic Input Models for TouchDesigner MCP Tools.

Previously a single 1,137-line ``models.py``. Now a package so classes can be
migrated into themed submodules (nodes, params, memory, vision, ...) without
breaking any existing `from td_mcp.models import X` call.

Current state:
- ``_legacy.py``  — all 70+ input classes (the original models.py content)
- ``__init__.py`` (this file) re-exports everything from ``_legacy``

Future migrations should move subsets of classes into new submodules
(``nodes.py``, ``params.py``, ``memory.py``, ``vision.py``, ``knowledge.py``,
``safety.py``, ``macros.py``, ``planning.py``) and have this file
``from .new_submodule import *`` alongside ``from ._legacy import *``. The
public import surface stays identical.
"""

from __future__ import annotations

# Star-import everything from the legacy file. Everything listed in
# `_legacy.__all__` (or all public names if no __all__) becomes importable as
# ``from td_mcp.models import X``, matching the pre-split behavior exactly.
from td_mcp.models._legacy import *  # noqa: F401,F403
