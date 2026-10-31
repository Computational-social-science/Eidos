@echo off
setlocal
cd /d "%~dp0.."
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUTF8=1"
if "%PYTHON%"=="" set "PYTHON=python"
"%PYTHON%" "%~dp0..\tools\launch_runtime.py" install %*
exit /b %ERRORLEVEL%
