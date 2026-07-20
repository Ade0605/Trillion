<#
Install Trillion's web server as a Windows service (runs before login).

Must run elevated. nssm supervises the process itself — restarting it on exit —
so this replaces both scripts/serve_supervisor.py and the "Trillion Server"
scheduled task. Those are disabled here; leaving them running would race the
service for port 7777.

The morning brief stays a *user* scheduled task on purpose: services run in
Session 0 and cannot play audio to the desktop, so a spoken brief from a
service would be silent.

    powershell -ExecutionPolicy Bypass -File scripts\install_service.ps1
#>
param(
    [string]$ServiceName = "Trillion",
    [string]$ProjectDir  = "C:\Users\delux\Bami AI Jarvis\trillion",
    [string]$Python      = "C:\Users\delux\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe",
    [string]$Nssm        = "C:\Users\delux\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_Microsoft.Winget.Source_8wekyb3d8bbwe\nssm-2.24-101-g897c7ad\win64\nssm.exe"
)

$ErrorActionPreference = "Stop"

if (-not (New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Must run elevated."; exit 1
}
foreach ($p in @($Nssm, $Python, $ProjectDir)) {
    if (-not (Test-Path -LiteralPath $p)) { Write-Error "Missing: $p"; exit 1 }
}

Write-Host "== stopping the scheduled task + supervisor (they would race the service for 7777)"
try { Stop-ScheduledTask -TaskName "Trillion Server" -ErrorAction SilentlyContinue } catch {}
try { Disable-ScheduledTask -TaskName "Trillion Server" -ErrorAction SilentlyContinue | Out-Null } catch {}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'serve_supervisor|web_server' } |
    ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
Start-Sleep -Seconds 2

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "== removing existing service"
    & $Nssm stop $ServiceName confirm | Out-Null
    & $Nssm remove $ServiceName confirm | Out-Null
    Start-Sleep -Seconds 2
}

Write-Host "== installing service '$ServiceName'"
& $Nssm install $ServiceName $Python "web_server.py" | Out-Null
& $Nssm set $ServiceName AppDirectory   $ProjectDir            | Out-Null
& $Nssm set $ServiceName DisplayName    "Trillion AI Assistant" | Out-Null
& $Nssm set $ServiceName Description    "Trillion's web server on port 7777" | Out-Null
& $Nssm set $ServiceName Start          SERVICE_AUTO_START     | Out-Null
# restart on any exit, ~2s later; throttle guards a crash loop
& $Nssm set $ServiceName AppExit Default Restart               | Out-Null
& $Nssm set $ServiceName AppRestartDelay 2000                  | Out-Null
& $Nssm set $ServiceName AppThrottle     5000                  | Out-Null
& $Nssm set $ServiceName AppStdout "$ProjectDir\logs\service.out.log" | Out-Null
& $Nssm set $ServiceName AppStderr "$ProjectDir\logs\service.err.log" | Out-Null
& $Nssm set $ServiceName AppRotateFiles  1                     | Out-Null
& $Nssm set $ServiceName AppRotateBytes  1048576               | Out-Null

Write-Host "== starting"
& $Nssm start $ServiceName | Out-Null

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Get-NetTCPConnection -LocalPort 7777 -State Listen -ErrorAction SilentlyContinue) { break }
}
$svc = Get-Service -Name $ServiceName
$listening = [bool](Get-NetTCPConnection -LocalPort 7777 -State Listen -ErrorAction SilentlyContinue)
Write-Host "service=$($svc.Status) startType=$($svc.StartType) listening=$listening afterSeconds=$i"
if (-not $listening) {
    Write-Host "--- stderr tail ---"
    Get-Content "$ProjectDir\logs\service.err.log" -Tail 20 -ErrorAction SilentlyContinue
}
