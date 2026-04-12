#!/usr/bin/env bash
# =============================================================================
# sintaris-backup.sh — VPS Backup Script
# =============================================================================
# Backs up all services on dev2null.de and dev2null.website.
# Stores archives on a mounted backup volume.
# Sends Telegram notifications at every major step.
#
# Usage:
#   backup.sh                     # full backup of all targets
#   backup.sh --dry-run           # simulate — print actions, no changes
#   backup.sh --target mysql      # backup only MySQL
#   backup.sh --target postgres   # backup only PostgreSQL
#   backup.sh --target docker     # backup Docker configs + volumes
#   backup.sh --target configs    # backup nginx, mail, SSL, system configs
#   backup.sh --target all        # same as default (all targets)
#
# Config: /opt/sintaris-backup/.env
# Deploy: see install.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults + argument parsing
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${BACKUP_CONFIG:-/opt/sintaris-backup/.env}"
LOCKFILE="/tmp/sintaris-backup.lock"
HOSTNAME_REAL="$(hostname -f 2>/dev/null || hostname)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
DATE="$(date -u +%Y-%m-%d)"

DRY_RUN=false
TARGET="all"
BACKUP_EXIT_CODE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)     DRY_RUN=true ;;
        --target)      TARGET="$2"; shift ;;
        --config)      CONFIG_FILE="$2"; shift ;;
        -h|--help)
            grep '^# ' "$0" | head -20 | sed 's/^# //'
            exit 0 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------

if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

# TG credentials required (in dry-run, dummy values are accepted)
: "${TG_BOT_TOKEN:=}"
: "${TG_CHAT_ID:=}"
if ! $DRY_RUN && [[ -z "$TG_BOT_TOKEN" || -z "$TG_CHAT_ID" ]]; then
    echo "ERROR: TG_BOT_TOKEN and TG_CHAT_ID must be set in $CONFIG_FILE" >&2
    exit 1
fi
: "${BACKUP_RETENTION_DAYS:=7}"
: "${BACKUP_MAIL_DATA:=no}"
# Space-separated list of Docker volume names to skip (e.g. large media volumes)
: "${VOLUMES_SKIP:=}"

BACKUP_BASE="${BACKUP_MOUNT}/backups/${HOSTNAME_REAL}"
BACKUP_DIR="${BACKUP_BASE}/${DATE}"
LOG_DIR="${BACKUP_MOUNT}/logs"
# In dry-run mode the log dir may not exist yet — log to /tmp instead
if $DRY_RUN; then
    LOG_FILE="/tmp/sintaris-backup-dryrun-${TIMESTAMP}.log"
else
    LOG_FILE="${LOG_DIR}/${HOSTNAME_REAL}-${TIMESTAMP}.log"
fi
DRY_PREFIX=""
$DRY_RUN && DRY_PREFIX="[DRY-RUN] "

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "${LOG_FILE:-/tmp/sintaris-backup.log}"; }
err() { echo "[$(date -u +%H:%M:%S)] ERROR: $*" | tee -a "${LOG_FILE:-/tmp/sintaris-backup.log}" >&2; }

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

tg() {
    local msg="$1"
    curl -sf -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TG_CHAT_ID}" \
        -d parse_mode="HTML" \
        --data-urlencode "text=${msg}" \
        --max-time 10 \
        > /dev/null 2>&1 || true
}

tg_start()    { tg "💾 <b>${DRY_PREFIX}Backup started</b> — <code>${HOSTNAME_REAL}</code>
📅 ${DATE} | Target: <code>${TARGET}</code>
📂 ${BACKUP_DIR}"; }
tg_section()  { tg "🔄 ${DRY_PREFIX}<b>$1</b> — <code>${HOSTNAME_REAL}</code>"; }
tg_ok()       { tg "✅ ${DRY_PREFIX}<b>$1</b> — <code>${HOSTNAME_REAL}</code>
$2"; }
tg_fail()     { tg "❌ <b>Backup FAILED</b> — <code>${HOSTNAME_REAL}</code>
Step: $1
Error: $2"; }
tg_complete() {
    local size
    size="$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1 || echo "n/a")"
    tg "✅ ${DRY_PREFIX}<b>Backup complete</b> — <code>${HOSTNAME_REAL}</code>
📅 ${DATE} | Size: <b>${size}</b>
📂 ${BACKUP_DIR}
⏱ Elapsed: ${ELAPSED}s"
}

# ---------------------------------------------------------------------------
# Dry-run wrapper
# ---------------------------------------------------------------------------

run() {
    if $DRY_RUN; then
        log "[DRY-RUN] Would run: $*"
    else
        log "Running: $*"
        eval "$@"
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

preflight() {
    log "Pre-flight checks..."

    # Check lock
    if [[ -f "$LOCKFILE" ]]; then
        local pid
        pid="$(cat "$LOCKFILE")"
        if kill -0 "$pid" 2>/dev/null; then
            err "Backup already running (PID $pid). Aborting."
            exit 1
        fi
        rm -f "$LOCKFILE"
    fi
    echo $$ > "$LOCKFILE"

    # Check backup mount
    if ! $DRY_RUN; then
        if [[ ! -d "$BACKUP_MOUNT" ]]; then
            err "Backup mount point $BACKUP_MOUNT does not exist."
            err "Mount the backup storage or set BACKUP_MOUNT in $CONFIG_FILE"
            tg_fail "preflight" "Backup mount ${BACKUP_MOUNT} not found"
            exit 1
        fi
        # Warn if not an actual mount (just a directory)
        if ! mountpoint -q "$BACKUP_MOUNT" 2>/dev/null; then
            log "WARNING: $BACKUP_MOUNT is not a mount point — using local directory"
        fi
        mkdir -p "${BACKUP_DIR}" "${LOG_DIR}"
    else
        log "[DRY-RUN] Would create: ${BACKUP_DIR} and ${LOG_DIR}"
    fi

    log "Pre-flight OK | Host: ${HOSTNAME_REAL} | Mount: ${BACKUP_MOUNT} | Dry-run: ${DRY_RUN}"
}

# ---------------------------------------------------------------------------
# Cleanup on exit
# ---------------------------------------------------------------------------

cleanup() {
    local code=$?
    rm -f "$LOCKFILE"
    if [[ $code -ne 0 ]]; then
        err "Backup script exited with code $code"
        tg_fail "unexpected exit" "Script exited with code $code"
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Backup: MySQL
# ---------------------------------------------------------------------------

backup_mysql() {
    local target="${BACKUP_DIR}/mysql"
    tg_section "MySQL backup"
    log "--- MySQL backup ---"

    # Check mysql is available
    if ! command -v mysqldump &>/dev/null && ! $DRY_RUN; then
        log "mysqldump not found — skipping MySQL backup"
        return 0
    fi

    if $DRY_RUN; then
        log "[DRY-RUN] Would create: ${target}/"
        log "[DRY-RUN] Would run: mysqldump --all-databases > ${target}/all-databases.sql"
        log "[DRY-RUN] Would compress: ${target}/all-databases.sql.gz"
        log "[DRY-RUN] Databases targeted: nextcloud, roundcube, postfixadmin"
        tg_ok "MySQL backup" "Would dump: nextcloud, roundcube, postfixadmin → ${target}/"
        return 0
    fi

    mkdir -p "$target"

    # Dump each DB separately for easier restore
    local dbs
    dbs="$(mysql -N -e "SHOW DATABASES;" 2>/dev/null | grep -vE '^(information_schema|performance_schema|sys|mysql)$' || true)"

    if [[ -z "$dbs" ]]; then
        log "No user databases found (MySQL may require auth — check .env MYSQL_ROOT_PASS)"
        return 0
    fi

    local dumped=()
    for db in $dbs; do
        log "Dumping MySQL database: $db"
        mysqldump \
            --single-transaction \
            --routines \
            --triggers \
            --events \
            "$db" | gzip > "${target}/${db}.sql.gz"
        dumped+=("$db")
    done

    # Also dump full schema
    mysqldump --no-data --all-databases | gzip > "${target}/_schema.sql.gz"

    local size
    size="$(du -sh "$target" | cut -f1)"
    tg_ok "MySQL backup" "Databases: ${dumped[*]}\nSize: ${size}"
    log "MySQL backup done (${size})"
}

# ---------------------------------------------------------------------------
# Backup: PostgreSQL
# ---------------------------------------------------------------------------

backup_postgres() {
    local target="${BACKUP_DIR}/postgresql"
    tg_section "PostgreSQL backup"
    log "--- PostgreSQL backup ---"

    if ! command -v pg_dump &>/dev/null && ! $DRY_RUN; then
        log "pg_dump not found — skipping PostgreSQL backup"
        return 0
    fi

    if $DRY_RUN; then
        log "[DRY-RUN] Would create: ${target}/"
        log "[DRY-RUN] Would run: pg_dumpall (globals) and pg_dump per database"
        log "[DRY-RUN] Databases targeted: n8n, espocrm, postgres (user/role globals)"
        tg_ok "PostgreSQL backup" "Would dump: n8n, espocrm + globals → ${target}/"
        return 0
    fi

    mkdir -p "$target"

    # Dump globals (users, roles, tablespaces)
    sudo -u postgres pg_dumpall --globals-only | gzip > "${target}/_globals.sql.gz"

    # Dump each user database
    local dbs
    dbs="$(sudo -u postgres psql -At -c "SELECT datname FROM pg_database WHERE datistemplate=false AND datname != 'postgres';" 2>/dev/null || true)"

    local dumped=()
    for db in $dbs; do
        log "Dumping PostgreSQL database: $db"
        sudo -u postgres pg_dump \
            --format=custom \
            --compress=9 \
            "$db" > "${target}/${db}.pgdump"
        dumped+=("$db")
    done

    local size
    size="$(du -sh "$target" | cut -f1)"
    tg_ok "PostgreSQL backup" "Databases: ${dumped[*]}\nSize: ${size}"
    log "PostgreSQL backup done (${size})"
}

# ---------------------------------------------------------------------------
# Backup: Docker (compose files + named volumes)
# ---------------------------------------------------------------------------

backup_docker() {
    local target="${BACKUP_DIR}/docker"
    tg_section "Docker backup"
    log "--- Docker backup ---"

    if $DRY_RUN; then
        log "[DRY-RUN] Would archive Docker compose configs from: /opt/*"
        log "[DRY-RUN] Would dump named Docker volumes"
        log "[DRY-RUN] Compose stacks: nextcloud-docker, n8n-docker, espocrm, metabase, pgadmin, bots"
        tg_ok "Docker backup" "Would archive all compose configs + named volumes → ${target}/"
        return 0
    fi

    mkdir -p "${target}/configs" "${target}/volumes"

    # Backup all docker-compose directories in /opt/
    for d in /opt/*/; do
        [[ -f "${d}docker-compose.yml" ]] || [[ -f "${d}docker-compose.yaml" ]] || continue
        local name
        name="$(basename "$d")"
        log "Archiving compose config: $d"
        tar -czf "${target}/configs/${name}.tar.gz" \
            --exclude='*.log' --exclude='*.sock' \
            "$d" 2>/dev/null || log "WARNING: partial archive for $name"
    done

    # Backup named Docker volumes
    if command -v docker &>/dev/null; then
        local volumes
        volumes="$(docker volume ls -q 2>/dev/null || true)"
        for vol in $volumes; do
            # Skip volumes in VOLUMES_SKIP list
            local skip=false
            for skip_vol in $VOLUMES_SKIP; do
                [[ "$vol" == "$skip_vol" ]] && skip=true && break
            done
            if $skip; then
                log "Skipping Docker volume (in VOLUMES_SKIP): $vol"
                continue
            fi
            log "Dumping Docker volume: $vol"
            docker run --rm \
                -v "${vol}:/data:ro" \
                -v "${target}/volumes:/backup" \
                alpine tar -czf "/backup/${vol}.tar.gz" /data 2>/dev/null \
                || log "WARNING: failed to backup volume $vol"
        done
    fi

    local size
    size="$(du -sh "$target" | cut -f1)"
    tg_ok "Docker backup" "Configs + volumes → ${target}/\nSize: ${size}"
    log "Docker backup done (${size})"
}

# ---------------------------------------------------------------------------
# Backup: System configs (nginx, postfix, dovecot, SSL, fail2ban, etc.)
# ---------------------------------------------------------------------------

backup_configs() {
    local target="${BACKUP_DIR}/configs"
    tg_section "Config backup"
    log "--- Config backup ---"

    # Paths to back up (common to all servers)
    local paths=(
        /etc/nginx
        /etc/fail2ban
        /etc/ufw
        /etc/cron.d
        /etc/cron.daily
        /etc/systemd/system
    )

    # Production server (dev2null.de) extras
    if echo "$HOSTNAME_REAL" | grep -q "dev2null.de"; then
        paths+=(
            /etc/postfix
            /etc/dovecot
            /etc/opendkim
            /etc/letsencrypt/renewal
            /etc/mysql/mysql.conf.d
            /etc/php/8.3/fpm
            /etc/roundcube
        )
    fi

    # VPN server (dev2null.website) extras
    if echo "$HOSTNAME_REAL" | grep -q "dev2null.website"; then
        paths+=(
            /etc/haproxy
            /usr/local/x-ui/db
        )
    fi

    if $DRY_RUN; then
        log "[DRY-RUN] Would archive the following paths:"
        for p in "${paths[@]}"; do
            log "  - $p"
        done
        tg_ok "Config backup" "Would archive:\n$(printf '%s\n' "${paths[@]}")"
        return 0
    fi

    mkdir -p "$target"

    for p in "${paths[@]}"; do
        [[ -e "$p" ]] || continue
        local name
        name="$(echo "$p" | tr '/' '_' | sed 's/^_//')"
        log "Archiving: $p → ${target}/${name}.tar.gz"
        tar -czf "${target}/${name}.tar.gz" \
            --exclude='*.sock' --exclude='*/run/*' \
            "$p" 2>/dev/null || log "WARNING: partial archive for $p"
    done

    # SSL certs (live certs only — no private keys in full readable form)
    if [[ -d /etc/letsencrypt/live ]]; then
        log "Archiving SSL certs: /etc/letsencrypt/live"
        tar -czf "${target}/ssl_live.tar.gz" /etc/letsencrypt/live 2>/dev/null || true
    fi

    local size
    size="$(du -sh "$target" | cut -f1)"
    tg_ok "Config backup" "All system configs → ${target}/\nSize: ${size}"
    log "Config backup done (${size})"
}

# ---------------------------------------------------------------------------
# Backup: Mail data (optional — can be large)
# ---------------------------------------------------------------------------

backup_mail() {
    [[ "${BACKUP_MAIL_DATA,,}" == "yes" ]] || {
        log "Mail data backup skipped (BACKUP_MAIL_DATA != yes)"
        return 0
    }

    local target="${BACKUP_DIR}/mail"
    tg_section "Mail data backup"
    log "--- Mail data backup ---"

    if $DRY_RUN; then
        log "[DRY-RUN] Would rsync: /var/mail/vhosts/ → ${target}/"
        local size
        size="$(du -sh /var/mail/vhosts 2>/dev/null | cut -f1 || echo 'unknown')"
        log "[DRY-RUN] Mail data size: ${size}"
        tg_ok "Mail backup" "Would backup /var/mail/vhosts/ (${size}) → ${target}/"
        return 0
    fi

    [[ -d /var/mail/vhosts ]] || { log "No /var/mail/vhosts — skipping"; return 0; }

    mkdir -p "$target"
    rsync -a --delete /var/mail/vhosts/ "${target}/"

    local size
    size="$(du -sh "$target" | cut -f1)"
    tg_ok "Mail backup" "/var/mail/vhosts/ → ${target}/\nSize: ${size}"
    log "Mail backup done (${size})"
}

# ---------------------------------------------------------------------------
# Backup: /opt deploy dirs (non-docker runtime files)
# ---------------------------------------------------------------------------

backup_opt() {
    local target="${BACKUP_DIR}/opt"
    tg_section "Deploy dirs backup (/opt)"
    log "--- /opt backup ---"

    if $DRY_RUN; then
        log "[DRY-RUN] Would archive runtime dirs in /opt/ (excluding large data dirs)"
        tg_ok "/opt backup" "Would archive monitor, bots config, install scripts → ${target}/"
        return 0
    fi

    mkdir -p "$target"

    # Archive lightweight runtime dirs (exclude large data)
    for d in /opt/sintaris-monitor /opt/sintaris-backup; do
        [[ -d "$d" ]] || continue
        local name
        name="$(basename "$d")"
        log "Archiving: $d"
        tar -czf "${target}/${name}.tar.gz" \
            --exclude='*.log' "$d" 2>/dev/null || true
    done

    local size
    size="$(du -sh "$target" 2>/dev/null | cut -f1 || echo 'empty')"
    tg_ok "/opt backup" "Runtime configs → ${target}/\nSize: ${size}"
    log "/opt backup done (${size})"
}

# ---------------------------------------------------------------------------
# Create manifest (checksums)
# ---------------------------------------------------------------------------

create_manifest() {
    $DRY_RUN && { log "[DRY-RUN] Would create: ${BACKUP_DIR}/MANIFEST.sha256"; return; }
    log "Creating manifest..."
    (cd "$BACKUP_DIR" && find . -type f ! -name 'MANIFEST.sha256' -exec sha256sum {} \;) \
        > "${BACKUP_DIR}/MANIFEST.sha256"
    log "Manifest: ${BACKUP_DIR}/MANIFEST.sha256"
}

# ---------------------------------------------------------------------------
# Retention: remove old backups
# ---------------------------------------------------------------------------

rotate_backups() {
    $DRY_RUN && {
        log "[DRY-RUN] Would remove backups older than ${BACKUP_RETENTION_DAYS} days from ${BACKUP_BASE}/"
        return
    }
    log "Rotating backups (keep ${BACKUP_RETENTION_DAYS} days)..."
    find "${BACKUP_BASE}" -maxdepth 1 -type d -mtime "+${BACKUP_RETENTION_DAYS}" \
        -exec rm -rf {} + 2>/dev/null || true
    log "Rotation done"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

START_TIME=$SECONDS

preflight
tg_start

log "===== BACKUP START: ${HOSTNAME_REAL} | ${TIMESTAMP} | dry-run=${DRY_RUN} ====="

case "$TARGET" in
    mysql)    backup_mysql ;;
    postgres) backup_postgres ;;
    docker)   backup_docker ;;
    configs)  backup_configs ;;
    mail)     backup_mail ;;
    all)
        backup_configs
        backup_mysql    || { err "MySQL backup failed"; BACKUP_EXIT_CODE=1; }
        backup_postgres || { err "PostgreSQL backup failed"; BACKUP_EXIT_CODE=1; }
        backup_docker   || { err "Docker backup failed"; BACKUP_EXIT_CODE=1; }
        backup_mail     || { err "Mail backup failed"; BACKUP_EXIT_CODE=1; }
        backup_opt
        ;;
    *)
        err "Unknown target: $TARGET. Use: mysql|postgres|docker|configs|mail|all"
        exit 1 ;;
esac

create_manifest
rotate_backups

# Write last-backup timestamp for monitor.py health check
if ! $DRY_RUN; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%S)" > /opt/sintaris-backup/.last_backup
fi

ELAPSED=$(( SECONDS - START_TIME ))
log "===== BACKUP COMPLETE | Elapsed: ${ELAPSED}s ====="

if [[ $BACKUP_EXIT_CODE -ne 0 ]]; then
    tg "⚠️ <b>Backup completed with errors</b> — <code>${HOSTNAME_REAL}</code>
Some targets failed — check log: ${LOG_FILE}"
else
    tg_complete
fi

# Remove the trap (clean exit — don't send failure notification)
trap - EXIT
rm -f "$LOCKFILE"

exit $BACKUP_EXIT_CODE
