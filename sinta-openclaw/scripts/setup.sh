#!/usr/bin/env bash
# setup.sh — Install and configure OpenClaw on a new machine
# Usage: bash setup.sh [--vps-host <host>] [--vps-user <user>]
# Run from inside: ~/projects/sintaris-srv/sinta-openclaw/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_BIN="${HOME}/.local/bin/openclaw"
OPENCLAW_CFG="${HOME}/.openclaw"
SYSTEMD_USER="${HOME}/.config/systemd/user"
MCP_DIR="${HOME}/.local/lib/openclaw-mcp"

# Parse optional args
VPS_HOST="${VPS_HOST:-dev2null.de}"
VPS_USER="${VPS_USER:-stas}"
while [[ $# -gt 0 ]]; do
  case $1 in
    --vps-host) VPS_HOST="$2"; shift 2 ;;
    --vps-user) VPS_USER="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "=== sinta-openclaw setup ==="
echo "VPS: ${VPS_USER}@${VPS_HOST}"
echo ""

# ── Step 1: Verify openclaw is installed ───────────────────────────────────
echo "[1/6] Checking openclaw installation..."
if ! command -v openclaw &>/dev/null && [[ ! -f "$OPENCLAW_BIN" ]]; then
  echo "openclaw not found. Installing via npm..."
  npm install -g openclaw
  echo "openclaw installed."
else
  OPENCLAW_VER=$("$OPENCLAW_BIN" --version 2>/dev/null || openclaw --version 2>/dev/null || echo "unknown")
  echo "openclaw found: $OPENCLAW_VER"
fi

# ── Step 2: Apply openclaw config ──────────────────────────────────────────
echo "[2/6] Configuring openclaw..."
mkdir -p "$OPENCLAW_CFG"

if [[ ! -f "${OPENCLAW_CFG}/openclaw.json" ]]; then
  echo "  No config found. Copying template..."
  cp "${SCRIPT_DIR}/config/openclaw.json.template" "${OPENCLAW_CFG}/openclaw.json"
  chmod 600 "${OPENCLAW_CFG}/openclaw.json"
  echo "  ⚠  Edit ${OPENCLAW_CFG}/openclaw.json — fill in Telegram bot token + gateway auth token."
else
  echo "  Config already exists — checking key settings..."
fi

# Ensure gateway binds to all interfaces (needed for SSH tunnel)
openclaw config set gateway.bind lan 2>/dev/null && echo "  gateway.bind = lan" || true
openclaw config set channels.telegram.groupPolicy open 2>/dev/null && echo "  groupPolicy = open" || true

# ── Step 3: Install custom skills ──────────────────────────────────────────
echo "[3/6] Installing custom skills..."
mkdir -p "${OPENCLAW_CFG}/skills"

for skill_dir in "${SCRIPT_DIR}/skills"/skill-*; do
  skill_name=$(basename "$skill_dir")
  target="${OPENCLAW_CFG}/skills/${skill_name}"
  if [[ -L "$target" ]]; then
    echo "  $skill_name — symlink already exists"
  elif [[ -d "$target" ]]; then
    echo "  $skill_name — directory exists (not a symlink, skipping)"
  else
    ln -s "$skill_dir" "$target"
    echo "  $skill_name — symlinked"
  fi
done

# Remind about api-keys.txt
if [[ ! -f "${SCRIPT_DIR}/skills/skill-n8n/api-keys.txt" ]]; then
  echo ""
  echo "  ⚠  Missing: skills/skill-n8n/api-keys.txt"
  echo "     Create it with your N8N API key (see api-keys.txt.example)"
fi

# ── Step 4: Install systemd services ───────────────────────────────────────
echo "[4/6] Installing systemd services..."
mkdir -p "$SYSTEMD_USER"

for svc in openclaw-gateway.service openclaw-tunnel.service; do
  src="${SCRIPT_DIR}/systemd/${svc}"
  dst="${SYSTEMD_USER}/${svc}"
  if [[ -f "$dst" ]]; then
    echo "  $svc — already installed"
  else
    cp "$src" "$dst"
    echo "  $svc — installed"
  fi
done

systemctl --user daemon-reload
systemctl --user enable --now openclaw-gateway.service
echo "  openclaw-gateway.service enabled and started"

# Tunnel service needs VPS SSH key
if ssh -o BatchMode=yes -o ConnectTimeout=5 "${VPS_USER}@${VPS_HOST}" true 2>/dev/null; then
  systemctl --user enable --now openclaw-tunnel.service
  echo "  openclaw-tunnel.service enabled and started"
else
  echo "  ⚠  SSH to ${VPS_USER}@${VPS_HOST} not available — tunnel service NOT started"
  echo "     Run: systemctl --user start openclaw-tunnel.service  (after SSH key is configured)"
fi

# ── Step 5: Install MCP server ─────────────────────────────────────────────
echo "[5/6] Installing MCP server..."
mkdir -p "$MCP_DIR"
cp "${SCRIPT_DIR}/mcp/server.mjs" "$MCP_DIR/"
cp "${SCRIPT_DIR}/mcp/package.json" "$MCP_DIR/"
cp "${SCRIPT_DIR}/mcp/package-lock.json" "$MCP_DIR/" 2>/dev/null || true
(cd "$MCP_DIR" && npm install --silent)
echo "  MCP server installed at $MCP_DIR"

# Check Copilot CLI MCP config
COPILOT_MCP="${HOME}/.config/github-copilot/mcp.json"
if [[ -f "$COPILOT_MCP" ]]; then
  if grep -q "openclaw-mcp" "$COPILOT_MCP"; then
    echo "  Copilot MCP config already references openclaw-mcp"
  else
    echo "  ⚠  Add openclaw-mcp to $COPILOT_MCP (see docs/install.md)"
  fi
else
  echo "  Creating Copilot MCP config..."
  mkdir -p "$(dirname "$COPILOT_MCP")"
  cat > "$COPILOT_MCP" << MCPEOF
{
  "servers": {
    "openclaw": {
      "command": "node",
      "args": ["${MCP_DIR}/server.mjs"]
    }
  }
}
MCPEOF
  echo "  Copilot MCP config created at $COPILOT_MCP"
fi

# ── Step 6: Verify ─────────────────────────────────────────────────────────
echo "[6/6] Verifying..."
sleep 2

if curl -sf http://localhost:18789/ >/dev/null 2>&1; then
  echo "  ✓ OpenClaw gateway responding at http://localhost:18789"
else
  echo "  ✗ Gateway not responding — check: systemctl --user status openclaw-gateway.service"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit ~/.openclaw/openclaw.json — add Telegram bot token + gateway auth token"
echo "  2. Add N8N API key to: ${SCRIPT_DIR}/skills/skill-n8n/api-keys.txt"
echo "  3. Web UI: https://agents.sintaris.net/openclaw/ (once tunnel is active)"
echo "  4. Check status: systemctl --user status openclaw-gateway openclaw-tunnel"
