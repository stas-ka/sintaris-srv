#!/usr/bin/env bash
# =============================================================================
# sintaris-recover.sh — VPS Recovery Script
# =============================================================================
# Lists and restores backups created by backup.sh.
#
# Usage:
#   recover.sh list                         # list all available backups
#   recover.sh restore --date 2026-03-25    # restore everything from a date
#   recover.sh restore --date 2026-03-25 --target mysql
#   recover.sh restore --date 2026-03-25 --target postgres
#   recover.sh restore --date 2026-03-25 --target configs
#   recover.sh restore --date 2026-03-25 --target docker
#   recover.sh restore --date 2026-03-25 --dry-run
# =============================================================================

set -euo pipefail

CONFIG_FILE="${BACKUP_CONFIG:-/opt/sintaris-backup/.env}"

# Parse DRY_RUN early (needed for TG credential check)
DRY_RUN=false
for arg in "$@"; do [[ "$arg" == "--dry-run" ]] && DRY_RUN=true; done

if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

: "${TG_BOT_TOKEN:=}"
: "${TG_CHAT_ID:=}"
if ! $DRY_RUN && [[ -z "$TG_BOT_TOKEN" || -z "$TG_CHAT_ID" ]]; then
    echo "ERROR: TG_BOT_TOKEN and TG_CHAT_ID must be set" >&2
    exit 1
fi
: "${BACKUP_MOUNT:=/mnt/sintaris-backup}"

HOSTNAME_REAL="$(hostname -f 2>/dev/null || hostname)"
BACKUP_BASE="${BACKUP_MOUNT}/backups/${HOSTNAME_REAL}"

TARGET="all"
RESTORE_DATE=""
COMMAND="${1:-list}"
shift || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --target)  TARGET="$2"; shift ;;
        --date)    RESTORE_DATE="$2"; shift ;;
        -h|--help) grep '^# ' "$0" | sed 's/^# //'; exit 0 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
    shift
done

DRY_PREFIX=""
$DRY_RUN && DRY_PREFIX="[DRY-RUN] "

# ---------------------------------------------------------------------------
# Logging + Telegram
# ---------------------------------------------------------------------------

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
err() { echo "[$(date -u +%H:%M:%S)] ERROR: $*" >&2; }

tg() {
    curl -sf -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TG_CHAT_ID}" \
        -d parse_mode="HTML" \
        --data-urlencode "text=$1" \
        --max-time 10 > /dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# List available backups
# ---------------------------------------------------------------------------

cmd_list() {
    if [[ ! -d "$BACKUP_BASE" ]]; then
        echo "No backups found at: $BACKUP_BASE"
        exit 0
    fi

    echo "Available backups for ${HOSTNAME_REAL}:"
    echo "======================================="
    for d in "${BACKUP_BASE}"/*/; do
        [[ -d "$d" ]] || continue
        local date
        date="$(basename "$d")"
        local size
        size="$(du -sh "$d" 2>/dev/null | cut -f1)"
        local targets=""
        [[ -d "${d}mysql" ]]      && targets+=" mysql"
        [[ -d "${d}postgresql" ]] && targets+=" postgres"
        [[ -d "${d}docker" ]]     && targets+=" docker"
        [[ -d "${d}configs" ]]    && targets+=" configs"
        [[ -d "${d}mail" ]]       && targets+=" mail"
        [[ -d "${d}opt" ]]        && targets+=" opt"
        [[ -f "${d}MANIFEST.sha256" ]] && local manifest="✓ manifest" || local manifest="✗ no manifest"

        printf "  📦 %-12s  %6s  [%s]  %s\n" "$date" "$size" "${targets# }" "$manifest"
    done
}

# ---------------------------------------------------------------------------
# Verify manifest
# ---------------------------------------------------------------------------

verify_manifest() {
    local backup_dir="$1"
    local manifest="${backup_dir}/MANIFEST.sha256"

    if [[ ! -f "$manifest" ]]; then
        log "WARNING: No manifest file found — cannot verify integrity"
        return 0
    fi

    log "Verifying integrity..."
    if (cd "$backup_dir" && sha256sum --check MANIFEST.sha256 --quiet 2>&1); then
        log "✓ Integrity check passed"
    else
        err "✗ Integrity check FAILED — backup may be corrupted"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Restore: MySQL
# ---------------------------------------------------------------------------

restore_mysql() {
    local src="${RESTORE_DIR}/mysql"
    [[ -d "$src" ]] || { log "No MySQL backup at ${src}"; return 0; }

    log "--- Restore MySQL ---"
    if $DRY_RUN; then
        log "[DRY-RUN] Would restore MySQL databases from: $src"
        for f in "${src}"/*.sql.gz; do
            [[ -f "$f" ]] || continue
            local db
            db="$(basename "${f%.sql.gz}")"
            [[ "$db" == _* ]] && continue
            log "[DRY-RUN]   Would restore DB: $db"
        done
        return 0
    fi

    for f in "${src}"/*.sql.gz; do
        [[ -f "$f" ]] || continue
        local db
        db="$(basename "${f%.sql.gz}")"
        [[ "$db" == _* ]] && continue
        log "Restoring MySQL DB: $db"
        mysql -e "CREATE DATABASE IF NOT EXISTS \`${db}\`;"
        zcat "$f" | mysql "$db"
        log "✓ Restored: $db"
    done
}

# ---------------------------------------------------------------------------
# Restore: PostgreSQL
# ---------------------------------------------------------------------------

restore_postgres() {
    local src="${RESTORE_DIR}/postgresql"
    [[ -d "$src" ]] || { log "No PostgreSQL backup at ${src}"; return 0; }

    log "--- Restore PostgreSQL ---"
    if $DRY_RUN; then
        log "[DRY-RUN] Would restore PostgreSQL databases from: $src"
        for f in "${src}"/*.pgdump; do
            [[ -f "$f" ]] || continue
            local db
            db="$(basename "${f%.pgdump}")"
            log "[DRY-RUN]   Would restore DB: $db"
        done
        return 0
    fi

    # Restore globals first
    if [[ -f "${src}/_globals.sql.gz" ]]; then
        log "Restoring PostgreSQL globals (roles/users)..."
        zcat "${src}/_globals.sql.gz" | sudo -u postgres psql --quiet || true
    fi

    # Restore each database
    for f in "${src}"/*.pgdump; do
        [[ -f "$f" ]] || continue
        local db
        db="$(basename "${f%.pgdump}")"
        log "Restoring PostgreSQL DB: $db"
        sudo -u postgres createdb "$db" 2>/dev/null || log "DB $db already exists"
        sudo -u postgres pg_restore \
            --dbname="$db" \
            --clean \
            --if-exists \
            --no-owner \
            "$f" 2>/dev/null || log "WARNING: pg_restore reported issues for $db"
        log "✓ Restored: $db"
    done
}

# ---------------------------------------------------------------------------
# Restore: configs
# ---------------------------------------------------------------------------

restore_configs() {
    local src="${RESTORE_DIR}/configs"
    [[ -d "$src" ]] || { log "No config backup at ${src}"; return 0; }

    log "--- Restore configs ---"
    if $DRY_RUN; then
        log "[DRY-RUN] Would restore config archives from: $src"
        for f in "${src}"/*.tar.gz; do
            [[ -f "$f" ]] || continue
            log "[DRY-RUN]   Would extract: $(basename "$f")"
        done
        return 0
    fi

    for f in "${src}"/*.tar.gz; do
        [[ -f "$f" ]] || continue
        log "Extracting: $(basename "$f") → /"
        tar -xzf "$f" -C / 2>/dev/null || log "WARNING: issues extracting $(basename "$f")"
    done
    log "Reloading affected services..."
    systemctl daemon-reload
    systemctl reload nginx 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Restore: Docker configs
# ---------------------------------------------------------------------------

restore_docker() {
    local src="${RESTORE_DIR}/docker"
    [[ -d "$src" ]] || { log "No Docker backup at ${src}"; return 0; }

    log "--- Restore Docker configs ---"
    if $DRY_RUN; then
        log "[DRY-RUN] Would restore Docker compose configs to /opt/ from: $src"
        return 0
    fi

    for f in "${src}/configs/"*.tar.gz; do
        [[ -f "$f" ]] || continue
        log "Extracting: $(basename "$f") → /"
        tar -xzf "$f" -C / 2>/dev/null || log "WARNING: issues extracting $(basename "$f")"
    done
    log "Docker configs restored. Run 'docker compose up -d' in each /opt/* directory."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

case "$COMMAND" in
    list)
        cmd_list
        ;;

    restore)
        [[ -n "$RESTORE_DATE" ]] || { err "--date is required for restore"; exit 1; }
        RESTORE_DIR="${BACKUP_BASE}/${RESTORE_DATE}"

        if [[ ! -d "$RESTORE_DIR" ]] && ! $DRY_RUN; then
            err "Backup not found: $RESTORE_DIR"
            echo ""
            cmd_list
            exit 1
        fi

        log "===== RESTORE START: ${HOSTNAME_REAL} | date=${RESTORE_DATE} | target=${TARGET} ====="
        tg "🔄 ${DRY_PREFIX}<b>Recovery started</b> — <code>${HOSTNAME_REAL}</code>
📅 Restoring from: <b>${RESTORE_DATE}</b>
Target: <code>${TARGET}</code>"

        ! $DRY_RUN && verify_manifest "$RESTORE_DIR" || true

        case "$TARGET" in
            mysql)    restore_mysql ;;
            postgres) restore_postgres ;;
            configs)  restore_configs ;;
            docker)   restore_docker ;;
            all)
                restore_configs
                restore_mysql
                restore_postgres
                restore_docker
                ;;
            *) err "Unknown target: $TARGET"; exit 1 ;;
        esac

        log "===== RESTORE COMPLETE ====="
        tg "✅ ${DRY_PREFIX}<b>Recovery complete</b> — <code>${HOSTNAME_REAL}</code>
📅 Restored from: <b>${RESTORE_DATE}</b>
Target: <code>${TARGET}</code>"
        ;;

    *)
        echo "Usage: $0 {list|restore} [options]"
        echo "Run '$0 --help' for details."
        exit 1 ;;
esac
