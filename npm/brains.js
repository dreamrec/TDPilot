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
// Bundled manifest (shipped with the repo and plugin zip). The installer
// copies it to ~/.tdpilot/brains_manifest.json so `readManifest()` resolves
// it even when the npx CLI is run without cwd=INSTALL_DIR.
const BUNDLED_MANIFEST = join(INSTALL_DIR, "data", "brains", "brains_manifest.json");
const HOME_MANIFEST = join(INSTALL_DIR, "brains_manifest.json");

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
  // Resolution order:
  //   1. ~/.tdpilot/brains_manifest.json   (installer-copied, user-facing)
  //   2. ~/.tdpilot/data/brains/brains_manifest.json  (bundled with repo)
  // Both are shipped from `data/brains/brains_manifest.json` in the repo;
  // the first path just avoids a nested traversal on the happy CLI path.
  for (const candidate of [HOME_MANIFEST, BUNDLED_MANIFEST]) {
    if (existsSync(candidate)) {
      try {
        return JSON.parse(readFileSync(candidate, "utf-8"));
      } catch { /* fall through to next candidate */ }
    }
  }
  return null;
}

function resolvePython() {
  // Windows has no `python3` alias (the bare spawn used pre-batch-E failed
  // with ENOENT there). Try python3, then python, then the Windows launcher
  // `py -3`. Returns { cmd, argsPrefix } or null when no interpreter found.
  const candidates = [
    { cmd: "python3", argsPrefix: [] },
    { cmd: "python", argsPrefix: [] },
    { cmd: "py", argsPrefix: ["-3"] },
  ];
  for (const candidate of candidates) {
    const probe = spawnSync(candidate.cmd, [...candidate.argsPrefix, "--version"], {
      stdio: "pipe",
    });
    if (!probe.error && probe.status === 0) return candidate;
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

  const python = resolvePython();
  if (!python) {
    console.error(
      "[TDPilot] No Python interpreter found (tried python3, python, py -3). " +
        "Install Python 3 and re-run."
    );
    return false;
  }
  const result = spawnSync(python.cmd, [...python.argsPrefix, ...args], {
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
    const mode = brain.install_mode || "download";
    const modeTag = ` [${mode}]`;
    console.log(`  ${id}: ${brain.display_name}${status}${modeTag}`);
    console.log(`    ${brain.description} (~${Math.round(totalMb)}MB)`);
    if (mode === "local_build" && brain.install_notes) {
      console.log(`    note: ${brain.install_notes}`);
    }
  }
}

function addBrain(brainId) {
  if (!brainId) {
    console.error("[TDPilot] Usage: npx tdpilot brains add <brain-id>");
    process.exit(1);
  }

  // v1.4.5: validate against manifest BEFORE calling downloader so a typo
  // can't pollute active.json. active.json is an allow-list — adding a bogus
  // id would disable all known brains on next server startup.
  const manifest = readManifest();
  if (!manifest) {
    console.error(
      "[TDPilot] No brains_manifest.json found. Run `npx tdpilot install` first."
    );
    process.exit(1);
  }
  const entry = manifest.brains && manifest.brains[brainId];
  if (!entry) {
    const valid = Object.keys(manifest.brains || {}).sort().join(", ");
    console.error(
      `[TDPilot] Unknown brain id '${brainId}'. Valid ids: ${valid}`
    );
    process.exit(2);
  }

  // Local-build brains cannot be fetched by the downloader. Allow activation
  // only when the runtime DB is already present on disk (the user ran the
  // dedicated builder).
  if (entry.install_mode === "local_build") {
    const runtimeDb = entry.runtime_db;
    const dbPath = runtimeDb ? join(INSTALL_DIR, runtimeDb) : null;
    if (!dbPath || !existsSync(dbPath)) {
      console.error(
        `[TDPilot] Brain '${brainId}' is local-build only and its runtime DB\n` +
        `          was not found at ${dbPath || "<unspecified>"}.\n` +
        `          ${entry.install_notes || "Build it with the dedicated script first, then re-run."}\n` +
        `          Activation refused — active.json left untouched.`
      );
      process.exit(3);
    }
    console.log(`[TDPilot] Activating local-build brain '${brainId}' (runtime DB found).`);
  } else {
    console.log(`[TDPilot] Adding brain: ${brainId}`);
    const ok = downloadBrains([brainId]);
    if (!ok) {
      console.error(`[TDPilot] Failed to download brain '${brainId}'. active.json left untouched.`);
      process.exit(1);
    }
  }

  // Only write active.json AFTER verified activation (real download OR
  // local-build DB present on disk). Pre-v1.4.5 this ran unconditionally
  // and any typo polluted the allow-list.
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

// When invoked directly (`node brains.js …` or via the `tdpilot brains` npm
// bin dispatch), run main. Guarded by `require.main === module` so unit
// tests that `require()` this module don't immediately consume process.argv.
if (require.main === module) {
  main(process.argv.slice(2));
}
