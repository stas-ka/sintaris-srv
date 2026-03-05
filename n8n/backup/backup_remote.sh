#!/bin/bash
# ============================================
# N8N Remote Backup & Download Script
# ============================================
# This script:
# 1. Creates backups on remote host
# 2. Downloads them to local machine
# 3. Optionally cleans up remote backups
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
LOCAL_BACKUP_DIR="${BACKUP_PATH:-./backups}/${TIMESTAMP}"
REMOTE_BACKUP_DIR="/tmp/n8n_backup_${TIMESTAMP}"
SSH_CMD="ssh -i ${SSH_KEY_PATH} -p ${SSH_PORT} ${SSH_USER}@${SSH_HOST}"
SCP_CMD="scp -i ${SSH_KEY_PATH} -P ${SSH_PORT}"
SUDO_PREFIX=""

if [ "${DOCKER_REQUIRES_SUDO}" = "true" ]; then
    SUDO_PREFIX="sudo"
fi

# Create local backup directory
mkdir -p "${LOCAL_BACKUP_DIR}"/{database,workflows,docker,n8n_data}

echo "======================================"
echo "N8N Remote Backup: ${TIMESTAMP}"
echo "======================================"
echo "Remote host: ${SSH_HOST}"
echo "Local backup: ${LOCAL_BACKUP_DIR}"
echo ""

# ============================================
# Step 1: Create remote backup directory
# ============================================
echo "[1/6] Creating remote backup directory..."
${SSH_CMD} "mkdir -p ${REMOTE_BACKUP_DIR}/{database,workflows,docker,n8n_data}"
echo "  ✓ Remote directory created: ${REMOTE_BACKUP_DIR}"

# ============================================
# Step 2: Backup databases on remote host
# ============================================
echo ""
echo "[2/6] Creating database backups on remote host..."

# Backup n8n_apps database
echo "  - Backing up n8n_apps database..."
${SSH_CMD} "PGPASSWORD='${PGPASSWORD}' pg_dump -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} -F c -f ${REMOTE_BACKUP_DIR}/database/n8n_apps_${TIMESTAMP}.dump"
${SSH_CMD} "PGPASSWORD='${PGPASSWORD}' pg_dump -h ${PGHOST} -p ${PGPORT} -U ${PGUSER} -d ${PGDATABASE} | gzip > ${REMOTE_BACKUP_DIR}/database/n8n_apps_${TIMESTAMP}.sql.gz"

# Backup n8n internal database
echo "  - Backing up n8n internal database..."
${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h localhost -U \$POSTGRES_USER -d \$POSTGRES_DB -F c' > ${REMOTE_BACKUP_DIR}/database/n8n_internal_${TIMESTAMP}.dump"
${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} sh -c 'PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h localhost -U \$POSTGRES_USER -d \$POSTGRES_DB' | gzip > ${REMOTE_BACKUP_DIR}/database/n8n_internal_${TIMESTAMP}.sql.gz"

echo "  ✓ Database backups created on remote host"

# ============================================
# Step 3: Backup Docker configs on remote host
# ============================================
echo ""
echo "[3/6] Backing up Docker configurations on remote host..."

${SSH_CMD} "cp ${N8N_DOCKER_DIR}/docker-compose.yml ${REMOTE_BACKUP_DIR}/docker/docker-compose.yml"
${SSH_CMD} "cp ${N8N_DOCKER_DIR}/.env ${REMOTE_BACKUP_DIR}/docker/docker.env 2>/dev/null || echo '# No .env file' > ${REMOTE_BACKUP_DIR}/docker/docker.env"
${SSH_CMD} "${SUDO_PREFIX} docker inspect ${DOCKER_N8N_CONTAINER} > ${REMOTE_BACKUP_DIR}/docker/container_inspect.json"
${SSH_CMD} "${SUDO_PREFIX} docker volume ls --format '{{.Name}}' | grep n8n > ${REMOTE_BACKUP_DIR}/docker/volumes.txt || echo 'No n8n volumes' > ${REMOTE_BACKUP_DIR}/docker/volumes.txt"
${SSH_CMD} "${SUDO_PREFIX} docker network inspect \$(${SUDO_PREFIX} docker inspect ${DOCKER_N8N_CONTAINER} | jq -r '.[0].NetworkSettings.Networks | keys[]') > ${REMOTE_BACKUP_DIR}/docker/network_inspect.json 2>/dev/null || echo '[]' > ${REMOTE_BACKUP_DIR}/docker/network_inspect.json"

echo "  ✓ Docker configurations backed up"

# ============================================
# Step 4: Backup N8N data directory
# ============================================
echo ""
echo "[4/6] Backing up N8N data directory on remote host..."

${SSH_CMD} "${SUDO_PREFIX} docker exec ${DOCKER_N8N_CONTAINER} tar czf /tmp/n8n_data.tar.gz /home/node/.n8n 2>/dev/null && ${SUDO_PREFIX} docker cp ${DOCKER_N8N_CONTAINER}:/tmp/n8n_data.tar.gz ${REMOTE_BACKUP_DIR}/n8n_data/n8n_data_${TIMESTAMP}.tar.gz || echo 'Data backup skipped'"

echo "  ✓ N8N data directory backed up"

# ============================================
# Step 5: Download backups from remote host
# ============================================
echo ""
echo "[5/6] Downloading backups from remote host..."

echo "  - Downloading databases..."
${SCP_CMD} -r "${SSH_USER}@${SSH_HOST}:${REMOTE_BACKUP_DIR}/database/*" "${LOCAL_BACKUP_DIR}/database/"

echo "  - Downloading Docker configs..."
${SCP_CMD} -r "${SSH_USER}@${SSH_HOST}:${REMOTE_BACKUP_DIR}/docker/*" "${LOCAL_BACKUP_DIR}/docker/"

echo "  - Downloading N8N data..."
${SCP_CMD} -r "${SSH_USER}@${SSH_HOST}:${REMOTE_BACKUP_DIR}/n8n_data/*" "${LOCAL_BACKUP_DIR}/n8n_data/"

echo "  ✓ Backups downloaded to local machine"

# ============================================
# Step 6: Backup workflows via API (local)
# ============================================
echo ""
echo "[6/6] Backing up workflows via API..."

# Use curl to fetch workflows
WORKFLOWS=$(curl -s -X GET "${N8N_API_BASE}/v1/workflows" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    -H "Accept: application/json")

if [ $? -eq 0 ]; then
    echo "${WORKFLOWS}" | jq '.' > "${LOCAL_BACKUP_DIR}/workflows/all_workflows.json"
    
    # Extract and save each workflow individually
    echo "${WORKFLOWS}" | jq -c '.data[]' | while read -r workflow; do
        WORKFLOW_ID=$(echo "${workflow}" | jq -r '.id')
        WORKFLOW_NAME=$(echo "${workflow}" | jq -r '.name' | sed 's/[^a-zA-Z0-9_-]/_/g')
        
        echo "  - Saving workflow: ${WORKFLOW_NAME} (${WORKFLOW_ID})"
        echo "${workflow}" | jq '.' > "${LOCAL_BACKUP_DIR}/workflows/${WORKFLOW_ID}_${WORKFLOW_NAME}.json"
    done
    
    echo "  ✓ Workflows backed up"
else
    echo "  ✗ Failed to fetch workflows via API"
fi

# Backup credentials via API
CREDENTIALS=$(curl -s -X GET "${N8N_API_BASE}/v1/credentials" \
    -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
    -H "Accept: application/json")

if [ $? -eq 0 ]; then
    echo "${CREDENTIALS}" | jq '.' > "${LOCAL_BACKUP_DIR}/n8n_data/credentials.json"
    echo "  ✓ Credentials backed up"
fi

# ============================================
# Create manifest
# ============================================
cat > "${LOCAL_BACKUP_DIR}/MANIFEST.txt" <<EOF
N8N Backup Manifest
==================
Date: $(date)
Timestamp: ${TIMESTAMP}
Host: ${SSH_HOST}
User: ${SSH_USER}
Container: ${DOCKER_N8N_CONTAINER}

Backup Contents:
- database/n8n_apps_${TIMESTAMP}.dump        : n8n_apps database (binary)
- database/n8n_apps_${TIMESTAMP}.sql.gz      : n8n_apps database (SQL)
- database/n8n_internal_${TIMESTAMP}.dump    : n8n internal database (binary)
- database/n8n_internal_${TIMESTAMP}.sql.gz  : n8n internal database (SQL)
- workflows/all_workflows.json               : All workflows
- workflows/*_*.json                         : Individual workflows
- n8n_data/credentials.json                  : N8N credentials (encrypted)
- n8n_data/n8n_data_${TIMESTAMP}.tar.gz     : N8N data directory
- docker/docker-compose.yml                  : Docker Compose config
- docker/docker.env                          : Docker environment
- docker/container_inspect.json              : Container config
- docker/volumes.txt                         : Docker volumes
- docker/network_inspect.json                : Network config

Backup Location: ${LOCAL_BACKUP_DIR}
Remote backup: ${REMOTE_BACKUP_DIR}
EOF

# ============================================
# Cleanup remote backup (optional)
# ============================================
echo ""
read -p "Remove backup files from remote host? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleaning up remote backup..."
    ${SSH_CMD} "rm -rf ${REMOTE_BACKUP_DIR}"
    echo "  ✓ Remote backup cleaned up"
else
    echo "  - Remote backup kept at: ${REMOTE_BACKUP_DIR}"
fi

# ============================================
# Cleanup old local backups
# ============================================
echo ""
echo "Cleaning up old local backups..."

if [ ! -z "${BACKUP_RETENTION_DAYS}" ] && [ "${BACKUP_RETENTION_DAYS}" -gt 0 ]; then
    find "${BACKUP_PATH}" -maxdepth 1 -type d -mtime +${BACKUP_RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null || true
    echo "  ✓ Removed backups older than ${BACKUP_RETENTION_DAYS} days"
else
    echo "  - No retention policy (keeping all backups)"
fi

# Create "latest" symlink
rm -f "${BACKUP_PATH}/latest"
ln -s "${TIMESTAMP}" "${BACKUP_PATH}/latest" 2>/dev/null || echo "  - Could not create symlink (Windows limitation)"

# ============================================
# Summary
# ============================================
echo ""
echo "======================================"
echo "Backup completed successfully!"
echo "======================================"
echo "Local backup: ${LOCAL_BACKUP_DIR}"
echo "Backup size: $(du -sh ${LOCAL_BACKUP_DIR} 2>/dev/null | cut -f1 || echo 'N/A')"
echo ""

cat "${LOCAL_BACKUP_DIR}/MANIFEST.txt"
