#!/usr/bin/env bash
# ============================================================================
#  TDPilot -> Claude Code plugin installer
#
#  One-liner:
#    curl -fsSL https://raw.githubusercontent.com/dreamrec/TDPilot/main/scripts/install_claude_plugin.sh | bash
#
#  What it does:
#    1. Ensures `claude` CLI is on PATH.
#    2. Adds dreamrec/TDPilot as a plugin marketplace.
#    3. Installs the tdpilot plugin.
#    4. Prints next steps (TD-side setup).
#
#  Idempotent: re-running upgrades the plugin.
# ============================================================================

set -euo pipefail

MARKETPLACE="dreamrec/TDPilot"
PLUGIN_REF="tdpilot@dreamrec-TDPilot"

log()   { printf "\033[1;36m[TDPilot]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[TDPilot]\033[0m %s\n" "$*" >&2; }
die()   { printf "\033[1;31m[TDPilot]\033[0m %s\n" "$*" >&2; exit 1; }

# ---------- Step 1: check claude CLI ----------

if ! command -v claude >/dev/null 2>&1; then
    die "The 'claude' CLI is not on PATH. Install Claude Code first: https://claude.com/claude-code"
fi

log "Found Claude Code: $(claude --version 2>&1 | head -1)"

# ---------- Step 1b: ensure uv is on PATH (MCP server uses it) ----------

if ! command -v uv >/dev/null 2>&1; then
    log "uv not found — installing (astral.sh pinned 0.6.10)..."
    UV_PINNED_VERSION="${TDPILOT_UV_VERSION:-0.6.10}"
    if [ "$UV_PINNED_VERSION" = "latest" ]; then
        UV_INSTALL_URL="https://astral.sh/uv/install.sh"
    else
        UV_INSTALL_URL="https://astral.sh/uv/${UV_PINNED_VERSION}/install.sh"
    fi
    curl -LsSf "$UV_INSTALL_URL" | sh

    # uv installs to ~/.local/bin on macOS/Linux
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v uv >/dev/null 2>&1; then
        warn "uv installed but not on PATH yet. Open a new terminal and re-run."
        warn "(Plugin installation will continue; MCP server may fail to start on first use.)"
    else
        log "uv ready: $(uv --version 2>&1)"
    fi
else
    log "Found uv: $(uv --version 2>&1)"
fi

# ---------- Step 2: add marketplace ----------

log "Adding marketplace: $MARKETPLACE"
# Capture output + exit code separately instead of grepping for specific strings,
# which are not stable across Claude Code versions.
_marketplace_output="$(claude plugin marketplace add "$MARKETPLACE" 2>&1)"
_marketplace_status=$?
if [ "$_marketplace_status" -eq 0 ]; then
    log "Marketplace added."
else
    # "already added" is fine; any other non-zero is a real error.
    if printf "%s" "$_marketplace_output" | grep -qi "already"; then
        log "Marketplace already registered, continuing."
    else
        printf "%s\n" "$_marketplace_output"
        die "plugin marketplace add failed (exit $_marketplace_status)."
    fi
fi

# ---------- Step 3: install the plugin ----------

log "Installing plugin: $PLUGIN_REF"
claude plugin install "$PLUGIN_REF"

# ---------- Step 4: next steps ----------

cat <<'EOF'

[TDPilot] Plugin installed!

Next steps:

  1. Open TouchDesigner (2025.30000 or newer).

  2. In a running Claude Code session, the 'touchdesigner' MCP server will
     auto-start the next time it's needed. Trigger it with something like:

         "What's in my TouchDesigner project?"

     Claude will start the TDPilot MCP server from the plugin cache. First
     run takes a few seconds while uv resolves the Python dependencies.

  3. Load the TDPilot .tox component into TouchDesigner. Either:

     (a) Drag td_component/tdpilot_v1_3.tox from the plugin cache into your
         /local container. The cache lives at:

           ~/.claude/plugins/cache/dreamrec-TDPilot/tdpilot/<version>/

     (b) Or run setup_mcp_in_td.py in the TD Textport (it auto-detects
         the plugin cache path).

     Option (a) is recommended for first-time setup.

  4. To update the plugin later:

         claude plugin update tdpilot@dreamrec-TDPilot

  5. To uninstall:

         claude plugin uninstall tdpilot@dreamrec-TDPilot
         claude plugin marketplace remove dreamrec-TDPilot

Docs: https://github.com/dreamrec/TDPilot

EOF
