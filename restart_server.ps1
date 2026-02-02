param(
    [string]$DbPath = "data\honeygrid.db",
    [securestring]$DbPassword = (ConvertTo-SecureString "change_this_password" -AsPlainText -Force),
    [string]$ServerHost = "0.0.0.0",
    [int]$Port = 9000,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "Stopping HoneyGrid server..." -ForegroundColor Yellow

$serverProcs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "server\\server\.py"
}

if ($serverProcs) {
    foreach ($proc in $serverProcs) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        } catch {
            # ignore
        }
    }
}

# Wait for port to close
$deadline = (Get-Date).AddSeconds(5)
while ((Get-Date) -lt $deadline) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $Port)
        $client.Close()
        Start-Sleep -Milliseconds 200
    } catch {
        break
    }
}

Write-Host "Starting HoneyGrid server..." -ForegroundColor Green

$pythonExe = $PythonPath
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    if ($env:VIRTUAL_ENV) {
        $pythonExe = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    } else {
        $pythonExe = "python"
    }
}

# Convert SecureString to plaintext only for passing to subprocess
$plainDbPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($DbPassword))

$serverArgs = @(
    "server/server.py",
    "--host", $ServerHost,
    "--port", $Port,
    "--db", $DbPath,
    "--db-password", $plainDbPassword
)

Start-Process -FilePath $pythonExe -ArgumentList $serverArgs -WindowStyle Hidden

Write-Host "Server restarted on $($ServerHost):$($Port)" -ForegroundColor DarkGreen
