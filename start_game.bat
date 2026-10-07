@echo off
setlocal enabledelayedexpansion

:: 1. Always navigate to script root directory
cd /d "%~dp0"

echo =======================================================
echo   CLASH ROYALE AUTONOMOUS ARENA - WINDOWS LAUNCHER
echo =======================================================
echo.

:: 2. Detect Python executable (py launcher or python)
set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python 3 is not installed or not found in system PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    echo Ensure "Add python.exe to PATH" is checked during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PY_CMD% --version 2^>^&1') do echo [INFO] Using Python: %%v

:: 3. Setup or verify virtual environment
:: If .venv was copied from Linux (contains .venv\bin instead of .venv\Scripts), recreate it cleanly
if exist ".venv" (
    if not exist ".venv\Scripts\python.exe" (
        echo [SETUP] Rebuilding incompatible non-Windows virtual environment...
        rd /s /q ".venv" >nul 2>&1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Initializing clean virtual environment in .venv...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SETUP] Installing dependencies from requirements.txt...
    .venv\Scripts\python -m pip install --upgrade pip --quiet
    .venv\Scripts\python -m pip install -r requirements.txt --quiet
    echo [SETUP] Dependencies successfully installed.
) else (
    :: Verify critical packages exist
    .venv\Scripts\python -c "import fastapi, uvicorn, pydantic, websockets" >nul 2>&1
    if errorlevel 1 (
        echo [SETUP] Missing dependencies detected. Updating requirements...
        .venv\Scripts\python -m pip install -r requirements.txt --quiet
        echo [SETUP] Dependencies updated.
    )
)

:: 4. Run automated test suite verification
echo [TEST] Running verification test suite...
.venv\Scripts\python -m unittest discover tests -v
if errorlevel 1 (
    echo [WARNING] Some tests encountered issues. Review output above.
) else (
    echo [TEST] All tests passed! Engine and AI triggers verified.
)
echo.

:: 5. Check for optional Ollama local LLM service
curl -s http://localhost:11434/api/tags >nul 2>&1
if not errorlevel 1 (
    echo [AI] Local Ollama service is active. Autonomous LLM commander connected.
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

echo.
echo =======================================================
echo   Arena URL: http://localhost:8000
echo   Press Ctrl+C in this terminal to stop the server
echo =======================================================
echo.

:: 6. Auto-open browser in background after brief delay
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: 7. Launch FastAPI + Uvicorn server
.venv\Scripts\python -m uvicorn server.app:app --host 0.0.0.0 --port 8000

if errorlevel 1 (
    echo.
    echo [NOTICE] Server encountered an error or was stopped.
    pause
)
