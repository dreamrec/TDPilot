#!/usr/bin/env node
/**
 * TDPilot Brain Manager — list, add, and remove installed brains.
 *
 * Usage via npx:
 *   npx tdpilot brains                  # show installed brains
 *   npx tdpilot brains list             # show all available brains
 *   npx tdpilot brains add <id>         # download + activate a brain
 *   npx tdpilot brains remove <id>      # deactivate a brain
 */

const { readFileSync, writeFileSync, mkdirSync, existsSync } = require("fs");
const { join, dirname } = require("path");
const { spawnSync } = require("child_process");
const os = require("os");

const INSTALL_DIR = join(os.homedir(), ".tdpilot");
const ACTIVE_PATH = join(INSTALL_DIR, "data", "brains", "active.json");
const MANIFEST_CACHE = join(INSTALL_DIR, "data", "brains", "manifest.json");
// Replace after uploading manifest to Google Drive
const MANIFEST_DRIVE_ID = "MANIFEST_FILE_ID";

// ── Helpers ──────────────────────────────────────────────────

function readActive() {
  if (!existsSync(ACTIVE_PATH)) return null;
  try {
    return JSON.parse(readFileSync(ACTIVE_PATH, "utf-8"));
  } catch {
    return null;
  }
}

function writeActive(data) {
  mkdirSync(dirname(ACTIVE_PATH), { recursive: true });
  writeFileSync(ACTIVE_PATH, JSON.stringify(data, null, 2) + "\n");
}

function readManifest() {
  // Try local manifest first (bundled in Dreamrec repo)
  const localManifest = join(INSTALL_DIR, "brains_manifest.json");
  if (existsSync(localManifest)) {
    try {
      return JSON.parse(readFileSync(localManifest, "utf-8"));
    } catch { /* fall through */ }
  }
  // Try cached manifest
  if (existsSync(MANIFEST_CACHE)) {
    try {
      return JSON.parse(readFileSync(MANIFEST_CACHE, "utf-8"));
    } catch { /* fall through */ }
  }
  return null;
}

function downloadBrains(brainIds) {
  const tmpFile = join(os.tmpdir(), "tdpilot-selected-brains.json");
  writeFileSync(tmpFile, JSON.stringify(brainIds));

  const manifestPath = join(INSTALL_DIR, "brains_manifest.json");
  const args = [
    join(INSTALL_DIR, "scripts", "download_brains.py"),
  ];
  if (existsSync(manifestPath)) {
    args.push("--manifest", manifestPath);
  }
  args.push("--brains-file", tmpFile);

  const result = spawnSync("python3", args, {
    stdio: "inherit",
    cwd: INSTALL_DIR,
  });
  return result.status === 0;
}

// ── Commands ─────────────────────────────────────────────────

function showInstalled() {
  const active = readActive();
  if (!active) {
    console.log("[TDPilot] No active.json found — all available brains will load.");
    console.log("  Run 'npx tdpilot brains list' to see available brains.");
    return;
  }
  const brains = active.installed_brains || [];
  if (brains.length === 0) {
    console.log("[TDPilot] No brains installed.");
  } else {
    console.log(`[TDPilot] Installed brains (${brains.length}):`);
    const manifest = readManifest();
    for (const id of brains) {
      const info = manifest?.brains?.[id];
      const name = info ? `${info.display_name} — ${info.description}` : id;
      console.log(`  - ${id}: ${name}`);
    }
  }
  if (active.installed_at) {
    console.log(`\n  Configured at: ${active.installed_at}`);
  }
}

function showAvailable() {
  const manifest = readManifest();
  if (!manifest) {
    console.log("[TDPilot] No manifest found. Download brains manually or use the installer.");
    return;
  }
  const active = readActive();
  const installed = new Set(active?.installed_brains || []);

  console.log(`[TDPilot] Available brains (manifest v${manifest.manifest_version || "?"}):\n`);
  for (const [id, brain] of Object.entries(manifest.brains || {})) {
    const status = installed.has(id) ? " [installed]" : "";
    const totalMb = (brain.files || []).reduce((s, f) => s + (f.size_mb || 0), 0);
    console.log(`  ${id}: ${brain.display_name}${status}`);
    console.log(`    ${brain.description} (~${Math.round(totalMb)}MB)`);
  }
}

function addBrain(brainId) {
  if (!brainId) {
    console.error("[TDPilot] Usage: npx tdpilot brains add <brain-id>");
    process.exit(1);
  }

  console.log(`[TDPilot] Adding brain: ${brainId}`);
  const ok = downloadBrains([brainId]);
  if (!ok) {
    console.error(`[TDPilot] Failed to download brain '${brainId}'.`);
    process.exit(1);
  }

  // Update active.json
  const active = readActive() || {
    installed_brains: [],
    installed_at: new Date().toISOString(),
    manifest_version: 1,
  };
  if (!active.installed_brains.includes(brainId)) {
    active.installed_brains.push(brainId);
  }
  active.installed_at = new Date().toISOString();
  writeActive(active);
  console.log(`[TDPilot] Brain '${brainId}' added. Restart TDPilot to activate.`);
}

function removeBrain(brainId) {
  if (!brainId) {
    console.error("[TDPilot] Usage: npx tdpilot brains remove <brain-id>");
    process.exit(1);
  }

  const active = readActive();
  if (!active) {
    console.log("[TDPilot] No active.json — nothing to remove.");
    return;
  }

  active.installed_brains = (active.installed_brains || []).filter(b => b !== brainId);
  active.installed_at = new Date().toISOString();
  writeActive(active);
  console.log(`[TDPilot] Brain '${brainId}' removed from active config.`);
  console.log("  Note: brain files are still on disk. Delete manually if needed.");
}

// ── Main ─────────────────────────────────────────────────────

function main(args) {
  const cmd = (args[0] || "").toLowerCase();

  switch (cmd) {
    case "list":
    case "available":
      showAvailable();
      break;
    case "add":
      addBrain(args[1]);
      break;
    case "remove":
    case "rm":
      removeBrain(args[1]);
      break;
    case "":
    case "status":
      showInstalled();
      break;
    default:
      console.log("Usage: npx tdpilot brains [list|add <id>|remove <id>]");
      console.log("\nCommands:");
      console.log("  (none)         Show installed brains");
      console.log("  list           Show all available brains from manifest");
      console.log("  add <id>       Download and activate a brain");
      console.log("  remove <id>    Deactivate a brain");
      process.exit(1);
  }
}

module.exports = { main, readActive, writeActive, readManifest };
