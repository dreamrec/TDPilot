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
# 2026-05-12: bumped 103 → 104 with td_tool_batch (deepseek-v4 backport).
# 2026-05-18: bumped 104 → 106 with td_get_activity_log + td_self_update
#             (v1.6.16 agent-observability + auto-update surface).
# 2026-06-16: bumped 106 → 109 with td_brain_plan, td_brain_execute,
#             and td_transaction_apply (vNext correctness brain).
# 2026-06-16: bumped 109 → 110 with td_cockpit_render (optional MCP Apps cockpit).
# 2026-06-24: bumped 110 → 111 with td_sync_status (one-call install/version
#             truth across server, live TD component, .tox, caches, npm/GitHub).
# 2026-06-24: bumped 111 → 112 with td_sync_diagnose (strict live sync,
#             version-skew, endpoint, and auth fingerprint diagnostics).
# 2026-07-09: bumped 112 → 114 with td_brain_ground + td_brain_propose
#             (host-authored BrainPlan drafting loop: grounding pack + review
#             gate — the LLM-as-planner flip).
EXPECTED_MIN_TOOL_COUNT: int = 114
