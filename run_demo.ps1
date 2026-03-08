#!/usr/bin/env pwsh
<#
.SYNOPSIS
    HoneyGrid Demo Runner - Starts server, GUI, and agents for presentation
    
.DESCRIPTION
    Launches a complete HoneyGrid demonstration environment:
    - Generates certificates if needed
    - Starts the central server (port 9000)
    - Launches the GUI dashboard
    - Starts demo agents monitoring sample honeytokens
    
.EXAMPLE
    .\run_demo.ps1
    
.NOTES
    Requires Python 3.10+, virtual environment activated, and watchdog installed
#>

param(
    [switch]$RecordingMode,
    [switch]$AutoRunTests,
    [switch]$SkipCertGeneration,
    [int]$ServerPort = 9000,
    [int]$TestGapSeconds = 8,
    [int]$AutoTestStartDelaySeconds = 12,
    [string]$DemoDir = "$env:TEMP\honeygrid_demo"
)

# Enable error handling
$ErrorActionPreference = "Stop"

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           HoneyGrid - Demo Environment Launcher            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

function Get-PythonCommand {
    $venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return "python"
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        return $null -ne $conn
    } catch {
        return $false
    }
}

function Invoke-DemoTestSequence {
    param(
        [string]$HoneytokenDir,
        [int]$GapSeconds = 8,
        [int]$StartDelaySeconds = 12
    )

    Write-Host "" 
    Write-Host "🤖 Auto test mode enabled. Starting sequence in $StartDelaySeconds second(s)..." -ForegroundColor Magenta
    Start-Sleep -Seconds $StartDelaySeconds

    $dbPath = Join-Path $HoneytokenDir "db_password.txt"
    $roadmapPath = Join-Path $HoneytokenDir "roadmap.txt"
    $configPath = Join-Path $HoneytokenDir "config.env"
    $newSecretPath = Join-Path $HoneytokenDir "new_secret.txt"
    $dbBackupPath = Join-Path $HoneytokenDir "db_password_backup.txt"

    $steps = @(
        @{ Name = "ACCESS"; Action = { Get-Content $roadmapPath | Out-Null } },
        @{ Name = "MODIFY"; Action = { Add-Content $dbPath "BREACH DETECTED" } },
        @{ Name = "CREATE"; Action = {
                if (Test-Path $newSecretPath) { Remove-Item $newSecretPath -Force }
                New-Item -Path $newSecretPath -ItemType File | Out-Null
            }
        },
        @{ Name = "DELETE"; Action = {
                if (Test-Path $configPath) { Remove-Item $configPath -Force }
            }
        },
        @{ Name = "RENAME"; Action = {
                if (Test-Path $dbBackupPath) { Remove-Item $dbBackupPath -Force }
                if (Test-Path $dbPath) { Rename-Item $dbPath -NewName "db_password_backup.txt" }
            }
        },
        @{ Name = "BULK_MODIFY"; Action = {
                for ($i = 0; $i -lt 5; $i++) { Add-Content $roadmapPath "Edit $i" }
            }
        }
    )

    foreach ($step in $steps) {
        try {
            & $step.Action
            Write-Host ("[{0}] ✅ {1}" -f (Get-Date -Format "HH:mm:ss"), $step.Name) -ForegroundColor DarkGreen
        } catch {
            Write-Host ("[{0}] ⚠ {1} failed: {2}" -f (Get-Date -Format "HH:mm:ss"), $step.Name, $_.Exception.Message) -ForegroundColor Yellow
        }
        Start-Sleep -Seconds $GapSeconds
    }

    Write-Host "🤖 Auto test sequence complete." -ForegroundColor Magenta
}

$pythonCmd = Get-PythonCommand

if ($RecordingMode) {
    Write-Host "🎥 Recording mode enabled (cleaner output + deterministic cues)" -ForegroundColor Magenta
}

if ($AutoRunTests) {
    Write-Host "🤖 AutoRunTests enabled (timed command execution)" -ForegroundColor Magenta
}

if (Test-PortInUse -Port $ServerPort) {
    Write-Host "✗ Port $ServerPort is already in use." -ForegroundColor Red
    Write-Host "  Run .\stop_demo.ps1 or free the port, then retry." -ForegroundColor Yellow
    exit 1
}

# Check Python
Write-Host "✓ Checking Python environment..." -ForegroundColor Green
$pythonVersion = & $pythonCmd --version 2>&1
if ($pythonVersion -match "3\.[0-9]+") {
    Write-Host "  $pythonVersion" -ForegroundColor DarkGreen
} else {
    Write-Host "✗ Python 3.10+ required" -ForegroundColor Red
    exit 1
}

# Check/create certificates
Write-Host ""
Write-Host "✓ Checking SSL certificates..." -ForegroundColor Green
if ($SkipCertGeneration) {
    Write-Host "  Skipping certificate generation (--SkipCertGeneration)" -ForegroundColor DarkYellow
} elseif (-not (Test-Path "certs/ca.crt")) {
    Write-Host "  Generating certificates..." -ForegroundColor Yellow
    # Clean Python cache to ensure fresh cert generation
    if (Test-Path "scripts/__pycache__") {
        Remove-Item -Recurse -Force "scripts/__pycache__" | Out-Null
    }
    & $pythonCmd "scripts/generate_certs.py" 3
} else {
    Write-Host "  Certificates found" -ForegroundColor DarkGreen
}

# Create demo honeytoken directory
Write-Host ""
Write-Host "✓ Setting up demo honeytokens..." -ForegroundColor Green
$honeytokenDir = $DemoDir
if (-not (Test-Path $honeytokenDir)) {
    New-Item -ItemType Directory -Path $honeytokenDir | Out-Null
    Write-Host "  Created: $honeytokenDir" -ForegroundColor DarkGreen
} else {
    Write-Host "  Using: $honeytokenDir" -ForegroundColor DarkGreen
}

# Create sample honeytokens
@"
This is a honeytoken - if you're reading this, someone accessed it!
File: Secret Database Credentials
Created: $(Get-Date)
"@ | Set-Content "$honeytokenDir\db_password.txt"

@"
CONFIDENTIAL: Project Roadmap 2026
Infrastructure, enhanced monitoring, and anomaly detection capabilities
"@ | Set-Content "$honeytokenDir\roadmap.txt"

@"
API_KEY = sk-honeygrid-demo-12345
DB_HOST = internal-db.local
DB_USER = admin
DB_PASSWORD = SuperSecretPassword123!
"@ | Set-Content "$honeytokenDir\config.env"

Write-Host "  Created 3 sample honeytokens" -ForegroundColor DarkGreen

# Start server
Write-Host ""
Write-Host "⚙ Starting HoneyGrid Server..." -ForegroundColor Cyan
$serverProcess = Start-Process $pythonCmd -ArgumentList @("server/server.py", "--host", "0.0.0.0", "--port", "$ServerPort") -NoNewWindow -PassThru
Write-Host "  Server PID: $($serverProcess.Id)" -ForegroundColor DarkGreen
Start-Sleep -Seconds 2

# Start GUI
Write-Host ""
Write-Host "⚙ Starting GUI Dashboard..." -ForegroundColor Cyan
$guiProcess = Start-Process $pythonCmd -ArgumentList "gui_tk/app.py" -NoNewWindow -PassThru
Write-Host "  GUI PID: $($guiProcess.Id)" -ForegroundColor DarkGreen
Start-Sleep -Seconds 2

# Start agents
Write-Host ""
Write-Host "⚙ Starting Demo Agents..." -ForegroundColor Cyan

# Agent 1 (uses auto-generated agent-001 cert)
$agent1Config = @{
    agent_id = "agent-001"
    server_host = "localhost"
    server_port = 9000
    watch_paths = @("$honeytokenDir\db_password.txt")
    token_mapping = @{
        "$honeytokenDir\db_password.txt" = "token-db-creds"
    }
}

$agent1Process = Start-Process $pythonCmd -ArgumentList @(
    "agent/agent.py",
    "--agent-id", $agent1Config.agent_id,
    "--server-host", $agent1Config.server_host,
    "--server-port", "$ServerPort",
    "--watch-path", "$honeytokenDir\db_password.txt",
    "--token-id", "token-db-creds"
) -NoNewWindow -PassThru

Write-Host "  Agent agent-001 (monitoring db_password.txt) - PID: $($agent1Process.Id)" -ForegroundColor DarkGreen
Start-Sleep -Seconds 2

# Agent 2 (uses auto-generated agent-002 cert)
$agent2Process = Start-Process $pythonCmd -ArgumentList @(
    "agent/agent.py",
    "--agent-id", "agent-002",
    "--server-host", "localhost",
    "--server-port", "$ServerPort",
    "--watch-path", "$honeytokenDir\roadmap.txt",
    "--token-id", "token-roadmap"
) -NoNewWindow -PassThru

Write-Host "  Agent agent-002 (monitoring roadmap.txt) - PID: $($agent2Process.Id)" -ForegroundColor DarkGreen
Start-Sleep -Seconds 2

# Agent 3 (uses auto-generated agent-003 cert)
$agent3Process = Start-Process $pythonCmd -ArgumentList @(
    "agent/agent.py",
    "--agent-id", "agent-003",
    "--server-host", "localhost",
    "--server-port", "$ServerPort",
    "--watch-path", "$honeytokenDir\config.env",
    "--token-id", "token-config"
) -NoNewWindow -PassThru

Write-Host "  Agent agent-003 (monitoring config.env) - PID: $($agent3Process.Id)" -ForegroundColor DarkGreen
Start-Sleep -Seconds 2

# Summary
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                  🟢 Demo Running Successfully              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Dashboard:     GUI (tkinter window)" -ForegroundColor Cyan
Write-Host "🔗 Server:        localhost:$ServerPort" -ForegroundColor Cyan
Write-Host "👁️  Agents:        3 (agent-001, agent-002, agent-003)" -ForegroundColor Cyan
Write-Host "🎯 Honeytokens:   $honeytokenDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 Demo Actions:" -ForegroundColor Yellow
Write-Host "  Open another PowerShell window and try these commands:" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "🔍 TEST FILE MODIFICATION (Add-Content):" -ForegroundColor Cyan
Write-Host "Add-Content '$honeytokenDir\db_password.txt' 'BREACH DETECTED'" -ForegroundColor Gray
Write-Host " → Should trigger MODIFIED event in GUI" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "📖 TEST FILE ACCESS (Get-Content):" -ForegroundColor Cyan
Write-Host "Get-Content '$honeytokenDir\roadmap.txt'" -ForegroundColor Gray
Write-Host " → Should trigger ACCESSED event in GUI" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "➕ TEST FILE CREATION:" -ForegroundColor Cyan
Write-Host "New-Item -Path '$honeytokenDir\new_secret.txt' -ItemType File" -ForegroundColor Gray
Write-Host " → Should trigger CREATED event in GUI" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "❌ TEST FILE DELETION:" -ForegroundColor Cyan
Write-Host "Remove-Item '$honeytokenDir\config.env'" -ForegroundColor Gray
Write-Host " → Should trigger DELETED event in GUI" -ForegroundColor DarkGreen
Write-Host ""
Write-Host " ✏️  TEST FILE RENAME:" -ForegroundColor Cyan
Write-Host "Rename-Item '$honeytokenDir\db_password.txt' 'db_password_backup.txt'" -ForegroundColor Gray
Write-Host " → Should trigger MOVED event in GUI" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "⏱️  BULK TEST (rapid modifications):" -ForegroundColor Cyan
$bulkCmd = 'for ($i = 0; $i -lt 5; $i++) { Add-Content "__PATH__" "Edit $i" }'
$bulkCmd = $bulkCmd.Replace('__PATH__', "$honeytokenDir\roadmap.txt")
Write-Host $bulkCmd -ForegroundColor Gray
Write-Host " → Should trigger multiple MODIFIED events" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "💡 Watch the GUI dashboard for real-time alerts!" -ForegroundColor Yellow

if ($RecordingMode) {
    Write-Host "" 
    Write-Host "🎬 Recording cue sheet:" -ForegroundColor Magenta
    Write-Host "  1) Show GUI map with 3 green agents" -ForegroundColor Gray
    Write-Host "  2) Run: Get-Content '$honeytokenDir\roadmap.txt'" -ForegroundColor Gray
    Write-Host "  3) Run: Add-Content '$honeytokenDir\db_password.txt' 'BREACH DETECTED'" -ForegroundColor Gray
    Write-Host "  4) Run: Rename-Item '$honeytokenDir\db_password.txt' 'db_password_backup.txt'" -ForegroundColor Gray
    Write-Host "  5) Open Alerts tab and Event details dialog" -ForegroundColor Gray
}

if ($AutoRunTests) {
    Write-Host "" 
    Write-Host "⏳ Auto tests will run every $TestGapSeconds second(s), after $AutoTestStartDelaySeconds second(s) initial delay." -ForegroundColor DarkMagenta
    Start-Job -Name "HoneyGridAutoDemoTests" -ScriptBlock {
        param($dir, $gap, $delay)

        $dbPath = Join-Path $dir "db_password.txt"
        $roadmapPath = Join-Path $dir "roadmap.txt"
        $configPath = Join-Path $dir "config.env"
        $newSecretPath = Join-Path $dir "new_secret.txt"
        $dbBackupPath = Join-Path $dir "db_password_backup.txt"

        Start-Sleep -Seconds $delay

        try { Get-Content $roadmapPath | Out-Null } catch {}
        Start-Sleep -Seconds $gap

        try { Add-Content $dbPath "BREACH DETECTED" } catch {}
        Start-Sleep -Seconds $gap

        try {
            if (Test-Path $newSecretPath) { Remove-Item $newSecretPath -Force }
            New-Item -Path $newSecretPath -ItemType File | Out-Null
        } catch {}
        Start-Sleep -Seconds $gap

        try {
            if (Test-Path $configPath) { Remove-Item $configPath -Force }
        } catch {}
        Start-Sleep -Seconds $gap

        try {
            if (Test-Path $dbBackupPath) { Remove-Item $dbBackupPath -Force }
            if (Test-Path $dbPath) { Rename-Item $dbPath -NewName "db_password_backup.txt" }
        } catch {}
        Start-Sleep -Seconds $gap

        try {
            for ($i = 0; $i -lt 5; $i++) { Add-Content $roadmapPath "Edit $i" }
        } catch {}
    } -ArgumentList $honeytokenDir, $TestGapSeconds, $AutoTestStartDelaySeconds | Out-Null

    Write-Host "▶ Auto test job started: HoneyGridAutoDemoTests" -ForegroundColor DarkMagenta
}

Write-Host ""
Write-Host "🛑 To Stop:" -ForegroundColor Yellow
Write-Host "Press Ctrl+C in any window, or run:" -ForegroundColor DarkYellow
Write-Host ".\stop_demo.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "Process IDs for monitoring:" -ForegroundColor Cyan
Write-Host "  Server: $($serverProcess.Id)" -ForegroundColor Gray
Write-Host "  GUI:    $($guiProcess.Id)" -ForegroundColor Gray
Write-Host "  Agent1: $($agent1Process.Id)" -ForegroundColor Gray
Write-Host "  Agent2: $($agent2Process.Id)" -ForegroundColor Gray
Write-Host "  Agent3: $($agent3Process.Id)" -ForegroundColor Gray
Write-Host ""

$metaOut = Join-Path $scriptDir "report_assets\slide_images\screenshots\demo_run_info.txt"
"RunTime: $(Get-Date -Format s)`nServerPort: $ServerPort`nHoneytokenDir: $honeytokenDir`nServerPID: $($serverProcess.Id)`nGUIPID: $($guiProcess.Id)`nAgent1PID: $($agent1Process.Id)`nAgent2PID: $($agent2Process.Id)`nAgent3PID: $($agent3Process.Id)" | Set-Content $metaOut
Write-Host "🗂️  Run metadata saved: $metaOut" -ForegroundColor DarkCyan

# Wait for processes
Write-Host "Waiting for demo to complete (Ctrl+C to stop)..." -ForegroundColor Cyan
Write-Host ""

try {
    while ($true) {
        if ($serverProcess.HasExited -or $guiProcess.HasExited) {
            Write-Host ""
            Write-Host "⚠️ Demo process stopped" -ForegroundColor Yellow
            break
        }
        Start-Sleep -Seconds 1
    }
} catch {
    # Handle Ctrl+C
}

# Cleanup
Write-Host ""
Write-Host "Cleaning up..." -ForegroundColor Yellow

# Kill processes if still running
@($serverProcess, $guiProcess, $agent1Process, $agent2Process, $agent3Process) | 
    Where-Object { -not $_.HasExited } | 
    ForEach-Object { $_ | Stop-Process -Force -ErrorAction SilentlyContinue }

# Stop auto test job if present
Get-Job -Name "HoneyGridAutoDemoTests" -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Job $_ -ErrorAction SilentlyContinue } catch {}
    try { Remove-Job $_ -Force -ErrorAction SilentlyContinue } catch {}
}

Write-Host "✓ Cleanup complete" -ForegroundColor Green
Write-Host ""
Write-Host "Demo environment stopped." -ForegroundColor Cyan
