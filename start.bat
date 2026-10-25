@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo =====================================================================
echo                PharmaTrack System Launcher
echo =====================================================================
echo.

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_PY%" goto :venv_exists

REM Virtual environment does not exist. Locate Python 3.11+
echo [*] Searching for Python 3.11 or higher...
set "PY_CMD="

py -3.14 -V >nul 2>&1 && set "PY_CMD=py -3.14"
if not defined PY_CMD py -3.13 -V >nul 2>&1 && set "PY_CMD=py -3.13"
if not defined PY_CMD py -3.12 -V >nul 2>&1 && set "PY_CMD=py -3.12"
if not defined PY_CMD py -3.11 -V >nul 2>&1 && set "PY_CMD=py -3.11"
if not defined PY_CMD py -3 -V >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD python -V >nul 2>&1 && set "PY_CMD=python"

if not defined PY_CMD (
    echo [ERROR] Python 3.11 or higher was not found in PATH.
    echo Please install Python 3.11 or higher: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Using Python:
%PY_CMD% --version
echo.

echo [*] Creating virtual environment in .venv...
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment created successfully.
echo.

:venv_exists
echo [OK] Using virtual environment python:
"%VENV_PY%" --version
echo.

echo [*] Verifying application dependencies...
"%VENV_PY%" -c "import streamlit, pandas, numpy, matplotlib, seaborn" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing missing dependencies from requirements.txt...
    "%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
    echo [OK] All dependencies installed successfully.
) else (
    echo [OK] All required dependencies are already satisfied.
)
echo.

set "DATA_MISSING="
if not exist "%~dp0data\raw\medicines.csv" set "DATA_MISSING=1"
if not exist "%~dp0data\raw\inventory.csv" set "DATA_MISSING=1"
if not exist "%~dp0data\raw\sales.csv" set "DATA_MISSING=1"

if defined DATA_MISSING (
    echo [*] Synthetic datasets not found. Generating reproducible data...
    "%VENV_PY%" -m src.data.generator
    if errorlevel 1 (
        echo [ERROR] Failed to generate sample datasets.
        pause
        exit /b 1
    )
    echo [OK] Sample data generated successfully in data\raw\
) else (
    echo [OK] Verified sample datasets in data\raw\
)
echo.

echo =====================================================================
echo [*] Launching PharmaTrack Clinical Operations System...
echo [*] Dashboard will open in your browser at: http://localhost:8501
echo [*] Press Ctrl+C in this terminal window to stop the server.
echo =====================================================================
echo.

"%VENV_PY%" -m streamlit run "%~dp0app.py"

echo.
echo [*] PharmaTrack server stopped.
pause
endlocal
