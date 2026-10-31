@echo off
setlocal
cd /d "%~dp0.."
if exist "%~dp0monitor.env" call "%~dp0monitor.env"
if "%PYTHON%"=="" set PYTHON=python
if /i "%~1"=="remove" (
    "%PYTHON%" tools\install_autostart.py --remove
) else (
    "%PYTHON%" tools\install_autostart.py
)
exit /b %ERRORLEVEL%
