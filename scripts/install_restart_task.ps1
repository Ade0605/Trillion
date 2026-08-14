<#
Register a "Trillion Restart" scheduled task so the service can be restarted
WITHOUT opening an elevated shell every time.

Why this is needed: the Trillion web server runs as a Windows service in
Session 0 under the service account. Stopping/restarting it needs service-control
privilege (admin), so `Restart-Service Trillion` fails from a normal shell.

The fix: a scheduled task registered for the current user with RunLevel=Highest.
A Highest task runs with an elevated token when triggered, and the owner can
trigger an already-registered task on demand WITHOUT a UAC prompt. So this
installer needs admin ONCE; after that, scripts\restart-trillion.cmd (or
`schtasks /run /tn "Trillion Restart"`) restarts the service with no elevation.

    powershell -ExecutionPolicy Bypass -File scripts\install_restart_task.ps1
#>
param(
    [string]$ServiceName = "Trillion",
    [string]$TaskName    = "Trillion Restart"
)

$ErrorActionPreference = "Stop"

if (-not (New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Must run elevated (right-click PowerShell -> Run as administrator). This is the ONLY step that needs admin."
    exit 1
}

if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    Write-Error "Service '$ServiceName' not found. Install it first with scripts\install_service.ps1."
    exit 1
}

$me = "$env:USERDOMAIN\$env:USERNAME"

# The task simply restarts the service. -WindowStyle Hidden so no console flashes.
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"Restart-Service -Name '$ServiceName' -Force`""

# Highest run level = the task runs elevated when triggered, so it can control
# the service. Interactive logon = runs as the signed-in user (the owner), who
# can then trigger it without a UAC prompt.
$principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal -Settings $settings `
    -Description "Restarts the Trillion Windows service on demand (no elevation needed to trigger)." -Force | Out-Null

Write-Host "== registered task '$TaskName' (runs as $me, elevated)."
Write-Host "== from now on, restart with NO admin needed:"
Write-Host "     scripts\restart-trillion.cmd"
Write-Host "   or:"
Write-Host "     schtasks /run /tn `"$TaskName`""
