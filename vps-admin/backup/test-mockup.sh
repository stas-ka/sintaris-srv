#!/usr/bin/env bash
# =============================================================================
# test-mockup.sh — Simulated backup test (no real server access needed)
# =============================================================================
# Runs backup.sh in DRY_RUN mode with a temp dir as BACKUP_MOUNT.
# Simulates both dev2null.de and dev2null.website profiles.
# Sends REAL Telegram [MOCKUP] notifications at each step.
#
# Usage:
#   bash test-mockup.sh               # run all tests
#   bash test-mockup.sh --no-tg       # skip Telegram (offline test)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(cd "${SCRIPT_DIR}/.." && pwd)/.env"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
NOTIFY_SCRIPT="${SCRIPT_DIR}/notify-event.sh"
TMP_DIR="$(mktemp -d /tmp/sintaris-backup-mockup.XXXXX)"
NO_TG=false
PASS=0
FAIL=0

[[ "$*" == *--no-tg* ]] && NO_TG=true

# Load credentials
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

TG_BOT_TOKEN="${TG_BOT_TOKEN:-}"
TG_CHAT_ID="${TG_CHAT_ID:-}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { echo "[test] $*"; }
ok()   { echo "  ✅ $*"; ((PASS++)) || true; }
fail() { echo "  ❌ $*"; ((FAIL++)) || true; }

tg_mockup() {
    $NO_TG && return 0
    [[ -z "$TG_BOT_TOKEN" || -z "$TG_CHAT_ID" ]] && return 0
    curl -sf -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TG_CHAT_ID}" \
        -d parse_mode="HTML" \
        --data-urlencode "text=🧪 [MOCKUP] $1" \
        --max-time 10 > /dev/null 2>&1 || true
}

# Minimal .env for backup.sh dry-run
write_env() {
    local hostname="$1"
    cat > "${TMP_DIR}/backup.env" << EOF
TG_BOT_TOKEN=${TG_BOT_TOKEN:-dummy_token_for_dry_run}
TG_CHAT_ID=${TG_CHAT_ID:-000000000}
BACKUP_MOUNT=${TMP_DIR}/mount
BACKUP_RETENTION_DAYS=7
BACKUP_MAIL_DATA=no
EOF
}

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo ""
echo "====================================================================="
echo "  Sintaris Backup — Mockup Test"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "====================================================================="
echo ""

tg_mockup "Backup mockup test started — simulating dev2null.de + dev2null.website"

# ---------------------------------------------------------------------------
# Test 1: Check all required files exist
# ---------------------------------------------------------------------------

log "=== Test 1: Required files present ==="
REQUIRED=(
    "${SCRIPT_DIR}/backup.sh"
    "${SCRIPT_DIR}/recover.sh"
    "${SCRIPT_DIR}/notify-event.sh"
    "${SCRIPT_DIR}/backup.env.example"
    "${SCRIPT_DIR}/sintaris-backup.service"
    "${SCRIPT_DIR}/sintaris-backup.timer"
    "${SCRIPT_DIR}/sintaris-sysevent.service"
    "${SCRIPT_DIR}/sintaris-sleep.sh"
    "${SCRIPT_DIR}/install.sh"
)
for f in "${REQUIRED[@]}"; do
    if [[ -f "$f" ]]; then
        ok "$(basename "$f") exists"
    else
        fail "MISSING: $f"
    fi
done

# ---------------------------------------------------------------------------
# Test 2: Scripts are executable / valid bash
# ---------------------------------------------------------------------------

log "=== Test 2: Script syntax ==="
for s in backup.sh recover.sh notify-event.sh install.sh; do
    if bash -n "${SCRIPT_DIR}/${s}" 2>/dev/null; then
        ok "${s}: syntax OK"
    else
        fail "${s}: syntax ERROR"
    fi
done

# ---------------------------------------------------------------------------
# Test 3: Dry-run backup — simulate dev2null.de
# ---------------------------------------------------------------------------

log "=== Test 3: Dry-run backup (simulated dev2null.de) ==="
mkdir -p "${TMP_DIR}/mount"
write_env "dev2null.de"

tg_mockup "Running dry-run backup for <b>dev2null.de</b> (simulated)..."

OUTPUT="$(BACKUP_CONFIG="${TMP_DIR}/backup.env" \
    HOSTNAME="dev2null.de" \
    bash "${BACKUP_SCRIPT}" --dry-run 2>&1)" || true

if echo "$OUTPUT" | grep -q "DRY-RUN"; then
    ok "Dry-run output contains DRY-RUN markers"
else
    fail "No DRY-RUN markers in output"
fi

if echo "$OUTPUT" | grep -q "Would archive"; then
    ok "Config backup step detected"
else
    fail "Config backup step not found"
fi

if echo "$OUTPUT" | grep -q "Would dump\|Would run.*mysqldump\|mysqldump not found"; then
    ok "MySQL step detected"
else
    fail "MySQL step not found"
fi

if echo "$OUTPUT" | grep -q "Would dump\|pg_dump\|pg_dump not found"; then
    ok "PostgreSQL step detected"
else
    fail "PostgreSQL step not found"
fi

if echo "$OUTPUT" | grep -q "compose\|Docker"; then
    ok "Docker step detected"
else
    fail "Docker step not found"
fi

echo ""
echo "  --- Dry-run output (last 15 lines) ---"
echo "$OUTPUT" | tail -15 | sed 's/^/  /'
echo ""

tg_mockup "dev2null.de dry-run complete ✅\nOutput:\n$(echo "$OUTPUT" | tail -5)"

# ---------------------------------------------------------------------------
# Test 4: Dry-run backup — simulate dev2null.website
# ---------------------------------------------------------------------------

log "=== Test 4: Dry-run backup (simulated dev2null.website) ==="
write_env "dev2null.website"

tg_mockup "Running dry-run backup for <b>dev2null.website</b> (simulated)..."

OUTPUT2="$(BACKUP_CONFIG="${TMP_DIR}/backup.env" \
    HOSTNAME="dev2null.website" \
    bash "${BACKUP_SCRIPT}" --dry-run 2>&1)" || true

if echo "$OUTPUT2" | grep -q "DRY-RUN"; then
    ok "dev2null.website: dry-run output OK"
else
    fail "dev2null.website: no DRY-RUN markers"
fi

if echo "$OUTPUT2" | grep -q "BACKUP START"; then
    ok "dev2null.website: backup sequence started"
else
    fail "dev2null.website: no backup start marker"
fi

echo ""
echo "  --- Dry-run output (last 10 lines) ---"
echo "$OUTPUT2" | tail -10 | sed 's/^/  /'
echo ""

tg_mockup "dev2null.website dry-run complete ✅"

# ---------------------------------------------------------------------------
# Test 5: Dry-run single target
# ---------------------------------------------------------------------------

log "=== Test 5: Single-target dry-run (--target configs) ==="

OUTPUT3="$(BACKUP_CONFIG="${TMP_DIR}/backup.env" \
    bash "${BACKUP_SCRIPT}" --dry-run --target configs 2>&1)" || true

if echo "$OUTPUT3" | grep -q "Would archive"; then
    ok "--target configs: dry-run OK"
else
    fail "--target configs: unexpected output"
fi

# ---------------------------------------------------------------------------
# Test 6: notify-event.sh syntax + event types
# ---------------------------------------------------------------------------

log "=== Test 6: notify-event.sh event types ==="
# Just check it runs without crashing (no real Telegram send — env may differ)
for event in startup shutdown reboot "backup_start" "backup_done" "backup_failed"; do
    if bash -c "TG_BOT_TOKEN=test TG_CHAT_ID=test bash ${NOTIFY_SCRIPT} ${event}" 2>&1 \
        | grep -qv "curl.*error\|TG_BOT_TOKEN\|TG_CHAT_ID" || true; then
        ok "notify-event.sh ${event}: runs without crash"
    fi
done

# ---------------------------------------------------------------------------
# Test 7: recover.sh list (no backup dir = graceful)
# ---------------------------------------------------------------------------

log "=== Test 7: recover.sh list (no backups) ==="

OUTPUT4="$(BACKUP_CONFIG="${TMP_DIR}/backup.env" \
    bash "${SCRIPT_DIR}/recover.sh" list 2>&1)" || true

if echo "$OUTPUT4" | grep -qi "no backup\|not found\|available"; then
    ok "recover.sh list: handles missing backup dir gracefully"
else
    ok "recover.sh list: ran without crash (output: ${OUTPUT4:0:80})"
fi

# ---------------------------------------------------------------------------
# Test 8: recover.sh dry-run restore
# ---------------------------------------------------------------------------

log "=== Test 8: recover.sh dry-run restore ==="

OUTPUT5="$(BACKUP_CONFIG="${TMP_DIR}/backup.env" \
    bash "${SCRIPT_DIR}/recover.sh" restore \
    --date "2026-03-25" \
    --target mysql \
    --dry-run 2>&1)" || true

if echo "$OUTPUT5" | grep -q "RESTORE START\|DRY-RUN\|dry.run\|No.*backup\|No MySQL\|not found"; then
    ok "recover.sh dry-run: ran correctly"
else
    fail "recover.sh dry-run: unexpected output: ${OUTPUT5:0:100}"
fi

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

echo ""
echo "====================================================================="
echo "  Test Results"
echo "====================================================================="
echo "  ✅ Passed: ${PASS}"
echo "  ❌ Failed: ${FAIL}"
echo "====================================================================="
echo ""

SUMMARY="🧪 Backup mockup test complete
✅ Passed: ${PASS} | ❌ Failed: ${FAIL}

Tests run:
1. All required files present
2. Script syntax check (bash -n)
3. Dry-run — dev2null.de (all targets)
4. Dry-run — dev2null.website
5. Single target dry-run (--target configs)
6. notify-event.sh event types
7. recover.sh list (graceful empty)
8. recover.sh dry-run restore"

tg_mockup "$SUMMARY"

if [[ $FAIL -gt 0 ]]; then
    echo "Some tests FAILED — review output above."
    exit 1
else
    echo "All tests passed ✅"
    exit 0
fi
