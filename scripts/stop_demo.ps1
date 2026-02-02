#!/usr/bin/env pwsh
<#
.SYNOPSIS
    HoneyGrid Demo Stopper - Gracefully stops all demo processes
    
.DESCRIPTION
    Terminates the server, GUI, and agent processes started by run_demo.ps1
    
.EXAMPLE
    .\stop_demo.ps1
    
.NOTES
    Safely cleans up all HoneyGrid demo processes
#>

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║            HoneyGrid - Demo Environment Stopper            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Kill by process patterns
$patterns = @(
    "python*server.py",
    "python*gui_tk*app.py",
    "python*agent*agent.py"
)

$killed = 0

foreach ($pattern in $patterns) {
    $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "server\.py|app\.py|agent\.py" }
    
    foreach ($proc in $processes) {
        try {
            $proc | Stop-Process -Force
            $killed++
            Write-Host "✓ Stopped: $($proc.Name) (PID: $($proc.Id))" -ForegroundColor Green
        } catch {
            Write-Host "⚠ Failed to stop process: $($proc.Id)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
if ($killed -gt 0) {
    Write-Host "✓ Stopped $killed HoneyGrid process(es)" -ForegroundColor Green
} else {
    Write-Host "ℹ No running HoneyGrid processes found" -ForegroundColor Cyan
}

# Optional: Show remaining Python processes
Write-Host ""
Write-Host "Remaining Python processes:" -ForegroundColor Cyan
$remaining = @(Get-Process python -ErrorAction SilentlyContinue | Format-Table -Property Id, ProcessName, CommandLine | Out-String)
if ($remaining.Length -gt 0) {
    Write-Host $remaining -ForegroundColor DarkGray
} else {
    Write-Host "None" -ForegroundColor Gray
}

Write-Host "Demo environment stopped." -ForegroundColor Cyan
Write-Host ""
