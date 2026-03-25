#!/usr/bin/env bash
# =============================================================================
# notify-event.sh — System Event Notifier
# =============================================================================
# Called by systemd services and sleep hooks to send Telegram notifications
# for: startup, shutdown, reboot, sleep, resume, and custom events.
#
# Usage:
#   notify-event.sh startup
#   notify-event.sh shutdown
#   notify-event.sh reboot
#   notify-event.sh "sleep (suspend)"
#   notify-event.sh "resume (from suspend)"
#   notify-event.sh "backup_start"
#   notify-event.sh "custom: my message"
# =============================================================================

set -uo pipefail

CONFIG_FILE="${BACKUP_CONFIG:-/opt/sintaris-backup/.env}"

if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

# Fallback: check monitor config
if [[ -z "${TG_BOT_TOKEN:-}" ]] && [[ -f /opt/sintaris-monitor/.env ]]; then
    source /opt/sintaris-monitor/.env
    TG_BOT_TOKEN="${BOT_TOKEN:-}"
    TG_CHAT_ID="${CHAT_ID:-}"
fi

: "${TG_BOT_TOKEN:?TG_BOT_TOKEN not set}"
: "${TG_CHAT_ID:?TG_CHAT_ID not set}"

HOSTNAME_REAL="$(hostname -f 2>/dev/null || hostname)"
EVENT="${1:-unknown}"
NOW="$(date -u '+%Y-%m-%d %H:%M UTC')"

# ---------------------------------------------------------------------------
# Detect reboot vs shutdown
# ---------------------------------------------------------------------------

detect_shutdown_type() {
    if systemctl list-jobs 2>/dev/null | grep -q "reboot.target\|systemd-reboot"; then
        echo "reboot"
    else
        echo "shutdown"
    fi
}

# ---------------------------------------------------------------------------
# Format message per event type
# ---------------------------------------------------------------------------

case "$EVENT" in
    startup)
        UPTIME="$(uptime -p 2>/dev/null | sed 's/^up //' || echo 'n/a')"
        LOAD="$(uptime 2>/dev/null | awk -F'load average:' '{print $2}' | xargs || echo 'n/a')"
        MSG="🟢 <b>Server started</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}
⏱ Up: ${UPTIME} | Load: ${LOAD}"
        ;;

    shutdown)
        TYPE="$(detect_shutdown_type)"
        if [[ "$TYPE" == "reboot" ]]; then
            MSG="🔄 <b>Server rebooting</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}"
        else
            MSG="🔴 <b>Server shutting down</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}"
        fi
        ;;

    reboot)
        MSG="🔄 <b>Server rebooting</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}"
        ;;

    sleep*|suspend*)
        MSG="😴 <b>Server sleeping</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}
Mode: ${EVENT}"
        ;;

    resume*|wake*)
        MSG="☀️ <b>Server resumed</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}
From: ${EVENT}"
        ;;

    backup_start)
        MSG="💾 <b>Backup started</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}"
        ;;

    backup_done)
        MSG="✅ <b>Backup completed</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}"
        ;;

    backup_failed)
        MSG="❌ <b>Backup FAILED</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}
Check logs on server"
        ;;

    *)
        MSG="ℹ️ <b>System event: ${EVENT}</b> — <code>${HOSTNAME_REAL}</code>
🕐 ${NOW}"
        ;;
esac

# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

curl -sf -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TG_CHAT_ID}" \
    -d parse_mode="HTML" \
    --data-urlencode "text=${MSG}" \
    --max-time 10 \
    > /dev/null 2>&1

exit 0
