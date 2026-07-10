#!/usr/bin/env bash
# SessionStart hook for TDPilot
# Promotes feedback_*.md memory files from "conditionally loaded" to
# "guaranteed system-reminder at session start". Output goes into Claude's
# context as additional context.
#
# Exit 0 always — failure to find memories must NOT block session start.

set +e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${PWD}}"
# Claude's project-memory directory is the absolute project path with every
# non-alphanumeric character normalized to a dash. Compute it at runtime so
# this source-scoped hook remains portable and contains no personal path.
PROJECT_SLUG=$(printf '%s' "$PROJECT_DIR" | sed 's/[^A-Za-z0-9]/-/g')
MEMORY_DIR="${HOME}/.claude/projects/${PROJECT_SLUG}/memory"

if [ ! -d "$MEMORY_DIR" ]; then
  exit 0
fi

# Concatenate only memory files with `type: feedback` in frontmatter.
# This filters out technique-essay memories (type: project) that happen to
# start with feedback_*. Cap at ~6KB so we don't blow context budget.
echo "## Loaded feedback memories (binding rules from prior sessions):"
echo ""
for f in "$MEMORY_DIR"/*.md; do
  [ -f "$f" ] || continue
  # Frontmatter sits in the first ~10 lines. Match exactly `type: feedback`.
  if head -10 "$f" | grep -qE '^type:[[:space:]]*feedback[[:space:]]*$'; then
    basename "$f"
    echo "----------------------------------------"
    head -c 1500 "$f"
    echo ""
    echo ""
  fi
done | head -c 6000

exit 0
