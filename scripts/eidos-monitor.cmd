@echo off
REM Keep the Eidos monitor alive across session ends, crashes and stalls.
REM
REM `serve_site.py` exits on purpose when its sampler stalls (code 3); this loop is what turns
REM that exit into a restart. Register it once with scripts/register-monitor.cmd, not by hand.
setlocal
cd /d "%~dp0.."

REM The interpreter is this host's business, not the repository's: a local file names it.
if exist "%~dp0monitor.env" call "%~dp0monitor.env"
REM A parent shell may point PYTHONPATH at another environment (the agent venv does), and may
REM disable the user site where dvc/mlflow are installed. The monitor needs this host's packages.
set PYTHONPATH=
set PYTHONNOUSERSITE=
if "%PYTHON%"=="" set PYTHON=python
if not exist "%QUARTO_BIN%" set QUARTO_BIN=%~dp0..\..\tools\quarto\bin\quarto.exe

:loop
"%PYTHON%" tools\serve_site.py --port 8765 >> docs\status\serve.log 2>&1
echo %DATE% %TIME% serve_site exited with %ERRORLEVEL%; restarting in 5 s >> docs\status\serve.log
timeout /t 5 /nobreak >nul
goto loop
