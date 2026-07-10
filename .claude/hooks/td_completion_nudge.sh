#!/usr/bin/env bash
# Stop hook for TDPilot
# When Claude tries to end a turn, surface a reminder if recent activity
# touched TouchDesigner state. Cheap, non-blocking — emits a JSON
# systemMessage.
#
# Why non-blocking: Stop hooks that exit 2 force the agent to keep running,
# which can become a perpetual loop if the verifier has a false-positive.
# A visible reminder is enough leverage for the discipline rule to fire.
#
# Exit 0 always.

set +e

# Read input but don't use it — Stop input is just session metadata.
# Drain stdin so the hook protocol is satisfied.
INPUT=$(cat 2>/dev/null || true)

cat <<'EOF'
{"systemMessage": "[Stop hook] Did you call td_screenshot on every render TOP/output null TOP touched this session? Did you describe what you actually saw? Did you set viewer=True on test/demo COMPs? `0 errors` is not a green light. (See project CLAUDE.md §1.)"}
EOF

exit 0
