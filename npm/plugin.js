/**
 * TDPilot Claude Code plugin install/uninstall via the `claude` CLI.
 *
 * install(): adds the dreamrec/TDPilot marketplace and installs the plugin.
 * uninstall(): removes the plugin and the marketplace entry.
 *
 * Requires the `claude` CLI (Claude Code) on PATH.
 */

const { execSync, spawnSync } = require("child_process");

const MARKETPLACE_REPO = "dreamrec/TDPilot";
const MARKETPLACE_NAME = "dreamrec-TDPilot";
const PLUGIN_NAME = "tdpilot";
const PLUGIN_REF = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;

function log(msg)  { console.log("[TDPilot] " + msg); }
function warn(msg) { console.warn("[TDPilot] " + msg); }
function die(msg)  { console.error("[TDPilot] " + msg); process.exit(1); }

function ensureClaudeCli() {
  const res = spawnSync("claude", ["--version"], { stdio: "pipe" });
  if (res.error || res.status !== 0) {
    die(
      "The 'claude' CLI is not on PATH. Install Claude Code first:\n" +
        "  https://claude.com/claude-code\n" +
        "Then rerun: npx tdpilot plugin-install"
    );
  }
  const version = (res.stdout || "").toString().trim().split("\n")[0];
  log("Found Claude Code: " + version);
}

function runClaude(args, opts = {}) {
  // stdio:inherit so the user sees claude's own output/prompts.
  const res = spawnSync("claude", args, { stdio: "inherit", ...opts });
  if (res.error) throw res.error;
  return res.status;
}

function install() {
  ensureClaudeCli();

  log("Adding marketplace: " + MARKETPLACE_REPO);
  let status = runClaude(["plugin", "marketplace", "add", MARKETPLACE_REPO]);
  if (status !== 0) {
    // Treat "already added" as success — idempotency.
    warn(
      "plugin marketplace add returned non-zero (" +
        status +
        "). If it's already added, that's fine; continuing."
    );
  }

  log("Installing plugin: " + PLUGIN_REF);
  status = runClaude(["plugin", "install", PLUGIN_REF]);
  if (status !== 0) {
    die("plugin install failed (" + status + "). Run 'claude plugin install " + PLUGIN_REF + "' manually to see the error.");
  }

  printNextSteps();
}

function uninstall() {
  ensureClaudeCli();

  log("Uninstalling plugin: " + PLUGIN_REF);
  runClaude(["plugin", "uninstall", PLUGIN_REF]);

  log("Removing marketplace: " + MARKETPLACE_NAME);
  runClaude(["plugin", "marketplace", "remove", MARKETPLACE_NAME]);

  log("Done.");
}

function printNextSteps() {
  const out = [
    "",
    "[TDPilot] Plugin installed.",
    "",
    "Next steps:",
    "  1. Open TouchDesigner (2025.30000+).",
    "  2. In a running Claude Code session, ask something like:",
    "       \"What's in my TouchDesigner project?\"",
    "     — the touchdesigner MCP server auto-starts on first use.",
    "  3. Load td_component/tdpilot_v1_3.tox from the plugin cache",
    "     (~/.claude/plugins/cache/" + MARKETPLACE_NAME + "/" + PLUGIN_NAME + "/<version>/)",
    "     by dragging it into your TD /local container.",
    "",
    "Update later:    claude plugin update " + PLUGIN_REF,
    "Uninstall:       npx tdpilot plugin-uninstall",
    "",
    "Docs: https://github.com/dreamrec/TDPilot",
    "",
  ];
  console.log(out.join("\n"));
}

module.exports = { install, uninstall };
