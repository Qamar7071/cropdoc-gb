@echo off
REM CropDoc GB: one command to install (first run) and start the app on http://127.0.0.1:8000
REM Double-click this file, or run:  start.bat --no-browser --port 8080
setlocal
cd /d "%~dp0"
title CropDoc GB

set "PY="
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.11 -c "import sys" >nul 2>nul && set "PY=py -3.11"
  if not defined PY py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Python 3.11 or newer is required. Install Python 3.11 from https://www.python.org/downloads/
  echo During installation tick "Add python.exe to PATH", then double-click start.bat again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a virtual environment in .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment.
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" scripts\ensure_deps.py
if errorlevel 1 (
  pause
  exit /b 1
)

".venv\Scripts\python.exe" backend\run.py %*
pause
