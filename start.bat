@echo off
REM ==============================================================================
REM Accuport Quick Start for Windows
REM Creates venv if needed, installs deps, starts dashboard
REM ==============================================================================

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%venv
set DASHBOARD_DIR=%SCRIPT_DIR%dashbored
set REQUIREMENTS=%SCRIPT_DIR%requirements.txt

echo.
echo Accuport Quick Start (Windows)
echo ==============================
echo.

REM Check if dashboard exists
if not exist "%DASHBOARD_DIR%\app.py" (
    echo ERROR: Dashboard not found at %DASHBOARD_DIR%\app.py
    exit /b 1
)

REM Check if venv exists, create if not
if not exist "%VENV_DIR%\" (
    echo Virtual environment not found. Creating...

    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python not found. Please install Python 3.8+
        exit /b 1
    )

    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        exit /b 1
    )
    echo Virtual environment created.

    if exist "%REQUIREMENTS%" (
        echo Installing dependencies - this may take a minute...
        "%VENV_DIR%\Scripts\pip.exe" install --upgrade pip -q
        "%VENV_DIR%\Scripts\pip.exe" install -r "%REQUIREMENTS%" -q
        if errorlevel 1 (
            echo ERROR: Failed to install dependencies
            exit /b 1
        )
        echo Dependencies installed.
    )
    echo.
)

REM Set SECRET_KEY - use persistent key from file or generate new one
set SECRET_KEY_FILE=%SCRIPT_DIR%.secret_key
if "%SECRET_KEY%"=="" (
    if exist "%SECRET_KEY_FILE%" (
        set /p SECRET_KEY=<"%SECRET_KEY_FILE%"
        echo Using persistent SECRET_KEY.
    ) else (
        for /f %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SECRET_KEY=%%i
        echo !SECRET_KEY!>"%SECRET_KEY_FILE%"
        echo Generated and saved new SECRET_KEY.
    )
)

REM Start dashboard
echo Starting dashboard...
cd /d "%DASHBOARD_DIR%"
start "Accuport Dashboard" "%VENV_DIR%\Scripts\python.exe" app.py

timeout /t 3 /nobreak >nul

echo.
echo Dashboard starting...
echo.
echo   URL:  http://localhost:5001
echo   Logs: %DASHBOARD_DIR%\app.log
echo.
echo To stop: Close the "Accuport Dashboard" window
echo.
pause
