#!/bin/bash
# ============================================
# N8N Complete Backup Script
# ============================================
# This script backs up:
# - PostgreSQL databases (n8n_apps and n8n itself)
# - N8N workflows (individual JSON files)
# - N8N settings and credentials
# - Docker configurations
# ============================================

set -e  # Exit on error

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_PATH:-./backups}/${TIMESTAMP}"
SSH_CMD="ssh -i ${SSH_KEY_PATH} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST}"
SUDO_PREFIX=""

if [ "${DOCKER_REQUIRES_SUDO}" = "true" ]; then
    SUDO_PREFIX="sudo"
fi

# Create backup directory
mkdir -p "${BACKUP_DIR}"/{database,workflows,docker,n8n_data}

echo "======================================"
echo "N8N Backup Started: ${TIMESTAMP}"
echo "======================================"

# ============================================
# 1. Backup PostgreSQL Databases
# ============================================
echo ""
echo "[1/5] Backing up PostgreSQL databases..."

# Backup n8n_apps database
echo "  - Backing up n8n_apps database..."
${SSH_CMD} "PGPASSWORD='${PGPASSWORD}' pg_dump -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} -F c" > "${BACKUP_DIR}/database/n8n_apps_${TIMESTAMP}.dump"

# Backup n8n self database (workflow execution data, credentials, etc.)
echo "  - Backing up n8n internal database..."
${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h localhost -U \$POSTGRES_USER -d \$POSTGRES_DB -F c'" > "${BACKUP_DIR}/database/n8n_internal_${TIMESTAMP}.dump"

# Also create SQL format for easy viewing
echo "  - Creating SQL format backups..."
${SSH_CMD} "PGPASSWORD='${PGPASSWORD}' pg_dump -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE}" | gzip > "${BACKUP_DIR}/database/n8n_apps_${TIMESTAMP}.sql.gz"
${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h localhost -U \$POSTGRES_USER -d \$POSTGRES_DB'" | gzip > "${BACKUP_DIR}/database/n8n_internal_${TIMESTAMP}.sql.gz"

echo "  ✓ Database backups completed"

# ============================================
# 2. Backup N8N Workflows (via API)
# ============================================
echo ""
echo "[2/5] Backing up N8N workflows..."

# Fetch all workflows
WORKFLOWS=$(curl -s -X GET "${N8N_API_BASE}/v1/workflows" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    -H "Accept: application/json")

# Save complete workflow list
echo "${WORKFLOWS}" | jq '.' > "${BACKUP_DIR}/workflows/all_workflows.json"

# Extract and save each workflow individually
echo "${WORKFLOWS}" | jq -c '.data[]' | while read -r workflow; do
    WORKFLOW_ID=$(echo "${workflow}" | jq -r '.id')
    WORKFLOW_NAME=$(echo "${workflow}" | jq -r '.name' | sed 's/[^a-zA-Z0-9_-]/_/g')
    
    echo "  - Saving workflow: ${WORKFLOW_NAME} (${WORKFLOW_ID})"
    echo "${workflow}" | jq '.' > "${BACKUP_DIR}/workflows/${WORKFLOW_ID}_${WORKFLOW_NAME}.json"
done

echo "  ✓ Workflow backups completed"

# ============================================
# 3. Backup N8N Credentials (Encrypted)
# ============================================
echo ""
echo "[3/5] Backing up N8N credentials..."

# Fetch all credentials
CREDENTIALS=$(curl -s -X GET "${N8N_API_BASE}/v1/credentials" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    -H "Accept: application/json")

echo "${CREDENTIALS}" | jq '.' > "${BACKUP_DIR}/n8n_data/credentials.json"
echo "  ✓ Credentials backup completed"

# ============================================
# 4. Backup Docker Configuration
# ============================================
echo ""
echo "[4/5] Backing up Docker configurations..."

# Backup docker-compose.yml
echo "  - Backing up docker-compose.yml..."
${SSH_CMD} "cat ${N8N_DOCKER_DIR}/docker-compose.yml" > "${BACKUP_DIR}/docker/docker-compose.yml"

# Backup .env file if exists
echo "  - Backing up Docker .env file..."
${SSH_CMD} "cat ${N8N_DOCKER_DIR}/.env 2>/dev/null || echo '# No .env file found'" > "${BACKUP_DIR}/docker/docker.env"

# Backup docker container configuration
echo "  - Backing up container inspection..."
${SSH_CMD} "${SUDO_PREFIX} docker inspect ${DOCKER_N8N_CONTAINER}" | jq '.' > "${BACKUP_DIR}/docker/container_inspect.json"

# Backup volume information
echo "  - Backing up volume information..."
${SSH_CMD} "${SUDO_PREFIX} docker volume ls --format '{{.Name}}' | grep n8n || true" > "${BACKUP_DIR}/docker/volumes.txt"

# Backup network information
echo "  - Backing up network information..."
${SSH_CMD} "${SUDO_PREFIX} docker network inspect \$(${SUDO_PREFIX} docker inspect ${DOCKER_N8N_CONTAINER} | jq -r '.[0].NetworkSettings.Networks | keys[]') 2>/dev/null || echo 'No network info'" | jq '.' > "${BACKUP_DIR}/docker/network_inspect.json"

echo "  ✓ Docker configuration backups completed"

# ============================================
# 5. Backup N8N Data Directory
# ============================================
echo ""
echo "[5/5] Backing up N8N data directory..."

# Create a tarball of the n8n data directory
echo "  - Creating tarball of N8N data..."
${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} tar czf - /home/node/.n8n 2>/dev/null || echo 'Data dir backup skipped'" > "${BACKUP_DIR}/n8n_data/n8n_data_${TIMESTAMP}.tar.gz"

echo "  ✓ N8N data directory backup completed"

# ============================================
# Create Backup Manifest
# ============================================
echo ""
echo "Creating backup manifest..."

cat > "${BACKUP_DIR}/MANIFEST.txt" <<EOF
N8N Backup Manifest
==================
Date: $(date)
Timestamp: ${TIMESTAMP}
Host: ${SSH_HOST}
User: ${SSH_USER}
Container: ${DOCKER_N8N_CONTAINER}

Backup Contents:
- database/n8n_apps_${TIMESTAMP}.dump        : n8n_apps database (binary format)
- database/n8n_apps_${TIMESTAMP}.sql.gz      : n8n_apps database (SQL format)
- database/n8n_internal_${TIMESTAMP}.dump    : n8n internal database (binary format)
- database/n8n_internal_${TIMESTAMP}.sql.gz  : n8n internal database (SQL format)
- workflows/all_workflows.json               : All workflows in single file
- workflows/*_*.json                         : Individual workflow files
- n8n_data/credentials.json                  : N8N credentials (encrypted)
- n8n_data/n8n_data_${TIMESTAMP}.tar.gz     : Complete N8N data directory
- docker/docker-compose.yml                  : Docker Compose configuration
- docker/docker.env                          : Docker environment variables
- docker/container_inspect.json              : Container configuration
- docker/volumes.txt                         : Docker volumes list
- docker/network_inspect.json                : Network configuration

Backup Location: ${BACKUP_DIR}
EOF

cat "${BACKUP_DIR}/MANIFEST.txt"

# ============================================
# Cleanup Old Backups
# ============================================
echo ""
echo "Cleaning up old backups..."

if [ ! -z "${BACKUP_RETENTION_DAYS}" ] && [ "${BACKUP_RETENTION_DAYS}" -gt 0 ]; then
    find "${BACKUP_PATH}" -maxdepth 1 -type d -mtime +${BACKUP_RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null || true
    echo "  ✓ Removed backups older than ${BACKUP_RETENTION_DAYS} days"
else
    echo "  - No retention policy configured (keeping all backups)"
fi

# ============================================
# Summary
# ============================================
echo ""
echo "======================================"
echo "Backup completed successfully!"
echo "======================================"
echo "Backup location: ${BACKUP_DIR}"
echo "Backup size: $(du -sh ${BACKUP_DIR} | cut -f1)"
echo ""

# Create a "latest" symlink
rm -f "${BACKUP_PATH}/latest"
ln -s "${TIMESTAMP}" "${BACKUP_PATH}/latest"
echo "Latest backup: ${BACKUP_PATH}/latest -> ${TIMESTAMP}"
