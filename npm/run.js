#!/usr/bin/env node
/**
 * TDPilot — npm wrapper
 * Installs uv (if needed) and runs the Python MCP server.
 * Usage: npx tdpilot
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

function hasCommand(cmd) {
  try {
    run(os.platform() === "win32" ? `where ${cmd}` : `which ${cmd}`);
    return true;
  } catch {
    return false;
  }
}

function installUv() {
  console.log("[TDPilot] Installing uv...");
  if (os.platform() === "win32") {
    execSync(
      'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
      { stdio: "inherit" }
    );
  } else {
    execSync("curl -LsSf https://astral.sh/uv/install.sh | sh", {
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
    // Pull latest
    try {
      run("git pull", { cwd: INSTALL_DIR });
      console.log("[TDPilot] Updated to latest version.");
    } catch {
      // Offline or no git — fine, use what we have
    }
    return;
  }

  console.log(`[TDPilot] Downloading to ${INSTALL_DIR}...`);
  if (hasCommand("git")) {
    execSync(`git clone ${REPO} "${INSTALL_DIR}"`, { stdio: "inherit" });
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

// ── Main ──────────────────────────────────────────────────────

if (!hasCommand("uv")) {
  installUv();
  if (!hasCommand("uv")) {
    console.error("[TDPilot] Failed to install uv. Install it manually: https://docs.astral.sh/uv/");
    process.exit(1);
  }
}

ensureRepo();

// ── Subcommands ──────────────────────────────────────────────
const subcommand = process.argv[2];

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
