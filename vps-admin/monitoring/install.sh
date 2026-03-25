#!/usr/bin/env bash
# Sintaris Monitor — installer
# Run as root on the target VPS:
#   sudo bash install.sh
#
# Before running: create /opt/sintaris-monitor/.env with BOT_TOKEN, CHAT_ID, HOSTNAME_LABEL

set -euo pipefail

INSTALL_DIR="/opt/sintaris-monitor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Sintaris Monitor installer ==="

# Create install dir
mkdir -p "$INSTALL_DIR"

# Copy monitor script
cp "$SCRIPT_DIR/monitor.py" "$INSTALL_DIR/monitor.py"
chmod +x "$INSTALL_DIR/monitor.py"

# Create .env if missing
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$SCRIPT_DIR/monitor.env.example" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    echo ""
    echo "⚠️  Created $INSTALL_DIR/.env — fill in BOT_TOKEN, CHAT_ID, HOSTNAME_LABEL before starting!"
    echo ""
fi

# Install systemd units
cp "$SCRIPT_DIR/sintaris-monitor.service"       /etc/systemd/system/
cp "$SCRIPT_DIR/sintaris-monitor.timer"         /etc/systemd/system/
cp "$SCRIPT_DIR/sintaris-monitor-daily.service" /etc/systemd/system/
cp "$SCRIPT_DIR/sintaris-monitor-daily.timer"   /etc/systemd/system/

# Enable and start
systemctl daemon-reload
systemctl enable --now sintaris-monitor.timer
systemctl enable --now sintaris-monitor-daily.timer

echo "=== Done ==="
echo "Test with: python3 $INSTALL_DIR/monitor.py test"
echo "Status:    systemctl list-timers sintaris-monitor*"
