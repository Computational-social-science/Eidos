@echo off
REM Compatibility entry: install one hidden per-user Startup entry.
call "%~dp0install-autostart.cmd" %*
exit /b %ERRORLEVEL%
