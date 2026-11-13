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

# Registered via the Task Scheduler COM API so we can set a security descriptor:
# the task RUNS as SYSTEM (a service account — no UAC consent, unlike a user +
# Highest principal, which fails a non-interactive trigger with 0x800710E0), and
# its SDDL grants Authenticated Users read+execute so ANY signed-in user can
# TRIGGER it with `schtasks /run` without being an administrator. SYSTEM alone is
# not enough: without this SDDL a non-admin trigger returns "Access is denied".
$cmd = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ""Restart-Service -Name '$ServiceName' -Force"""

$svc = New-Object -ComObject Schedule.Service
$svc.Connect()
$root = $svc.GetFolder("\")

$def = $svc.NewTask(0)
$def.RegistrationInfo.Description = "Restarts the Trillion service on demand (no elevation needed to trigger)."
$def.Principal.UserId = "SYSTEM"
$def.Principal.LogonType = 5          # TASK_LOGON_SERVICE_ACCOUNT
$def.Principal.RunLevel = 1           # TASK_RUNLEVEL_HIGHEST
$def.Settings.Enabled = $true
$def.Settings.AllowDemandStart = $true
$def.Settings.StartWhenAvailable = $true
$def.Settings.DisallowStartIfOnBatteries = $false
$def.Settings.StopIfGoingOnBatteries = $false
$def.Settings.MultipleInstances = 3   # TASK_INSTANCES_STOP_EXISTING

$act = $def.Actions.Create(0)         # TASK_ACTION_EXEC
$act.Path = "powershell.exe"
$act.Arguments = $cmd

# D: owner SYSTEM/Admins full (GA); Authenticated Users read+execute (GRGX) so a
# standard user can run it on demand.
$sddl = "D:(A;;GA;;;BA)(A;;GA;;;SY)(A;;GRGX;;;AU)"

# RegisterTaskDefinition(path, def, flags=6 CREATE_OR_UPDATE, user='SYSTEM',
#   password=$null, logonType=5 SERVICE_ACCOUNT, sddl)
$root.RegisterTaskDefinition($TaskName, $def, 6, "SYSTEM", $null, 5, $sddl) | Out-Null

Write-Host "== registered task '$TaskName' (runs as SYSTEM; any user may trigger it)."
Write-Host "== from now on, restart with NO admin needed:"
Write-Host "     scripts\restart-trillion.cmd"
Write-Host "   or:"
Write-Host "     schtasks /run /tn `"$TaskName`""
