@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title AI Video Web Editor

echo.
echo ========================================
echo   AI Video Web Editor
echo ========================================
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)

if not defined PYTHON_CMD (
  echo Python 3.10+ was not detected.
  echo Please install Python from:
  echo https://www.python.org/downloads/
  echo During installation, enable "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

echo Python command: %PYTHON_CMD%
echo.

echo Checking dependencies...
%PYTHON_CMD% -c "import flask, PIL, edge_tts, moviepy, imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
  echo First launch: installing dependencies. This may take a few minutes...
  %PYTHON_CMD% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check your network, then run:
    echo %PYTHON_CMD% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
  %PYTHON_CMD% -c "import flask, PIL, edge_tts, moviepy, imageio_ffmpeg" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo Dependencies still cannot be imported after installation.
    echo Please send the error output above to the developer.
    echo.
    pause
    exit /b 1
  )
)

if not exist "output\plan.json" (
  echo.
  echo No editable project found: output\plan.json does not exist.
  echo Generate a draft first, for example:
  echo %PYTHON_CMD% run_workflow.py --demo-assets --clean --skip-tts --skip-mp4
  echo.
  pause
  exit /b 1
)

echo Dependencies are ready.
echo.
echo Starting the web editor...
echo URL: http://127.0.0.1:5000
echo The browser should open automatically.
echo Close this window to stop the service.
echo.

%PYTHON_CMD% web_app.py

echo.
echo Web editor stopped.
pause
endlocal
