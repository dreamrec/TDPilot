# ============================================================================
#  TDPilot — Windows Installer
#  Run: powershell -ExecutionPolicy Bypass -File install.ps1
# ============================================================================

$ErrorActionPreference = 'Stop'
$RepoUrl = "https://github.com/dreamrec/TDPilot.git"
$RepoDirName = "TDPilot"

Write-Host ""
Write-Host "  TDPilot — Installer for Windows" -ForegroundColor Cyan
Write-Host "  ===============================" -ForegroundColor Cyan
Write-Host ""

# ---------- Step 1: Check / Install uv ----------

Write-Host "[1/4] Checking for uv..." -ForegroundColor Yellow

$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCmd) {
    $uvVersion = & uv --version 2>&1
    Write-Host "  Found uv: $uvVersion" -ForegroundColor Green
} else {
    Write-Host "  uv not found. Installing..." -ForegroundColor Yellow
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
        if (-not $uvCmd) {
            # Try common install location
            $uvDefault = "$env:USERPROFILE\.local\bin\uv.exe"
            if (Test-Path $uvDefault) {
                $env:Path += ";$env:USERPROFILE\.local\bin"
            } else {
                Write-Host "  ERROR: uv installed but not found in PATH." -ForegroundColor Red
                Write-Host "  Close this window, reopen PowerShell, and run this script again." -ForegroundColor Red
                exit 1
            }
        }
        Write-Host "  uv installed successfully." -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Failed to install uv: $_" -ForegroundColor Red
        exit 1
    }
}

# ---------- Step 2: Locate or clone the repo ----------

Write-Host ""
Write-Host "[2/4] Setting up repository..." -ForegroundColor Yellow

# Check if we're running from inside the repo already
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
$PyprojectHere = Join-Path $ScriptDir "pyproject.toml"

if (Test-Path $PyprojectHere) {
    $RepoPath = $ScriptDir
    Write-Host "  Running from repo: $RepoPath" -ForegroundColor Green
} else {
    # Clone to a safe location (avoid OneDrive issues)
    $InstallDir = "$env:USERPROFILE\$RepoDirName"

    if (Test-Path (Join-Path $InstallDir "pyproject.toml")) {
        $RepoPath = $InstallDir
        Write-Host "  Found existing install: $RepoPath" -ForegroundColor Green
    } else {
        Write-Host "  Cloning to: $InstallDir" -ForegroundColor Yellow
        try {
            $gitCmd = Get-Command git -ErrorAction SilentlyContinue
            if ($gitCmd) {
                & git clone $RepoUrl $InstallDir 2>&1 | Out-Null
            } else {
                Write-Host "  git not found — downloading ZIP instead..." -ForegroundColor Yellow
                $ZipUrl = "https://github.com/dreamrec/TDPilot/archive/refs/heads/main.zip"
                $ZipPath = "$env:TEMP\td-mcp.zip"
                $ExtractPath = "$env:TEMP\td-mcp-extract"
                Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath
                Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath -Force
                Move-Item "$ExtractPath\$RepoDirName-main" $InstallDir
                Remove-Item $ZipPath -Force
                Remove-Item $ExtractPath -Recurse -Force
            }
            $RepoPath = $InstallDir
            Write-Host "  Downloaded to: $RepoPath" -ForegroundColor Green
        } catch {
            Write-Host "  ERROR: Failed to download: $_" -ForegroundColor Red
            exit 1
        }
    }
}

# ---------- Step 3: Configure MCP Desktop Client ----------

Write-Host ""
Write-Host "[3/4] Configuring MCP desktop client..." -ForegroundColor Yellow

$ConfigDir = "$env:APPDATA\Claude"
$ConfigPath = "$ConfigDir\claude_desktop_config.json"

# Find uv full path for the config
$uvFullPath = (Get-Command uv).Source

# Build the touchdesigner server entry
$tdServer = @{
    command = $uvFullPath
    args = @("run", "--directory", $RepoPath, "tdpilot")
    env = @{
        TD_MCP_HOST = "127.0.0.1"
        TD_MCP_PORT = "9981"
        TD_MCP_WS_PORT = "9982"
    }
}

# Load or create config
if (Test-Path $ConfigPath) {
    # Backup first
    $BackupPath = "$ConfigPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $ConfigPath $BackupPath
    Write-Host "  Backed up config to: $BackupPath" -ForegroundColor DarkGray

    try {
        $configText = Get-Content $ConfigPath -Raw
        if ([string]::IsNullOrWhiteSpace($configText)) {
            $config = @{ mcpServers = @{} }
        } else {
            $config = $configText | ConvertFrom-Json
        }
    } catch {
        Write-Host "  WARNING: Existing config has invalid JSON. Creating fresh config." -ForegroundColor Yellow
        $config = @{ mcpServers = @{} }
    }
} else {
    if (-not (Test-Path $ConfigDir)) {
        New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    }
    $config = @{ mcpServers = @{} }
}

# Ensure mcpServers exists
if (-not $config.mcpServers) {
    $config | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue @{} -Force
}

# Convert to hashtable if needed (ConvertFrom-Json gives PSCustomObject)
if ($config.mcpServers -is [PSCustomObject]) {
    $servers = @{}
    $config.mcpServers.PSObject.Properties | ForEach-Object {
        $servers[$_.Name] = $_.Value
    }
} else {
    $servers = $config.mcpServers
}

# Add/overwrite touchdesigner entry
$servers["touchdesigner"] = $tdServer

# Rebuild config object as ordered for clean JSON
$output = [ordered]@{
    mcpServers = $servers
}

# Preserve any non-mcpServers keys
if ($config -is [PSCustomObject]) {
    $config.PSObject.Properties | ForEach-Object {
        if ($_.Name -ne "mcpServers") {
            $output[$_.Name] = $_.Value
        }
    }
}

$json = $output | ConvertTo-Json -Depth 10
Set-Content -Path $ConfigPath -Value $json -Encoding UTF8

Write-Host "  Config updated: $ConfigPath" -ForegroundColor Green

# ---------- Step 4: Summary ----------

Write-Host ""
Write-Host "[4/4] Done!" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "  INSTALL COMPLETE" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Repo location:   $RepoPath" -ForegroundColor White
Write-Host "  Config file:     $ConfigPath" -ForegroundColor White
Write-Host "  uv path:         $uvFullPath" -ForegroundColor White
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Restart your MCP desktop client" -ForegroundColor White
Write-Host "  2. Open TouchDesigner and load the component (once per session):" -ForegroundColor White
Write-Host "     Option A: Drag td_component\tdpilot_v1_3.tox into /local" -ForegroundColor White
Write-Host "     Option B: Run in Textport:" -ForegroundColor White
Write-Host "       exec(open('$RepoPath\setup_mcp_in_td.py').read(), globals(), globals())" -ForegroundColor DarkGray
Write-Host "  3. Ask your AI client: 'What's in my TouchDesigner project?'" -ForegroundColor White
Write-Host ""
Write-Host "  Installing into /local means TDPilot persists across project opens." -ForegroundColor Green
Write-Host ""
Write-Host "  .tox file is at:" -ForegroundColor DarkGray
Write-Host "  $RepoPath\td_component\tdpilot_v1_3.tox" -ForegroundColor DarkGray
Write-Host ""
