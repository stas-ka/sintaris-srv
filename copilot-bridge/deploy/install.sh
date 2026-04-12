#!/usr/bin/env bash
# install.sh — Run ON THE TARGET HOST after files are copied.
# Called automatically by deploy_taristation2.sh via SSH.
set -e

BRIDGE_DIR="$HOME/copilot-bridge"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="copilot-bridge.service"

echo "=== Copilot Bridge install on $(hostname) ==="

# ── Python dependencies ───────────────────────────────────────────────────────
echo "[1/4] Installing Python dependencies..."
pip3 install --user -q -r "$BRIDGE_DIR/requirements.txt"

# ── .env ──────────────────────────────────────────────────────────────────────
if [ ! -f "$BRIDGE_DIR/.env" ]; then
    echo "[2/4] Creating .env from .env.example..."
    cp "$BRIDGE_DIR/.env.example" "$BRIDGE_DIR/.env"
else
    echo "[2/4] .env already exists — skipping"
fi

# ── systemd service ───────────────────────────────────────────────────────────
echo "[3/4] Installing systemd user service..."
mkdir -p "$SERVICE_DIR"
cp "$BRIDGE_DIR/deploy/$SERVICE_NAME" "$SERVICE_DIR/$SERVICE_NAME"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

sleep 2

# ── Verify ────────────────────────────────────────────────────────────────────
echo "[4/4] Verifying bridge health..."
STATUS=$(curl -sf http://127.0.0.1:8765/health 2>/dev/null || echo "unreachable")
echo "Health: $STATUS"

if echo "$STATUS" | grep -q '"status"'; then
    echo "=== Copilot Bridge installed and running OK ==="
else
    echo "!!! Bridge did not start correctly. Check: journalctl --user -u copilot-bridge -n 30"
    exit 1
fi
