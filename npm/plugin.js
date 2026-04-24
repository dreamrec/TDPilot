/**
 * TDPilot Claude Code plugin install/uninstall via the `claude` CLI.
 *
 * install(): adds the dreamrec/TDPilot marketplace and installs the plugin.
 * uninstall(): removes the plugin and the marketplace entry.
 *
 * Requires the `claude` CLI (Claude Code) on PATH. Ensures `uv` is present
 * (bootstraps if missing) since the plugin's MCP server runs via `uv run`.
 */

const { spawnSync } = require("child_process");
const os = require("os");
const { join } = require("path");

const MARKETPLACE_REPO = "dreamrec/TDPilot";
const MARKETPLACE_NAME = "dreamrec-TDPilot";
const PLUGIN_NAME = "tdpilot";
const PLUGIN_REF = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;

function log(msg)  { console.log("[TDPilot] " + msg); }
function warn(msg) { console.warn("[TDPilot] " + msg); }
function die(msg)  { console.error("[TDPilot] " + msg); process.exit(1); }

function hasCommand(cmd) {
  const finder = os.platform() === "win32" ? "where" : "which";
  const res = spawnSync(finder, [cmd], { stdio: "pipe" });
  return !res.error && res.status === 0;
}

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

function ensureUv() {
  if (hasCommand("uv")) {
    const res = spawnSync("uv", ["--version"], { stdio: "pipe" });
    log("Found uv: " + (res.stdout || "").toString().trim());
    return;
  }
  log("uv not found — installing (pinned 0.6.10)...");
  const pinned = process.env.TDPILOT_UV_VERSION || "0.6.10";
  const urlPath = pinned === "latest" ? "" : pinned + "/";
  if (os.platform() === "win32") {
    const url = "https://astral.sh/uv/" + urlPath + "install.ps1";
    spawnSync("powershell", ["-ExecutionPolicy", "ByPass", "-c", "irm " + url + " | iex"], { stdio: "inherit" });
  } else {
    const url = "https://astral.sh/uv/" + urlPath + "install.sh";
    const script = "curl -LsSf " + url + " | sh";
    spawnSync("bash", ["-c", script], { stdio: "inherit" });
  }
  // Put uv on the CURRENT process PATH so later spawns find it.
  const uvBin = join(os.homedir(), ".local", "bin");
  const sep = os.platform() === "win32" ? ";" : ":";
  if (!process.env.PATH.includes(uvBin)) {
    process.env.PATH = uvBin + sep + process.env.PATH;
  }
  if (!hasCommand("uv")) {
    warn("uv installed but not on PATH in this shell. Open a new terminal.");
    warn("Plugin install will continue; MCP server may fail to start on first use.");
  } else {
    log("uv ready.");
  }
}

function runClaude(args, opts = {}) {
  // stdio:inherit so the user sees claude's own output/prompts.
  const res = spawnSync("claude", args, { stdio: "inherit", ...opts });
  if (res.error) throw res.error;
  return res.status;
}

// Capture both stdout/stderr from a claude subcommand so we can inspect text.
function runClaudeCapture(args) {
  const res = spawnSync("claude", args, { stdio: "pipe" });
  return {
    status: res.status,
    stdout: (res.stdout || "").toString(),
    stderr: (res.stderr || "").toString(),
  };
}

function install() {
  ensureClaudeCli();
  ensureUv();

  log("Adding marketplace: " + MARKETPLACE_REPO);
  // Capture output so we can distinguish "already added" from real errors
  // without grepping (which is brittle across Claude Code versions).
  const addResult = runClaudeCapture(["plugin", "marketplace", "add", MARKETPLACE_REPO]);
  if (addResult.status !== 0) {
    const combined = (addResult.stdout + "\n" + addResult.stderr).toLowerCase();
    if (combined.includes("already")) {
      log("Marketplace already registered, continuing.");
    } else {
      // Real error — surface it and bail.
      if (addResult.stdout) console.log(addResult.stdout);
      if (addResult.stderr) console.error(addResult.stderr);
      die("plugin marketplace add failed (exit " + addResult.status + ").");
    }
  } else {
    log("Marketplace added.");
  }

  log("Installing plugin: " + PLUGIN_REF);
  const status = runClaude(["plugin", "install", PLUGIN_REF]);
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
    "  3. Load td_component/tdpilot.tox from the plugin cache",
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
