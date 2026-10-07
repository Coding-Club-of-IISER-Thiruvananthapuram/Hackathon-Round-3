#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found in PATH."
    exit 1
fi

if ! command -v ollama &>/dev/null; then
    if ! command -v zstd &>/dev/null; then
        echo "Installing zstd..."
        export DEBIAN_FRONTEND=noninteractive
        if command -v sudo &>/dev/null; then
            sudo apt-get update -y -qq && sudo apt-get install -y -qq zstd curl
        elif command -v apt-get &>/dev/null; then
            apt-get update -y -qq && apt-get install -y -qq zstd curl
        fi
    fi
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "Starting Ollama service..."
    nohup ollama serve > /tmp/ollama_codespace.log 2>&1 &
    
    retries=15
    while ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do
        sleep 1
        retries=$((retries - 1))
        if [ "$retries" -le 0 ]; then
            echo "Error: Failed to start Ollama."
            cat /tmp/ollama_codespace.log
            exit 1
        fi
    done
fi

if ! curl -s http://localhost:11434/api/tags | grep -q "qwen2.5:0.5b"; then
    echo "Downloading model qwen2.5:0.5b..."
    ollama pull qwen2.5:0.5b
fi

if [ ! -d ".venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -r requirements.txt --quiet
fi

PORT=8000
if command -v lsof &>/dev/null && lsof -ti:$PORT >/dev/null 2>&1; then
    kill -9 $(lsof -ti:$PORT) 2>/dev/null || true
    sleep 1
elif command -v fuser &>/dev/null && fuser $PORT/tcp >/dev/null 2>&1; then
    fuser -k $PORT/tcp 2>/dev/null || true
    sleep 1
fi

echo "Arena starting on port ${PORT}..."
if [ "$CODESPACES" = "true" ] && [ -n "$CODESPACE_NAME" ]; then
    echo "Codespace URL: https://${CODESPACE_NAME}-${PORT}.app.github.dev"
    echo "Note: If required, set Port ${PORT} visibility to 'Public' in the Ports tab."
else
    echo "Local URL: http://localhost:${PORT}"
fi

exec .venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port $PORT
