@echo off
REM Restart the Trillion service WITHOUT elevation, by triggering the
REM "Trillion Restart" scheduled task (run scripts\install_restart_task.ps1
REM once, elevated, to register it). Double-click this file or run it from a
REM normal terminal.
echo Restarting Trillion service...
schtasks /run /tn "Trillion Restart"
if %errorlevel%==0 (
  echo Triggered. It relists on port 7777 within a few seconds.
) else (
  echo FAILED. Register the task first: powershell -ExecutionPolicy Bypass -File scripts\install_restart_task.ps1  ^(run as admin^)
)
