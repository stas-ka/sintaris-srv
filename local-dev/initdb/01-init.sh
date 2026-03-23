#!/bin/bash
# =============================================================================
# Sintaris Local Dev — PostgreSQL initialization
# Runs automatically on first `docker compose up` (only if data volume is empty)
# =============================================================================
set -euo pipefail

N8N_PASS="${N8N_DB_PASSWORD:?N8N_DB_PASSWORD env var required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- n8n user
    CREATE USER n8n_user WITH PASSWORD '${N8N_PASS}';

    -- n8n metadata DB (workflows, credentials, executions)
    CREATE DATABASE n8n OWNER n8n_user;
    GRANT ALL PRIVILEGES ON DATABASE n8n TO n8n_user;

    -- n8n_apps DB (workflow application data + pgvector for RAG)
    CREATE DATABASE n8n_apps OWNER n8n_user;
    GRANT ALL PRIVILEGES ON DATABASE n8n_apps TO n8n_user;
EOSQL

# Enable pgvector on n8n_apps
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "n8n_apps" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "✅ Databases n8n and n8n_apps created, pgvector enabled on n8n_apps"
