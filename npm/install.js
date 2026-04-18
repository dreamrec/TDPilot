/**
 * TDPilot install/uninstall for TouchDesigner auto-load.
 *
 * install(): Writes ~/.tdpilot_path config and sets up TD preferences
 *            so TDPilot loads on every TD launch via a startup .toe file.
 *
 * uninstall(): Removes config and reverts TD preferences.
 *
 * Uses only Node.js fs built-ins — no child processes needed.
 */

const { existsSync, readFileSync, mkdirSync, unlinkSync, writeFileSync } = require("fs");
const { join } = require("path");
const os = require("os");

const INSTALL_DIR = join(os.homedir(), ".tdpilot");
const CONFIG_FILE = join(os.homedir(), ".tdpilot_path");
const STARTUP_TOE = join(INSTALL_DIR, "tdpilot_default.toe");
const STARTUP_SCRIPT_NAME = "tdpilot_startup.py";

function getPrefsPath() {
  // TD preferences file location
  if (os.platform() === "darwin") {
    return join(os.homedir(), "Library", "Application Support", "Derivative", "TouchDesigner099", "pref.txt");
  }
  // Windows: %APPDATA%/Derivative/TouchDesigner099/pref.txt
  return join(os.homedir(), "AppData", "Roaming", "Derivative", "TouchDesigner099", "pref.txt");
}

function readPrefs(prefsPath) {
  if (!existsSync(prefsPath)) return {};
  const lines = readFileSync(prefsPath, "utf-8").split("\n");
  const prefs = {};
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const tabIdx = trimmed.indexOf("\t");
    if (tabIdx === -1) continue;
    prefs[trimmed.slice(0, tabIdx)] = trimmed.slice(tabIdx + 1);
  }
  return prefs;
}

function writePrefs(prefsPath, prefs) {
  const prefsDir = join(prefsPath, "..");
  if (!existsSync(prefsDir)) {
    mkdirSync(prefsDir, { recursive: true });
  }
  // Backup the existing pref.txt before we overwrite it. TD preference format
  // has shifted between versions, so losing the original is painful for users.
  if (existsSync(prefsPath)) {
    try {
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const backupPath = prefsPath + ".tdpilot-backup-" + ts;
      const original = readFileSync(prefsPath, "utf-8");
      writeFileSync(backupPath, original, "utf-8");
      console.log("[TDPilot] Backed up existing pref.txt to", backupPath);
    } catch (err) {
      console.warn("[TDPilot] Could not back up pref.txt:", err.message);
    }
  }
  const lines = Object.entries(prefs).map(([k, v]) => k + "\t" + v);
  writeFileSync(prefsPath, lines.join("\n") + "\n", "utf-8");
}

function install() {
  var sourceScript = join(INSTALL_DIR, "td_component", STARTUP_SCRIPT_NAME);

  // Validate source exists (requires ensureRepo() to have run first)
  if (!existsSync(sourceScript)) {
    console.error("[TDPilot] ERROR: Startup script not found at", sourceScript);
    console.error("[TDPilot] Run 'npx tdpilot' first to download the repo.");
    process.exit(1);
  }

  // Write config file (tells the startup script where to find the repo)
  writeFileSync(CONFIG_FILE, INSTALL_DIR + "\n", "utf-8");
  console.log("[TDPilot] Config written to", CONFIG_FILE);

  // Set TD preferences for custom startup file
  var prefsPath = getPrefsPath();
  var prefs = readPrefs(prefsPath);
  prefs["general.startupfilemode"] = "2"; // Custom File
  prefs["general.startupfilename"] = STARTUP_TOE;
  writePrefs(prefsPath, prefs);
  console.log("[TDPilot] TD preferences updated:", prefsPath);

  console.log("");

  if (existsSync(STARTUP_TOE)) {
    console.log("[TDPilot] Startup file exists:", STARTUP_TOE);
    console.log("[TDPilot] Done! TDPilot will auto-load next time TouchDesigner starts.");
  } else {
    console.log("[TDPilot] One-time TD setup needed:");
    console.log("[TDPilot] Open TouchDesigner and run these commands in the Textport:");
    console.log("");
    var setupPath = join(INSTALL_DIR, "setup_mcp_in_td.py");
    console.log('  # Step 1: Load TDPilot');
    console.log('  f=open("' + setupPath + '"); c=f.read(); f.close()');
    console.log('  compile(c, "setup", "exec")');
    console.log("");
    console.log("  # Step 2: Create auto-start and save");
    console.log("  dat = op('/project1').create('executeDAT', 'tdpilot_autostart')");
    console.log("  dat.par.active = True");
    console.log("  dat.par.start = True");
    console.log("  dat.comment = 'TDPilot auto-load'");
    console.log("  project.save('" + STARTUP_TOE + "')");
    console.log("");
    console.log("[TDPilot] After that, TDPilot will auto-load on every TD launch.");
  }

  console.log("[TDPilot] To undo: npx tdpilot uninstall");
}

function uninstall() {
  var removed = false;

  // Remove config file
  if (existsSync(CONFIG_FILE)) {
    unlinkSync(CONFIG_FILE);
    console.log("[TDPilot] Removed", CONFIG_FILE);
    removed = true;
  }

  // Revert TD preferences (set back to default startup mode)
  var prefsPath = getPrefsPath();
  if (existsSync(prefsPath)) {
    var prefs = readPrefs(prefsPath);
    if (prefs["general.startupfilemode"] === "2" && prefs["general.startupfilename"] === STARTUP_TOE) {
      delete prefs["general.startupfilemode"];
      delete prefs["general.startupfilename"];
      writePrefs(prefsPath, prefs);
      console.log("[TDPilot] TD preferences reverted to default startup");
      removed = true;
    }
  }

  // Remove startup .toe
  if (existsSync(STARTUP_TOE)) {
    unlinkSync(STARTUP_TOE);
    console.log("[TDPilot] Removed", STARTUP_TOE);
    removed = true;
  }

  if (removed) {
    console.log("[TDPilot] Uninstalled. TDPilot will no longer auto-load on TD startup.");
  } else {
    console.log("[TDPilot] Nothing to uninstall — TDPilot auto-load was not installed.");
  }
}

module.exports = { install, uninstall };
