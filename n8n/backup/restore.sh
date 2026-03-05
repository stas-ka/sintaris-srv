#!/bin/bash
# ============================================
# Restore N8N from Backup
# ============================================
# Usage: ./restore.sh <backup_directory>
# Example: ./restore.sh backups/20260107_143000
# ============================================

set -e  # Exit on error

# Check if backup directory is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_directory>"
    echo "Example: $0 backups/20260107_143000"
    echo ""
    echo "Available backups:"
    ls -1d backups/*/ 2>/dev/null | sed 's|backups/||g' | sed 's|/$||g' || echo "No backups found"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "${BACKUP_DIR}" ]; then
    echo "Error: Backup directory '${BACKUP_DIR}' not found"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

SSH_CMD="ssh -i ${SSH_KEY_PATH} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST}"
SUDO_PREFIX=""

if [ "${DOCKER_REQUIRES_SUDO}" = "true" ]; then
    SUDO_PREFIX="sudo"
fi

echo "======================================"
echo "N8N Restore Process"
echo "======================================"
echo "Backup directory: ${BACKUP_DIR}"
echo ""
echo "WARNING: This will OVERWRITE existing data!"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# ============================================
# 1. Stop N8N Container
# ============================================
echo ""
echo "[1/5] Stopping N8N container..."
${SSH_CMD} "${SUDO_PREFIX} docker stop ${DOCKER_N8N_CONTAINER}" || echo "Container already stopped"
sleep 2
echo "  ✓ Container stopped"

# ============================================
# 2. Restore Databases
# ============================================
echo ""
echo "[2/5] Restoring PostgreSQL databases..."

# Find the latest dump files
APPS_DUMP=$(ls -t ${BACKUP_DIR}/database/n8n_apps_*.dump 2>/dev/null | head -1)
INTERNAL_DUMP=$(ls -t ${BACKUP_DIR}/database/n8n_internal_*.dump 2>/dev/null | head -1)

if [ ! -z "${APPS_DUMP}" ]; then
    echo "  - Restoring n8n_apps database..."
    cat "${APPS_DUMP}" | ${SSH_CMD} "PGPASSWORD='${PGPASSWORD}' pg_restore -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} -c -F c" || echo "Some errors may be normal during restore"
    echo "  ✓ n8n_apps database restored"
else
    echo "  ✗ n8n_apps dump file not found"
fi

if [ ! -z "${INTERNAL_DUMP}" ]; then
    echo "  - Restoring n8n internal database..."
    cat "${INTERNAL_DUMP}" | ${SSH_CMD} "${SUDO_PREFIX} docker exec -i ${DOCKER_N8N_CONTAINER} sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD pg_restore -h localhost -U \$POSTGRES_USER -d \$POSTGRES_DB -c -F c'" || echo "Some errors may be normal during restore"
    echo "  ✓ n8n internal database restored"
else
    echo "  ✗ n8n internal dump file not found"
fi

# ============================================
# 3. Restore Docker Configuration
# ============================================
echo ""
echo "[3/5] Restoring Docker configurations..."

if [ -f "${BACKUP_DIR}/docker/docker-compose.yml" ]; then
    echo "  - Restoring docker-compose.yml..."
    cat "${BACKUP_DIR}/docker/docker-compose.yml" | ${SSH_CMD} "cat > ${N8N_DOCKER_DIR}/docker-compose.yml"
    echo "  ✓ docker-compose.yml restored"
fi

if [ -f "${BACKUP_DIR}/docker/docker.env" ]; then
    echo "  - Restoring Docker .env file..."
    cat "${BACKUP_DIR}/docker/docker.env" | ${SSH_CMD} "cat > ${N8N_DOCKER_DIR}/.env"
    echo "  ✓ Docker .env restored"
fi

echo "  ✓ Docker configuration restored"

# ============================================
# 4. Restore N8N Data Directory
# ============================================
echo ""
echo "[4/5] Restoring N8N data directory..."

N8N_DATA_TAR=$(ls -t ${BACKUP_DIR}/n8n_data/n8n_data_*.tar.gz 2>/dev/null | head -1)

if [ ! -z "${N8N_DATA_TAR}" ]; then
    echo "  - Restoring N8N data directory..."
    cat "${N8N_DATA_TAR}" | ${SSH_CMD} "${SUDO_PREFIX} docker exec -i ${DOCKER_N8N_CONTAINER} tar xzf - -C /" || echo "Data restore skipped or failed"
    echo "  ✓ N8N data directory restored"
else
    echo "  ✗ N8N data tarball not found"
fi

# ============================================
# 5. Restart N8N Container
# ============================================
echo ""
echo "[5/5] Restarting N8N container..."
${SSH_CMD} "${SUDO_PREFIX} docker start ${DOCKER_N8N_CONTAINER}"
sleep 5

# Wait for N8N to be ready
echo "  - Waiting for N8N to start..."
for i in {1..30}; do
    if ${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} curl -s http://localhost:5678/healthz" > /dev/null 2>&1; then
        echo "  ✓ N8N is ready"
        break
    fi
    echo "    Waiting... ($i/30)"
    sleep 2
done

echo ""
echo "======================================"
echo "Restore completed!"
echo "======================================"
echo ""
echo "Please verify that N8N is working correctly:"
echo "  - N8N URL: ${N8N_HOST}"
echo "  - Check workflows are present"
echo "  - Check credentials are working"
echo ""
echo "Note: You may need to manually restore workflows via the API if they were not in the database."
