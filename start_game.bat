@echo off
setlocal enabledelayedexpansion

:: 1. Always navigate to script root directory
cd /d "%~dp0"

echo =======================================================
echo   CLASH ROYALE AUTONOMOUS STRATEGY ARENA - LAUNCHER
echo =======================================================
echo.

:: 2. Detect Python executable (python or py launcher)
set "PY_CMD=python"
python --version >nul 2>&1
if errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py -3"
    ) else (
        echo [ERROR] Python 3 is not installed or not found in system PATH.
        echo Please install Python 3.10+ from https://www.python.org/
        echo Make sure to check "Add python.exe to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
)

:: 3. Setup or verify virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Initializing Python virtual environment in .venv...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SETUP] Installing required dependencies...
    .venv\Scripts\python -m pip install --upgrade pip --quiet
    .venv\Scripts\python -m pip install -r requirements.txt --quiet
    echo [SETUP] Dependencies successfully installed.
) else (
    :: Verify critical packages exist
    .venv\Scripts\python -c "import fastapi, uvicorn" >nul 2>&1
    if errorlevel 1 (
        echo [SETUP] Missing dependencies detected. Installing requirements...
        .venv\Scripts\python -m pip install -r requirements.txt
    )
)

:: 4. Check for optional Ollama local LLM service
curl -s http://localhost:11434/api/tags >nul 2>&1
if not errorlevel 1 (
    echo [AI] Local Ollama service is active. Autonomous LLM commander enabled.
) else (
    where ollama >nul 2>&1
    if not errorlevel 1 (
        echo [AI] Starting local Ollama service in background...
        start /b ollama serve >nul 2>&1
        timeout /t 2 /nobreak >nul
    ) else (
        echo [AI] Ollama not found - using built-in deterministic tactical heuristic engine.
    )
)

:: 5. Open browser smoothly in background after brief delay
echo.
echo Starting Clash Royale Battle Arena on http://localhost:8000
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: 6. Launch FastAPI + Uvicorn server
.venv\Scripts\python -m uvicorn server.app:app --host 0.0.0.0 --port 8000

if errorlevel 1 (
    echo.
    echo [NOTICE] Server terminated or encountered an error.
    pause
)
