#!/usr/bin/env bash
set -e

# 1. Always navigate to script root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================="
echo "  CLASH ROYALE AUTONOMOUS STRATEGY ARENA - LAUNCHER"
echo "======================================================="
echo ""

# 2. Detect Python 3
if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null && python --version 2>&1 | grep -q "Python 3"; then
    PY_CMD="python"
else
    echo "[ERROR] Python 3 is not installed or not found in PATH."
    exit 1
fi

# 3. Setup or verify virtual environment (guards against Windows-copied .venv)
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python" ]; then
    echo "[SETUP] Initializing Python virtual environment in .venv..."
    rm -rf .venv 2>/dev/null || true
    $PY_CMD -m venv .venv
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -r requirements.txt --quiet
    echo "[SETUP] Dependencies installed successfully."
else
    # Check if packages are installed
    if ! .venv/bin/python -c "import fastapi, uvicorn" &>/dev/null; then
        echo "[SETUP] Installing missing packages from requirements.txt..."
        .venv/bin/pip install -r requirements.txt --quiet
    fi
fi

# 4. Check for optional Ollama local LLM service
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    if command -v ollama &>/dev/null; then
        echo "[AI] Starting local Ollama service in background..."
        nohup ollama serve > /tmp/ollama_clash.log 2>&1 &
        sleep 2
    fi
fi

if command -v ollama &>/dev/null && curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    if ! curl -s http://localhost:11434/api/tags 2>&1 | grep -q "qwen2.5:0.5b"; then
        echo "[AI] Pulling model qwen2.5:0.5b..."
        ollama pull qwen2.5:0.5b || true
    fi
    echo "[AI] Local Ollama service connected."
else
    echo "[AI] Ollama not active - using built-in deterministic tactical heuristic engine."
fi

# 5. Clean up any stale process holding port 8000
PORT=8000
if command -v lsof &>/dev/null && lsof -ti:$PORT >/dev/null 2>&1; then
    kill -9 $(lsof -ti:$PORT) 2>/dev/null || true
    sleep 1
elif command -v fuser &>/dev/null && fuser $PORT/tcp >/dev/null 2>&1; then
    fuser -k $PORT/tcp 2>/dev/null || true
    sleep 1
fi

echo ""
echo "Starting server at http://localhost:${PORT}"

# 6. Auto-open browser on Linux desktop or macOS
if [ -n "$DISPLAY" ]; then
    (sleep 1.5 && (xdg-open "http://localhost:${PORT}" 2>/dev/null || sensible-browser "http://localhost:${PORT}" 2>/dev/null || true)) &
elif [ "$(uname -s)" = "Darwin" ]; then
    (sleep 1.5 && open "http://localhost:${PORT}" 2>/dev/null) &
fi

# 7. Start server
exec .venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port $PORT
