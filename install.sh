#!/bin/bash
# ============================================================================
#  TDPilot — macOS Installer
#  Run: bash install.sh
# ============================================================================

set -euo pipefail

REPO_URL="https://github.com/dreamrec/TDPilot.git"
REPO_DIR_NAME="TDPilot"
CONFIG_DIR="${MCP_CONFIG_DIR:-$HOME/Library/Application Support/Claude}"
CONFIG_PATH="${MCP_CONFIG_PATH:-$CONFIG_DIR/claude_desktop_config.json}"

echo ""
echo "  TDPilot — Installer for macOS"
echo "  ============================="
echo ""

# ---------- Step 1: Check / Install uv ----------

echo "[1/4] Checking for uv..."

UV_PINNED_VERSION="${TDPILOT_UV_VERSION:-0.6.10}"

if command -v uv &>/dev/null; then
    UV_PATH=$(which uv)
    echo "  Found uv: $(uv --version) at $UV_PATH"
else
    echo "  uv not found. Installing pinned version ${UV_PINNED_VERSION}..."
    # Pin the uv installer URL to a specific version. If you want the latest
    # uv, override by exporting TDPILOT_UV_VERSION=latest before running.
    if [ "$UV_PINNED_VERSION" = "latest" ]; then
        UV_INSTALL_URL="https://astral.sh/uv/install.sh"
    else
        UV_INSTALL_URL="https://astral.sh/uv/${UV_PINNED_VERSION}/install.sh"
    fi
    curl -LsSf "$UV_INSTALL_URL" | sh 2>&1

    # Reload PATH
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv &>/dev/null; then
        UV_PATH=$(which uv)
        echo "  uv installed: $UV_PATH"
    else
        echo "  ERROR: uv installed but not found in PATH."
        echo "  Close this terminal, open a new one, and run this script again."
        exit 1
    fi
fi

UV_PATH=$(which uv)

# ---------- Step 2: Locate or clone the repo ----------

echo ""
echo "[2/4] Setting up repository..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    REPO_PATH="$SCRIPT_DIR"
    echo "  Running from repo: $REPO_PATH"
else
    INSTALL_DIR="$HOME/$REPO_DIR_NAME"

    if [ -f "$INSTALL_DIR/pyproject.toml" ]; then
        REPO_PATH="$INSTALL_DIR"
        echo "  Found existing install: $REPO_PATH"
    else
        echo "  Cloning to: $INSTALL_DIR"
        if command -v git &>/dev/null; then
            git clone "$REPO_URL" "$INSTALL_DIR" 2>&1
        else
            echo "  git not found — downloading ZIP..."
            ZIP_URL="https://github.com/dreamrec/TDPilot/archive/refs/heads/main.zip"
            ZIP_PATH="/tmp/td-mcp.zip"
            curl -L -o "$ZIP_PATH" "$ZIP_URL"
            unzip -q "$ZIP_PATH" -d /tmp/td-mcp-extract
            mv "/tmp/td-mcp-extract/${REPO_DIR_NAME}-main" "$INSTALL_DIR"
            rm -f "$ZIP_PATH"
            rm -rf /tmp/td-mcp-extract
        fi
        REPO_PATH="$INSTALL_DIR"
        echo "  Downloaded to: $REPO_PATH"
    fi
fi

# ---------- Step 3: Configure MCP Desktop Client ----------

echo ""
echo "[3/4] Configuring MCP desktop client..."

mkdir -p "$CONFIG_DIR"

# Backup existing config
if [ -f "$CONFIG_PATH" ]; then
    BACKUP_PATH="${CONFIG_PATH}.backup_$(date +%Y%m%d_%H%M%S)"
    cp "$CONFIG_PATH" "$BACKUP_PATH"
    echo "  Backed up config to: $BACKUP_PATH"
fi

# Use Python to safely merge JSON (always available on macOS) and generate a secret.
python3 -c "
import json, os, secrets, sys

config_path = '$CONFIG_PATH'
repo_path = '$REPO_PATH'
uv_path = '$UV_PATH'

# Load or create
if os.path.exists(config_path):
    try:
        with open(config_path) as f:
            text = f.read().strip()
            config = json.loads(text) if text else {}
    except (json.JSONDecodeError, ValueError):
        print('  WARNING: Existing config has invalid JSON. Creating fresh config.')
        config = {}
else:
    config = {}

# Ensure mcpServers exists
if 'mcpServers' not in config:
    config['mcpServers'] = {}

# Preserve an existing secret if we already installed once.
existing = config['mcpServers'].get('touchdesigner', {})
existing_secret = existing.get('env', {}).get('TD_MCP_SHARED_SECRET', '')
shared_secret = existing_secret or secrets.token_hex(32)

config['mcpServers']['touchdesigner'] = {
    'command': uv_path,
    'args': ['run', '--directory', repo_path, 'tdpilot'],
    'env': {
        'TD_MCP_HOST': '127.0.0.1',
        'TD_MCP_PORT': '9981',
        'TD_MCP_WS_PORT': '9982',
        'TD_MCP_EXEC_MODE': 'restricted',
        'TD_MCP_REQUIRE_AUTH': '1',
        'TD_MCP_SHARED_SECRET': shared_secret,
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
os.chmod(config_path, 0o600)

print('  Config updated: ' + config_path)

# Also write the secret into a TD-readable env file so the .tox picks it up.
env_path = os.path.join(repo_path, '.tdpilot.env')
with open(env_path, 'w') as f:
    f.write('TD_MCP_SHARED_SECRET=' + shared_secret + '\n')
    f.write('TD_MCP_REQUIRE_AUTH=1\n')
    f.write('TD_MCP_EXEC_MODE=restricted\n')
os.chmod(env_path, 0o600)
print('  Secret written to: ' + env_path + ' (TD reads this at startup)')
"

# ---------- Step 4: Summary ----------

echo ""
echo "[4/4] Done!"
echo ""
echo "  ========================================"
echo "  INSTALL COMPLETE"
echo "  ========================================"
echo ""
echo "  Repo location:   $REPO_PATH"
echo "  Config file:     $CONFIG_PATH"
echo "  uv path:         $UV_PATH"
echo ""
echo "  NEXT STEPS:"
echo "  1. Restart your MCP desktop client"
echo "  2. Open TouchDesigner and load the component (once per session):"
echo "     Option A: Drag td_component/tdpilot_v1_3.tox into /local"
echo "     Option B: Run in Textport:"
echo "       exec(open(\"$REPO_PATH/setup_mcp_in_td.py\").read(), globals(), globals())"
echo "  3. Ask your AI client: 'What's in my TouchDesigner project?'"
echo ""
echo "  Installing into /local means TDPilot persists across project opens."
echo ""
echo "  .tox file is at:"
echo "  $REPO_PATH/td_component/tdpilot_v1_3.tox"
echo ""
