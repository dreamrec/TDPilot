#!/usr/bin/env node
/**
 * TDPilot — npm wrapper
 *
 * Usage:
 *   npx tdpilot                 run the MCP server (default)
 *   npx tdpilot install         install TD auto-load (.toe + pref.txt)
 *   npx tdpilot uninstall       undo install
 *   npx tdpilot update          update ~/.tdpilot to the latest release tag
 *   npx tdpilot plugin-install  install as a Claude Code plugin via marketplace
 *   npx tdpilot plugin-uninstall remove the Claude Code plugin
 *   npx tdpilot brains          manage downloaded brain DBs
 *   npx tdpilot help | --help   show this usage
 *
 * IMPORTANT — stdout discipline (v1.6.12 fix):
 * When invoked without a subcommand, this wrapper eventually spawns the Python
 * MCP server with `stdio: "inherit"`. That means the MCP client (Claude Desktop
 * / Claude Code) is listening on OUR stdout for JSON-RPC the entire time —
 * including the moments BEFORE we spawn the child. Any line written to stdout
 * here (e.g. `console.log("[TDPilot] Downloading...")`) is parsed as JSON by
 * the client and triggers `Unexpected token 'T', "[TDPilot] D"... is not
 * valid JSON` followed by `Server disconnected`. Every diagnostic / progress
 * message MUST go to stderr via `console.error` (or `console.warn`, which Node
 * also routes to stderr). Only the spawned Python process is allowed to write
 * to stdout — and only valid JSON-RPC.
 */

const { execSync, spawn } = require("child_process");
const { existsSync } = require("fs");
const { join } = require("path");
const os = require("os");

const REPO = "https://github.com/dreamrec/TDPilot.git";
const INSTALL_DIR = join(os.homedir(), ".tdpilot");

function run(cmd, opts = {}) {
  return execSync(cmd, { encoding: "utf-8", stdio: "pipe", ...opts }).trim();
}

function pinToLatestTag(dir) {
  // Auto-pin clones to the most recent reachable git tag rather than HEAD
  // of main. Without this, `npx tdpilot@1.5.1` would happily run whatever
  // bleeding-edge code is on main at fetch time — package.json's `version`
  // field would be decorative. With this, users get the latest published
  // release. Falls back to main HEAD if no tags exist (offline / private fork
  // / pre-release) — a degraded mode, so warn LOUDLY that the user is running
  // unpinned, possibly-unreleased code rather than a tagged version.
  try {
    const latestTag = run("git describe --tags --abbrev=0", { cwd: dir });
    if (latestTag) {
      run(`git checkout ${latestTag}`, { cwd: dir });
      console.error(`[TDPilot] Pinned to ${latestTag}`); // stderr — see top-of-file note
      return latestTag;
    }
  } catch {
    console.error(
      "[TDPilot] WARNING: no release tag found upstream — running UNPINNED main HEAD, " +
        "which may be unreleased/in-flux code, not a tagged version."
    );
  }
  return null;
}

function hasCommand(cmd) {
  try {
    run(os.platform() === "win32" ? `where ${cmd}` : `which ${cmd}`);
    return true;
  } catch {
    return false;
  }
}

function installUv() {
  // Pin uv to a known-good version (override via TDPILOT_UV_VERSION=latest).
  // install.sh / install.ps1 / npm/plugin.js all pin 0.6.10 — run.js was the
  // only path fetching an UNPINNED uv, a supply-chain drift risk where a future
  // uv release could break or alter the install non-deterministically.
  const pinned = process.env.TDPILOT_UV_VERSION || "0.6.10";
  const urlPath = pinned === "latest" ? "" : `${pinned}/`;
  console.error(`[TDPilot] Installing uv (pinned ${pinned})...`); // stderr — see top-of-file note
  if (os.platform() === "win32") {
    execSync(
      `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/${urlPath}install.ps1 | iex"`,
      { stdio: "inherit" }
    );
  } else {
    execSync(`curl -LsSf https://astral.sh/uv/${urlPath}install.sh | sh`, {
      stdio: "inherit",
      shell: "/bin/bash",
    });
  }

  // Add common uv locations to PATH
  const uvBin = join(os.homedir(), ".local", "bin");
  if (!process.env.PATH.includes(uvBin)) {
    process.env.PATH = `${uvBin}${os.platform() === "win32" ? ";" : ":"}${process.env.PATH}`;
  }
}

function ensureRepo() {
  const marker = join(INSTALL_DIR, "pyproject.toml");
  if (existsSync(marker)) {
    // Auto-update is OPT-IN — prior behavior silently ran `git pull` on every
    // invocation, which surprised users with local edits. Set TDPILOT_AUTO_UPDATE=1
    // to restore the old behavior, or use `npx tdpilot update` (updateRepo()
    // below) for an explicit refresh.
    if (process.env.TDPILOT_AUTO_UPDATE === "1") {
      try {
        // Fetch tags too, then re-pin to the latest tag so users move
        // forward across releases (not just to HEAD of main).
        run("git fetch --tags origin main", { cwd: INSTALL_DIR });
        run("git checkout main", { cwd: INSTALL_DIR });
        run("git pull", { cwd: INSTALL_DIR });
        pinToLatestTag(INSTALL_DIR);
        console.error("[TDPilot] Updated to latest version (TDPILOT_AUTO_UPDATE=1)."); // stderr — see top-of-file note
      } catch {
        // Offline or no git — fine, use what we have
      }
    }
    return;
  }

  console.error(`[TDPilot] Downloading to ${INSTALL_DIR}...`); // stderr — see top-of-file note (this exact line was the v1.6.11 MCP stdio poison)
  if (hasCommand("git")) {
    execSync(`git clone ${REPO} "${INSTALL_DIR}"`, { stdio: "inherit" });
    pinToLatestTag(INSTALL_DIR);
  } else {
    // Fallback: download zip
    const zipUrl =
      "https://github.com/dreamrec/TDPilot/archive/refs/heads/main.zip";
    const tmpZip = join(os.tmpdir(), "tdpilot.zip");
    const tmpDir = join(os.tmpdir(), "tdpilot-extract");
    if (os.platform() === "win32") {
      run(`powershell -c "Invoke-WebRequest -Uri '${zipUrl}' -OutFile '${tmpZip}'"`);
      run(`powershell -c "Expand-Archive -Path '${tmpZip}' -DestinationPath '${tmpDir}' -Force"`);
    } else {
      run(`curl -L -o "${tmpZip}" "${zipUrl}"`);
      run(`unzip -q "${tmpZip}" -d "${tmpDir}"`);
    }
    const extracted = join(tmpDir, "TDPilot-main");
    if (os.platform() === "win32") {
      run(`move "${extracted}" "${INSTALL_DIR}"`);
    } else {
      run(`mv "${extracted}" "${INSTALL_DIR}"`);
    }
  }
}

function updateRepo() {
  // `npx tdpilot update` — explicit refresh of ~/.tdpilot to the latest
  // release tag. Mirrors the pinning strategy of ensureRepo()/install.sh:
  // fetch tags, fast-forward main, then check out the newest reachable tag
  // (never leave the user on unpinned main HEAD). Windows-safe: every git
  // invocation is a plain fixed `git ...` string through run() — no &&,
  // no pipes, no shell-isms, no interpolated user input.
  const marker = join(INSTALL_DIR, "pyproject.toml");
  if (!existsSync(marker)) {
    console.error(`[TDPilot] No install found at ${INSTALL_DIR}. Run 'npx tdpilot' once first.`);
    process.exit(1);
  }
  if (!existsSync(join(INSTALL_DIR, ".git"))) {
    console.error(
      `[TDPilot] ${INSTALL_DIR} is not a git checkout (zip-based install?). ` +
        "Delete it and re-run 'npx tdpilot' to reinstall from git."
    );
    process.exit(1);
  }

  let before = "";
  try {
    before = run("git describe --tags --always", { cwd: INSTALL_DIR });
  } catch {
    /* fresh/odd checkout — proceed; the after-state still gets printed */
  }

  console.log(`[TDPilot] Updating ${INSTALL_DIR}...`);
  try {
    run("git fetch --tags origin main", { cwd: INSTALL_DIR });
    run("git checkout main", { cwd: INSTALL_DIR });
    run("git pull --ff-only origin main", { cwd: INSTALL_DIR });
  } catch (err) {
    console.error("[TDPilot] Update failed: " + (err && err.message ? err.message : err));
    console.error(
      "[TDPilot] If you have local edits in " +
        INSTALL_DIR +
        ", stash or revert them, then re-run 'npx tdpilot update'."
    );
    process.exit(1);
  }

  const pinnedTag = pinToLatestTag(INSTALL_DIR);
  let after = "";
  try {
    after = run("git describe --tags --always", { cwd: INSTALL_DIR });
  } catch {
    /* ignore */
  }

  if (before && after && before === after) {
    console.log(`[TDPilot] Already up to date (${after}).`);
  } else {
    console.log(`[TDPilot] Updated: ${before || "(unknown)"} -> ${after || pinnedTag || "(unknown)"}`);
  }
  console.log("");
  console.log("[TDPilot] Next steps:");
  console.log("  1. Restart your MCP client (Claude Desktop / Claude Code) so the new server loads.");
  console.log("  2. Update the TouchDesigner component too: run the td_self_update tool from your");
  console.log("     AI client, or run setup_mcp_in_td.py in the TD Textport");
  console.log("     (the 'npx tdpilot install' output and the README carry the exact snippet).");
}

function printHelp() {
  // Keep in sync with the usage block in the top-of-file comment.
  console.log(
    [
      "Usage: npx tdpilot [subcommand]",
      "",
      "  (none)            run the MCP server (default)",
      "  install           install TD auto-load (.toe + pref.txt)",
      "  uninstall         undo install",
      "  update            update ~/.tdpilot to the latest release tag",
      "  plugin-install    install as a Claude Code plugin via marketplace",
      "  plugin-uninstall  remove the Claude Code plugin",
      "  brains            manage downloaded brain DBs",
      "  help, --help      show this usage",
      "",
      "Docs: https://github.com/dreamrec/TDPilot",
    ].join("\n")
  );
}

// ── Subcommands that don't need uv/repo ──────────────────────
// (plugin-install runs Claude Code — no Python needed)
const subcommand = process.argv[2];

if (subcommand === "help" || subcommand === "--help" || subcommand === "-h") {
  printHelp();
  process.exit(0);
}

if (subcommand === "plugin-install" || subcommand === "plugin-uninstall") {
  const { install, uninstall } = require("./plugin");
  if (subcommand === "plugin-install") install();
  else uninstall();
  process.exit(0);
}

// `update` needs git + an existing checkout, but not uv — dispatch before
// the uv bootstrap so updating never triggers a toolchain install.
if (subcommand === "update") {
  updateRepo();
  process.exit(0);
}

// ── Main ──────────────────────────────────────────────────────

if (!hasCommand("uv")) {
  installUv();
  if (!hasCommand("uv")) {
    console.error("[TDPilot] Failed to install uv. Install it manually: https://docs.astral.sh/uv/");
    process.exit(1);
  }
}

ensureRepo();

if (subcommand === "brains") {
  const { main: brainsMain } = require("./brains");
  brainsMain(process.argv.slice(3));
  process.exit(0);
}

if (subcommand === "install" || subcommand === "uninstall") {
  const { install, uninstall } = require("./install");
  if (subcommand === "install") {
    install();
  } else {
    uninstall();
  }
  process.exit(0);
}

// Pass through env vars
const env = {
  ...process.env,
  TD_MCP_HOST: process.env.TD_MCP_HOST || "127.0.0.1",
  TD_MCP_PORT: process.env.TD_MCP_PORT || "9981",
};

// Run the Python MCP server via uv
const userArgs = process.argv.slice(2);
const child = spawn("uv", ["run", "--directory", INSTALL_DIR, "tdpilot", ...userArgs], {
  stdio: "inherit",
  env,
  shell: os.platform() === "win32",
});

child.on("exit", (code) => process.exit(code || 0));
