"""Release-gate constants shared across tests, scripts, and runtime.

Any threshold that needs to be in sync between a test assertion and a release
script lives here. Bump once per release.
"""

from __future__ import annotations

# Minimum tool count enforced by contract tests, the registry smoke check,
# the full e2e suite, and the runtime stress matrix. Kept as a floor (not an
# exact match) so adding tools never breaks downstream checks.
# 2026-04-25: bumped 97 → 101 with td_knowledge_{save,recall,get,list}.
# 2026-05-02: dropped 101 → 99 (community brain tools removed from public repo).
# 2026-05-02: bumped 99 → 101 with td_get_focus + td_locations (v1.6.0 Phase 1).
# 2026-05-02: bumped 101 → 102 with td_get_hints (v1.6.0 Phase 2).
# 2026-05-02: bumped 102 → 103 with td_component_notes (v1.6.0 Phase 3).
EXPECTED_MIN_TOOL_COUNT: int = 103
