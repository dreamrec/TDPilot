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
EXPECTED_MIN_TOOL_COUNT: int = 99
