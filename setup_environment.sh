#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up Python virtual environment..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if command -v ollama &>/dev/null; then
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        nohup ollama serve > /tmp/ollama_prep.log 2>&1 &
        sleep 3
    fi
    echo "Downloading model..."
    ollama pull qwen2.5:0.5b
fi

echo "Running tests..."
.venv/bin/python -m unittest tests/test_game.py

echo "Setup complete. You can run ./start_game.sh"
