#!/usr/bin/env bash
# Block commits that leak hardcoded personal filesystem paths.
#
# Detects macOS-style (``/Users/<name>/``) and Windows-style
# (``C:\Users\<name>\``) paths in tracked files. Linux ``/home/<name>/``
# is also flagged but only when it looks user-named (not generic
# ``/home/user/`` which is commonly used as a placeholder in docs).
#
# This check runs in CI (`.github/workflows/ci.yml`) and can be wired
# into a local pre-commit hook for fast feedback. Exits 0 on clean,
# 1 on any match.
#
# Remediation when a match is flagged:
#   - Replace with ``<REPO_ROOT>``, ``<USER_HOME>``, ``<USER_DESKTOP>``,
#     ``<DERIVATIVE_DOCS>`` or similar descriptive placeholder
#   - Use ``$HOME``, ``${HOME}`` in shell contexts
#   - Use ``pathlib.Path.home()`` or ``os.path.expanduser("~")`` in code

set -eu

# Pattern matches personal-looking paths:
#   /Users/<name>/             — macOS
#   C:\Users\<name>            — Windows (backslashes escaped 4x for bash+regex)
#   /home/<name>/              — Linux with a user-ish name (alpha-start, 3+ chars)
# The regex character classes after each prefix prevent matching legit
# placeholders we've introduced like ``/Users/<USER_NAME>``.
PATTERN='(/Users/[A-Za-z][A-Za-z0-9._-]*/)|(C:\\\\Users\\\\[A-Za-z])|(/home/[a-z][a-z0-9_-]{2,}/)'

# Pathspec exclusions. git grep respects these natively.
EXCLUDES=(
  ':!.venv'
  ':!.venv/**'
  ':!node_modules'
  ':!data/normalized'
  ':!data/brains'
  # The script contains the pattern as a regex literal — don't flag itself.
  ':!scripts/check_no_personal_paths.sh'
  # Lockfiles can contain resolved absolute paths from the build machine;
  # they get regenerated per-clone and don't leak intent.
  ':!uv.lock'
  ':!npm/package-lock.json'
)

if git grep -nE "$PATTERN" -- "${EXCLUDES[@]}" 2>/dev/null; then
  echo ""
  echo "ERROR: hardcoded personal filesystem path(s) detected above."
  echo ""
  echo "Replace with a portable placeholder:"
  echo "  <REPO_ROOT>        — for the repo's top-level directory"
  echo "  <USER_HOME>        — for the user's home directory"
  echo "  <USER_DESKTOP>     — for ~/Desktop-style locations"
  echo "  \$HOME or \${HOME}   — in shell snippets"
  echo "  ~/                 — in user-facing install instructions"
  echo ""
  echo "See commit 0ce4341 for an example sanitization sweep."
  exit 1
fi

echo "OK: no personal filesystem paths detected in tracked files."
