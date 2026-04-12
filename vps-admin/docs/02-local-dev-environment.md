# 02 — Local Dev Environment

Local development stack running in Docker. No cloud dependencies.

## Requirements

- Docker Engine ≥ 24
- Docker Compose plugin (v2)

Install on Ubuntu/Debian:
```bash
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER  # log out and back in after this
```

## Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| PostgreSQL 17 | `pgvector/pgvector:pg17` | 5432 | Database (with pgvector) |
| N8N | `docker.n8n.io/n8nio/n8n:latest` | 5678 | Workflow automation |

### Databases

| Database | Owner | Purpose |
|----------|-------|---------|
| `n8n` | `n8n_user` | N8N metadata (workflows, credentials, executions) |
| `n8n_apps` | `n8n_user` | Application data; pgvector extension enabled for RAG |

## Setup

```bash
cd ~/projects/sintaris-srv/local-dev

# First time: copy and fill in credentials
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD and N8N_DB_PASSWORD

# Start everything
docker compose up -d

# Check status
docker compose ps
```

**N8N UI:** http://localhost:5678  
**PostgreSQL:** `localhost:5432` (user: `postgres`, pass: from .env)

## .env

```
POSTGRES_PASSWORD=<superuser password>
N8N_DB_PASSWORD=<password for n8n_user — used by both N8N and n8n_apps>
```

The `.env` file is gitignored. See `.env.example` for the template.

## DB Initialization

On first `docker compose up`, the script `initdb/01-init.sh` runs automatically and:
1. Creates user `n8n_user`
2. Creates databases `n8n` and `n8n_apps`
3. Enables `pgvector` on `n8n_apps`

This only runs once (when the `postgres_data` volume is empty).

## Common Commands

```bash
# Start
docker compose up -d

# Stop (keep data)
docker compose down

# Wipe all data and start fresh
docker compose down -v && docker compose up -d

# View logs
docker compose logs -f n8n
docker compose logs -f postgres

# Connect to PostgreSQL
docker compose exec postgres psql -U postgres

# Connect to n8n_apps DB
docker compose exec postgres psql -U n8n_user -d n8n_apps

# Check pgvector
docker compose exec postgres psql -U postgres -d n8n_apps -c "\dx"
```

## Adding pgvector Tables (n8n_apps)

```sql
-- Connect to n8n_apps first
\c n8n_apps

-- Example: document embeddings table
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  embedding VECTOR(1536),   -- OpenAI embedding dimension
  metadata JSONB
);

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```
