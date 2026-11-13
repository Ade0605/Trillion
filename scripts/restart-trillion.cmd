@echo off
REM Restart the Trillion Windows service, reliably, with a single UAC click.
REM
REM Why not fully no-admin? The Trillion service runs as LocalSystem, and this
REM machine's user is a filtered-admin account. Windows denies service- and
REM task-control to that account's non-elevated token no matter how a scheduled
REM task is registered (both schtasks /run and Start-ScheduledTask return
REM "Access is denied", and the task never fires). So one UAC prompt is the floor
REM here. This self-elevates and restarts in ~20s.
REM
REM (A true standard-user account could use the "Trillion Restart" scheduled task
REM  with no prompt; install it with scripts\install_restart_task.ps1.)
echo Restarting Trillion (approve the UAC prompt)...
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-WindowStyle','Hidden','-Command','Restart-Service -Name Trillion -Force'"
echo Triggered. Trillion relists on port 7777 within a few seconds.
