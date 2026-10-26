@echo off
REM Keep the monitor alive across session ends, crashes and stalls.
REM
REM The loop itself lives in tools\monitor_supervisor.py, which holds a lock and knows whether
REM another supervisor is already running; a batch loop cannot.
setlocal
cd /d "%~dp0.."

REM The interpreter is this host's business, not the repository's: a local file names it.
if exist "%~dp0monitor.env" call "%~dp0monitor.env"
if "%PYTHON%"=="" set PYTHON=python
if not exist "%QUARTO_BIN%" set QUARTO_BIN=%~dp0..\..	ools\quartoin\quarto.exe

"%PYTHON%" tools\monitor_supervisor.py
