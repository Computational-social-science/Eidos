@echo off
REM Keep the monitor alive across session ends, crashes and stalls.
REM
REM The loop itself lives in tools\monitor_supervisor.py, which holds a lock and knows whether
REM another supervisor is already running; a batch loop cannot.
setlocal
cd /d "%~dp0.."

REM The interpreter is this host's business, not the repository's: a local file names it.
REM A .env is data, not an executable .bat/.cmd. Python reads its literal SET values.
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUTF8=1"
if "%PYTHON%"=="" set "PYTHON=python"
"%PYTHON%" "%~dp0..\tools\launch_runtime.py" monitor %*
exit /b %ERRORLEVEL%
