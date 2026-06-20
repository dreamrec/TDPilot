#!/usr/bin/env bash
# Package build smoke check — verifies the three distribution artifacts
# (wheel, npm tarball, plugin zip) each build cleanly and contain the
# critical files we expect.
#
# Run locally before tagging a release, or in CI as a release gate.
#
# Usage:
#   bash scripts/check_package_builds.sh             # build + verify, keep artifacts
#   bash scripts/check_package_builds.sh --cleanup   # delete artifacts on success
#
# Exit codes:
#   0 — all three artifacts built and contained required files
#   1 — at least one artifact build or content check failed

# Explicit error accumulation — not `set -e`, so we collect every failure
# instead of stopping at the first one (far more useful in CI logs).
set -o pipefail

CLEANUP=0
if [[ "${1:-}" == "--cleanup" ]]; then
    CLEANUP=1
fi

# Move to repo root (script location is scripts/)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Colors are cheap and make failure scanning easier in CI logs
C_RED=$'\033[31m'
C_GREEN=$'\033[32m'
C_YELLOW=$'\033[33m'
C_RESET=$'\033[0m'

fail() {
    echo "${C_RED}FAIL${C_RESET} $*"
}
ok() {
    echo "${C_GREEN}OK${C_RESET}   $*"
}
info() {
    echo "${C_YELLOW}INFO${C_RESET} $*"
}

# Per-artifact temp dirs so failures don't leak across steps
SMOKE_DIR="$(mktemp -d -t tdpilot-smoke-XXXX)"
trap 'rm -rf "$SMOKE_DIR"' EXIT

ERRORS=0

# ─────────────────────────────────────────────────────────────
# 1. Python wheel — `uv build`
# ─────────────────────────────────────────────────────────────
info "Building Python wheel via uv build..."
WHEEL_OUT="$SMOKE_DIR/wheel"
mkdir -p "$WHEEL_OUT"

if ! uv build --wheel --out-dir "$WHEEL_OUT" >/dev/null; then
    fail "uv build failed"
    ERRORS=$((ERRORS + 1))
else
    WHEEL_FILE=$(ls "$WHEEL_OUT"/tdpilot-*-py3-none-any.whl 2>/dev/null | head -1)
    if [[ -z "$WHEEL_FILE" ]]; then
        fail "wheel artifact not found in $WHEEL_OUT"
        ERRORS=$((ERRORS + 1))
    else
        # Capture once, grep many times — avoids pipefail/exit weirdness with
        # piped unzip | grep -q under `set -o pipefail`.
        WHEEL_CONTENTS=$(unzip -l "$WHEEL_FILE" | awk '{print $NF}')
        for required in "td_mcp/server.py" "td_mcp/tool_registry.py" "td_mcp/__init__.py"; do
            if grep -q "^${required}\$" <<< "$WHEEL_CONTENTS"; then
                ok "wheel contains ${required}"
            else
                fail "wheel missing ${required}"
                ERRORS=$((ERRORS + 1))
            fi
        done
    fi
fi

# ─────────────────────────────────────────────────────────────
# 2. npm tarball — `npm pack`
# ─────────────────────────────────────────────────────────────
info "Packing npm tarball via npm pack..."
NPM_OUT="$SMOKE_DIR/npm"
mkdir -p "$NPM_OUT"

if ! (cd npm && npm pack --pack-destination "$NPM_OUT" >/dev/null 2>&1); then
    fail "npm pack failed"
    ERRORS=$((ERRORS + 1))
else
    NPM_TARBALL=$(ls "$NPM_OUT"/tdpilot-*.tgz 2>/dev/null | head -1)
    if [[ -z "$NPM_TARBALL" ]]; then
        fail "npm tarball not found in $NPM_OUT"
        ERRORS=$((ERRORS + 1))
    else
        # Spot-check required files listed in npm/package.json "files"
        # tar -t lists entries; the prefix is "package/" inside npm tarballs.
        CONTENTS=$(tar -tzf "$NPM_TARBALL")
        for required in "package/run.js" "package/install.js" "package/brains.js" "package/README.md"; do
            if grep -q "^${required}\$" <<< "$CONTENTS"; then
                ok "npm tarball contains ${required#package/}"
            else
                fail "npm tarball missing ${required#package/}"
                ERRORS=$((ERRORS + 1))
            fi
        done
    fi
fi

# ─────────────────────────────────────────────────────────────
# 3. Plugin zip — scripts/build_plugin_zip.py
# ─────────────────────────────────────────────────────────────
info "Building plugin zip via scripts/build_plugin_zip.py..."
PLUGIN_OUT="$SMOKE_DIR/tdpilot.plugin"

if ! uv run python scripts/build_plugin_zip.py --output "$PLUGIN_OUT" >/dev/null; then
    fail "plugin zip build failed"
    ERRORS=$((ERRORS + 1))
else
    if [[ ! -f "$PLUGIN_OUT" ]]; then
        fail "plugin zip not found at $PLUGIN_OUT"
        ERRORS=$((ERRORS + 1))
    else
        CONTENTS=$(unzip -l "$PLUGIN_OUT" | awk '{print $NF}')
        for required in ".mcp.json" ".claude-plugin/plugin.json" "td_component/tdpilot.tox" "README.md"; do
            if grep -q "^${required}\$" <<< "$CONTENTS"; then
                ok "plugin zip contains ${required}"
            else
                fail "plugin zip missing ${required}"
                ERRORS=$((ERRORS + 1))
            fi
        done
    fi
fi

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
echo
if [[ $ERRORS -eq 0 ]]; then
    echo "${C_GREEN}All package build smoke checks passed.${C_RESET}"
    if [[ $CLEANUP -eq 1 ]]; then
        info "Cleanup: removing $SMOKE_DIR"
        # trap handles this, but explicit is nicer in logs
    else
        info "Artifacts at $SMOKE_DIR (pass --cleanup to delete on success)"
        trap - EXIT  # preserve dir
    fi
    exit 0
else
    echo "${C_RED}Package build smoke FAILED with $ERRORS error(s).${C_RESET}"
    info "Artifacts left at $SMOKE_DIR for inspection"
    trap - EXIT  # preserve dir
    exit 1
fi
