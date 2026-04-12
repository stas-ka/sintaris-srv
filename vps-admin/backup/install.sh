#!/usr/bin/env bash
# =============================================================================
# sintaris-backup install.sh — Deploy backup system to a VPS
# =============================================================================
# Copies backup.sh, recover.sh, notify-event.sh, systemd units to the VPS.
# Creates /opt/sintaris-backup/, installs timers, enables sysevent service.
#
# Usage (from local machine):
#   bash install.sh dev2null.de          # production (key auth)
#   bash install.sh dev2null.website     # VPN server (password auth)
#   bash install.sh --dry-run dev2null.de
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(cd "${SCRIPT_DIR}/.." && pwd)/.env"

# Load credentials
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

DRY_RUN=false
TARGET_HOST=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) TARGET_HOST="$arg" ;;
    esac
done

if [[ -z "$TARGET_HOST" ]]; then
    echo "Usage: $0 [--dry-run] <host>"
    echo "  host: dev2null.de | dev2null.website"
    exit 1
fi

# ---------------------------------------------------------------------------
# SSH helper — auto-selects key vs password auth
# ---------------------------------------------------------------------------

ssh_cmd() {
    local host="$1"; shift
    case "$host" in
        *dev2null.de)
            ssh -i "${HOME}/.ssh/id_ed25519" -o StrictHostKeyChecking=no \
                "${VPS_USER:-stas}@${host}" "$@" ;;
        *dev2null.website)
            sshpass -p "${WEB_PASS}" ssh -o StrictHostKeyChecking=no \
                "${WEB_USER:-boh}@${host}" "$@" ;;
        *)
            echo "Unknown host: $host"; exit 1 ;;
    esac
}

scp_cmd() {
    local src="$1" host="$2" dst="$3"
    case "$host" in
        *dev2null.de)
            scp -i "${HOME}/.ssh/id_ed25519" -o StrictHostKeyChecking=no \
                "$src" "${VPS_USER:-stas}@${host}:${dst}" ;;
        *dev2null.website)
            sshpass -p "${WEB_PASS}" scp -o StrictHostKeyChecking=no \
                "$src" "${WEB_USER:-boh}@${host}:${dst}" ;;
    esac
}

sudo_prefix() {
    local host="$1"
    case "$host" in
        *dev2null.de)      echo "sudo" ;;
        *dev2null.website) echo "echo \"\${WEB_PASS}\" | sudo -S" ;;
    esac
}

# ---------------------------------------------------------------------------
# Dry-run wrapper
# ---------------------------------------------------------------------------

log()  { echo "[install] $*"; }
step() { echo ""; echo "=== $* ==="; }

run_remote() {
    if $DRY_RUN; then
        log "[DRY-RUN] Remote: $*"
    else
        ssh_cmd "$TARGET_HOST" "$@"
    fi
}

upload() {
    local src="$1" dst="$2"
    if $DRY_RUN; then
        log "[DRY-RUN] Upload: $src → ${TARGET_HOST}:${dst}"
    else
        scp_cmd "$src" "$TARGET_HOST" "$dst"
    fi
}

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------

step "Pre-flight"
log "Target host: $TARGET_HOST"
log "Dry-run: $DRY_RUN"

for cmd in ssh scp; do
    command -v "$cmd" &>/dev/null || { echo "ERROR: $cmd not found"; exit 1; }
done

if echo "$TARGET_HOST" | grep -q "dev2null.website"; then
    command -v sshpass &>/dev/null || { echo "ERROR: sshpass required for dev2null.website"; exit 1; }
fi

# Test connectivity
log "Testing SSH connection..."
if ! $DRY_RUN; then
    ssh_cmd "$TARGET_HOST" echo "SSH OK" || { echo "SSH connection failed"; exit 1; }
fi

# ---------------------------------------------------------------------------
# Create remote directory structure
# ---------------------------------------------------------------------------

step "Create /opt/sintaris-backup/"
run_remote "sudo mkdir -p /opt/sintaris-backup && sudo chmod 750 /opt/sintaris-backup"

# ---------------------------------------------------------------------------
# Upload scripts
# ---------------------------------------------------------------------------

step "Upload scripts"
SCRIPTS=(backup.sh recover.sh notify-event.sh)
for s in "${SCRIPTS[@]}"; do
    local_path="${SCRIPT_DIR}/${s}"
    [[ -f "$local_path" ]] || { echo "ERROR: $local_path not found"; exit 1; }
    log "Uploading $s..."
    upload "$local_path" "/tmp/${s}"
    run_remote "sudo mv /tmp/${s} /opt/sintaris-backup/${s} && sudo chmod 750 /opt/sintaris-backup/${s}"
done

# ---------------------------------------------------------------------------
# Upload sleep hook
# ---------------------------------------------------------------------------

step "Install sleep hook"
upload "${SCRIPT_DIR}/sintaris-sleep.sh" "/tmp/sintaris-sleep.sh"
run_remote "sudo mv /tmp/sintaris-sleep.sh /lib/systemd/system-sleep/99-sintaris-notify.sh && sudo chmod +x /lib/systemd/system-sleep/99-sintaris-notify.sh"

# ---------------------------------------------------------------------------
# Create .env config on remote (if not present)
# ---------------------------------------------------------------------------

step "Deploy config (.env)"
if ! $DRY_RUN; then
    REMOTE_ENV_EXISTS="$(ssh_cmd "$TARGET_HOST" 'test -f /opt/sintaris-backup/.env && echo yes || echo no')"
    if [[ "$REMOTE_ENV_EXISTS" == "yes" ]]; then
        log "Config /opt/sintaris-backup/.env already exists — skipping (preserving existing config)"
    else
        log "Creating /opt/sintaris-backup/.env from template..."
        # Pull TG_* values from .env
        cat > /tmp/sintaris-backup.env << ENVEOF
# Sintaris Backup Config — generated by install.sh
TG_BOT_TOKEN=${TG_BOT_TOKEN:-}
TG_CHAT_ID=${TG_CHAT_ID:-}
BACKUP_MOUNT=/mnt/sintaris-backup
BACKUP_RETENTION_DAYS=7
BACKUP_MAIL_DATA=no
ENVEOF
        upload "/tmp/sintaris-backup.env" "/tmp/sintaris-backup.env"
        rm -f /tmp/sintaris-backup.env
        run_remote "sudo mv /tmp/sintaris-backup.env /opt/sintaris-backup/.env && sudo chmod 600 /opt/sintaris-backup/.env"
    fi
else
    log "[DRY-RUN] Would create /opt/sintaris-backup/.env with TG credentials"
fi

# ---------------------------------------------------------------------------
# Install systemd units
# ---------------------------------------------------------------------------

step "Install systemd units"
UNITS=(sintaris-backup.service sintaris-backup.timer sintaris-sysevent.service)
for u in "${UNITS[@]}"; do
    local_path="${SCRIPT_DIR}/${u}"
    [[ -f "$local_path" ]] || { echo "WARNING: $local_path not found — skipping"; continue; }
    log "Installing $u..."
    upload "$local_path" "/tmp/${u}"
    run_remote "sudo mv /tmp/${u} /etc/systemd/system/${u} && sudo chmod 644 /etc/systemd/system/${u}"
done

run_remote "sudo systemctl daemon-reload"

# ---------------------------------------------------------------------------
# Enable and start services
# ---------------------------------------------------------------------------

step "Enable services"
run_remote "sudo systemctl enable --now sintaris-backup.timer"
run_remote "sudo systemctl enable --now sintaris-sysevent.service"

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

step "Verify installation"
if ! $DRY_RUN; then
    log "Checking timer..."
    ssh_cmd "$TARGET_HOST" "systemctl status sintaris-backup.timer --no-pager -l" || true
    log "Checking sysevent..."
    ssh_cmd "$TARGET_HOST" "systemctl status sintaris-sysevent.service --no-pager -l" || true
    log "Listing installed files..."
    ssh_cmd "$TARGET_HOST" "ls -la /opt/sintaris-backup/"
    log "Next backup run:"
    ssh_cmd "$TARGET_HOST" "systemctl list-timers sintaris-backup.timer --no-pager" || true
else
    log "[DRY-RUN] Would verify all services and list files"
fi

echo ""
log "✅ Backup system installed on ${TARGET_HOST}"
log "   Scripts: /opt/sintaris-backup/"
log "   Config:  /opt/sintaris-backup/.env"
log "   Timer:   sintaris-backup.timer (daily 02:00 UTC)"
log "   Events:  sintaris-sysevent.service (startup/shutdown)"
log "   Sleep:   /lib/systemd/system-sleep/99-sintaris-notify.sh"
echo ""
log "⚠️  Make sure BACKUP_MOUNT is mounted before the first backup run!"
log "   Edit /opt/sintaris-backup/.env to set BACKUP_MOUNT path."
