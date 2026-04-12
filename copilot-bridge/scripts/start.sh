#!/usr/bin/env bash
# start.sh — Start Copilot Bridge on Linux/macOS
set -e

# Always run from copilot-bridge root (one level above this script)
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "No .env found — copying .env.example to .env"
    cp .env.example .env
fi

echo "Starting Copilot Bridge..."
python3 src/server.py
