#!/usr/bin/env bash
# deploy_taristation2.sh — Deploy Copilot Bridge to TariStation2 from Windows dev machine.
# Run from the sintaris-srv/copilot-bridge directory or project root.
# Reads credentials from sintaris-openclaw/.env (or exports below).
#
# Requires PuTTY tools (plink, pscp) in PATH.
# Usage:  bash deploy/deploy_taristation2.sh [--gh-token <token>]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Load credentials from sintaris-openclaw/.env ──────────────────────────────
OPENCLAW_DIR="$(cd "$BRIDGE_DIR/../../sintaris-openclaw" 2>/dev/null || echo "")"
ENV_FILE="$OPENCLAW_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    set -a; source "$ENV_FILE"; set +a
fi

TARGET_IP="${ENG_TARGETHOST_IP:-192.168.178.27}"
TARGET_USER="${ENG_HOSTUSER:-stas}"
TARGET_PWD="${ENG_HOSTPWD:-buerger}"
TARGET_KEY="${ENG_HOSTKEY:-SHA256:2Psz9uCmafYyM25q7XAjmdwIV1YhBzX6KfSzn/zqmhE}"
REMOTE_DIR="/home/$TARGET_USER/copilot-bridge"

# ── Optional GH_TOKEN override ────────────────────────────────────────────────
GH_TOKEN_ARG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gh-token) GH_TOKEN_ARG="$2"; shift 2 ;;
        *) shift ;;
    esac
done

PLINK="plink -pw \"$TARGET_PWD\" -hostkey \"$TARGET_KEY\" -batch $TARGET_USER@$TARGET_IP"
PSCP="pscp  -pw \"$TARGET_PWD\" -hostkey \"$TARGET_KEY\""

echo "=== Deploying Copilot Bridge → $TARGET_USER@$TARGET_IP:$REMOTE_DIR ==="

# ── Create remote directory structure ────────────────────────────────────────
eval $PLINK "mkdir -p $REMOTE_DIR/src $REMOTE_DIR/deploy $REMOTE_DIR/scripts $REMOTE_DIR/doc"

# ── Upload files ──────────────────────────────────────────────────────────────
echo "[1/4] Uploading source files..."
eval $PSCP "$BRIDGE_DIR/src/server.py"        "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/src/"
eval $PSCP "$BRIDGE_DIR/src/copilot_client.py" "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/src/"
eval $PSCP "$BRIDGE_DIR/src/config.py"         "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/src/"

echo "[2/4] Uploading config and scripts..."
eval $PSCP "$BRIDGE_DIR/requirements.txt"     "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/"
eval $PSCP "$BRIDGE_DIR/.env.example"         "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/"
eval $PSCP "$BRIDGE_DIR/scripts/start.sh"     "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/scripts/"
eval $PSCP "$BRIDGE_DIR/deploy/copilot-bridge.service" "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/deploy/"
eval $PSCP "$BRIDGE_DIR/deploy/install.sh"    "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/deploy/"
eval $PSCP "$BRIDGE_DIR/doc/architecture.md"  "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/doc/" 2>/dev/null || true
eval $PSCP "$BRIDGE_DIR/doc/deployment.md"    "$TARGET_USER@$TARGET_IP:$REMOTE_DIR/doc/" 2>/dev/null || true

# ── Write .env with GH_TOKEN on remote ───────────────────────────────────────
echo "[3/4] Configuring .env on remote..."
LOCAL_GH_TOKEN="${GH_TOKEN_ARG:-$(gh auth token 2>/dev/null || echo "")}"
if [ -n "$LOCAL_GH_TOKEN" ]; then
    eval $PLINK "
        if [ ! -f $REMOTE_DIR/.env ]; then
            cp $REMOTE_DIR/.env.example $REMOTE_DIR/.env
        fi
        # Set GH_TOKEN in .env
        if grep -q '^GH_TOKEN=' $REMOTE_DIR/.env; then
            sed -i 's|^GH_TOKEN=.*|GH_TOKEN=$LOCAL_GH_TOKEN|' $REMOTE_DIR/.env
        else
            echo 'GH_TOKEN=$LOCAL_GH_TOKEN' >> $REMOTE_DIR/.env
        fi
        # Ensure no bind to 0.0.0.0 (localhost only)
        grep -q '^COPILOT_BRIDGE_HOST=' $REMOTE_DIR/.env || echo 'COPILOT_BRIDGE_HOST=127.0.0.1' >> $REMOTE_DIR/.env
    "
    echo "    GH_TOKEN set in remote .env"
else
    echo "    WARNING: no GH_TOKEN found — set it manually in $REMOTE_DIR/.env on the target"
fi

# ── Run install.sh on remote ──────────────────────────────────────────────────
echo "[4/4] Running install.sh on remote..."
eval $PLINK "chmod +x $REMOTE_DIR/deploy/install.sh $REMOTE_DIR/scripts/start.sh && bash $REMOTE_DIR/deploy/install.sh"

echo ""
echo "=== Deployment complete ==="
echo "Bridge URL: http://$TARGET_IP:8765 (local to target; tunnel to access remotely)"
echo "SSH to verify: plink -pw '$TARGET_PWD' -hostkey '$TARGET_KEY' -batch $TARGET_USER@$TARGET_IP 'curl -s http://127.0.0.1:8765/health'"
