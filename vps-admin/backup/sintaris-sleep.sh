#!/usr/bin/env bash
# =============================================================================
# sintaris-sleep.sh — Sleep / Resume Notifier
# =============================================================================
# Deployed to: /lib/systemd/system-sleep/99-sintaris-notify.sh
# Called automatically by systemd before and after sleep/hibernate.
#
# Arguments passed by systemd:
#   $1 = pre | post
#   $2 = suspend | hibernate | hybrid-sleep | suspend-then-hibernate
# =============================================================================

NOTIFY="/opt/sintaris-backup/notify-event.sh"
[[ -x "$NOTIFY" ]] || exit 0

case "$1" in
    pre)
        "$NOTIFY" "sleep (${2})"
        ;;
    post)
        "$NOTIFY" "resume (from ${2})"
        ;;
esac

exit 0
