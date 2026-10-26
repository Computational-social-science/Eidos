@echo off
REM Register the monitor as a per-user scheduled task: starts at logon, no admin required.
REM
REM   scripts\register-monitor.cmd            install + start
REM   scripts\register-monitor.cmd remove     uninstall
setlocal
set TASK=Eidos Monitor
set RUNNER="%~dp0eidos-monitor.cmd"

if /i "%~1"=="remove" (
    schtasks /Delete /TN "%TASK%" /F
    exit /b %ERRORLEVEL%
)

schtasks /Create /TN "%TASK%" /TR %RUNNER% /SC ONLOGON /RL LIMITED /F
if errorlevel 1 exit /b 1
schtasks /Run /TN "%TASK%"
echo registered "%TASK%" to run %RUNNER% at logon
