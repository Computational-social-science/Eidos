@echo off
REM Start the monitor at logon without administrator rights: a one-line shim in the user's
REM Startup folder. A scheduled ONLOGON task is refused without elevation on this host, and the
REM Startup folder is the supported per-user equivalent.
REM
REM   scripts\install-autostart.cmd           install + start now
REM   scripts\install-autostart.cmd remove    uninstall
setlocal
set SHIM=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\eidos-monitor.cmd

if /i "%~1"=="remove" (
    if exist "%SHIM%" del "%SHIM%"
    echo removed %SHIM%
    exit /b 0
)

REM Record the interpreter this shell resolves, so the service does not inherit a random one.
if "%PYTHON%"=="" for /f "delims=" %%i in ('where python 2^>nul') do if not defined PYTHON set "PYTHON=%%i"
if defined PYTHON > "%~dp0monitor.env" echo set PYTHON=%PYTHON%

> "%SHIM%" echo @echo off
>> "%SHIM%" echo call "%~dp0eidos-monitor.cmd"
echo wrote %SHIM%
start "" /min cmd /c "%~dp0eidos-monitor.cmd"
echo started the monitor
