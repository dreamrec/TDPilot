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
            # Auto-pin to the latest reachable tag rather than HEAD of main
            # so the install matches the most recent published release.
            # Without this, fresh clones run whatever bleeding-edge code is
            # on main mid-development. Falls back to main with a notice if
            # no tags exist (offline / private fork / pre-release).
            LATEST_TAG="$( cd "$INSTALL_DIR" && git describe --tags --abbrev=0 2>/dev/null || true )"
            if [ -n "$LATEST_TAG" ]; then
                if ( cd "$INSTALL_DIR" && git checkout "$LATEST_TAG" >/dev/null 2>&1 ); then
                    echo "  Pinned to $LATEST_TAG"
                else
                    echo "  WARN: Could not check out $LATEST_TAG; staying on main"
                fi
            else
                echo "  WARN: No release tag found upstream; staying on main"
            fi
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

# Use Python to safely merge JSON (always available on macOS) and provision the
# canonical secret file. Paths are passed via the environment (NOT interpolated
# into the Python source), so a path containing a quote/newline can't break out
# of the string literal or inject code. install.ps1 keeps these as data the
# same way.
#
# Secret unification (audit batch E): ~/.tdpilot/.tdpilot.env is THE secret
# file. The client config gets TD_MCP_AUTOGENERATE_SECRET=1 instead of a
# literal secret (matching the shipped .mcp.json), and the installer writes
# only the canonical file — no repo-local .tdpilot.env, no secret material in
# claude_desktop_config.json. Existing secrets are preserved in this priority:
# canonical file > legacy repo-local file > legacy client-config literal;
# otherwise a fresh secrets.token_urlsafe(32) is generated (the same approach
# auth_bootstrap.maybe_generate_secret and the TD-side autostart use).
TDPILOT_CONFIG_PATH="$CONFIG_PATH" \
TDPILOT_REPO_PATH="$REPO_PATH" \
TDPILOT_UV_PATH="$UV_PATH" \
python3 -c "
import json, os, secrets, sys

config_path = os.environ['TDPILOT_CONFIG_PATH']
repo_path = os.environ['TDPILOT_REPO_PATH']
uv_path = os.environ['TDPILOT_UV_PATH']
canonical_env_path = os.path.join(os.path.expanduser('~'), '.tdpilot', '.tdpilot.env')


def read_env_secret(path):
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('TD_MCP_SHARED_SECRET='):
                    value = line.partition('=')[2].strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('\'', chr(34)):
                        value = value[1:-1]
                    return value
    except OSError:
        pass
    return ''


# Load or create the client config
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

if 'mcpServers' not in config:
    config['mcpServers'] = {}

# Migrate any pre-unification secret so re-running the installer never
# rotates a working secret out from under a live TD session.
existing = config['mcpServers'].get('touchdesigner', {})
legacy_config_secret = existing.get('env', {}).get('TD_MCP_SHARED_SECRET', '')
legacy_repo_secret = read_env_secret(os.path.join(repo_path, '.tdpilot.env'))
canonical_secret = read_env_secret(canonical_env_path)
shared_secret = (
    canonical_secret or legacy_repo_secret or legacy_config_secret or secrets.token_urlsafe(32)
)

# No literal secret in the client config: the server autogenerates/reads the
# canonical env file via TD_MCP_AUTOGENERATE_SECRET=1 (same as .mcp.json).
config['mcpServers']['touchdesigner'] = {
    'command': uv_path,
    'args': ['run', '--directory', repo_path, 'tdpilot'],
    'env': {
        'TD_MCP_HOST': '127.0.0.1',
        'TD_MCP_PORT': '9981',
        'TD_MCP_WS_PORT': '9982',
        'TD_MCP_EXEC_MODE': 'restricted',
        'TD_MCP_REQUIRE_AUTH': '1',
        'TD_MCP_AUTOGENERATE_SECRET': '1',
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
os.chmod(config_path, 0o600)

print('  Config updated: ' + config_path)

# Write the canonical env file (~/.tdpilot/.tdpilot.env) — the ONE file every
# reader (MCP server, td_client, TD component, TD startup scripts) resolves
# after the explicit TD_MCP_SHARED_SECRET env var. Preserve unrelated keys.
os.makedirs(os.path.dirname(canonical_env_path), exist_ok=True)
managed = {'TD_MCP_SHARED_SECRET', 'TD_MCP_REQUIRE_AUTH', 'TD_MCP_EXEC_MODE'}
kept = []
if os.path.exists(canonical_env_path):
    try:
        with open(canonical_env_path, encoding='utf-8') as f:
            for raw in f.read().splitlines():
                key = raw.strip().partition('=')[0].strip()
                if key not in managed:
                    kept.append(raw)
    except OSError:
        pass
lines = kept + [
    'TD_MCP_SHARED_SECRET=' + shared_secret,
    'TD_MCP_REQUIRE_AUTH=1',
    'TD_MCP_EXEC_MODE=restricted',
]
tmp_path = canonical_env_path + '.tmp'
with open(tmp_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
os.chmod(tmp_path, 0o600)
os.replace(tmp_path, canonical_env_path)
print('  Secret written to: ' + canonical_env_path + ' (canonical secret file)')
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
echo "     Option A: Drag td_component/tdpilot.tox into /local"
echo "     Option B: Run in Textport:"
echo "       exec(open(\"$REPO_PATH/setup_mcp_in_td.py\").read(), globals(), globals())"
echo "  3. Ask your AI client: 'What's in my TouchDesigner project?'"
echo ""
echo "  Installing into /local means TDPilot persists across project opens."
echo ""
echo "  .tox file is at:"
echo "  $REPO_PATH/td_component/tdpilot.tox"
echo ""
