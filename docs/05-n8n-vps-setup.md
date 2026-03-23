# 05 — N8N Production Setup on VPS

N8N runs in Docker on the VPS, managed from `/opt/n8n-docker/`.

**URL:** https://automata.dev2null.de/  
**Docker project:** `n8n-docker`  
**Compose file:** `/opt/n8n-docker/docker-compose.yml`

## Architecture

```
nginx (HTTPS, automata.dev2null.de)
  └── localhost:5678
        └── n8n-docker-n8n-1  (stock n8n image, --network n8n-docker_default)
              └── n8n-runners   (worksafety-runners:latest — Python + JS runner)
```

N8N connects to the host PostgreSQL (172.17.0.1:5432), database `n8n`, user `n8n_user`.

## Database

```
Host PostgreSQL (not Docker):
  DB: n8n          — N8N metadata (workflows, credentials, executions)
  DB: n8n_apps     — Application/workflow data, pgvector enabled
  User: n8n_user   — password in /opt/n8n-docker/.env
```

## Managing N8N

```bash
source ~/projects/sintaris-srv/.env
ssh ${VPS_USER}@${VPS_HOST}

cd /opt/n8n-docker

# Status
sudo docker compose ps

# Restart N8N only
sudo docker compose up -d n8n

# Logs
sudo docker compose logs -f n8n

# Logs (last 50 lines)
sudo docker logs n8n-docker-n8n-1 --tail 50
```

## Key Environment Variables

Set in `/opt/n8n-docker/docker-compose.yml` (environment section):

```
N8N_HOST=automata.dev2null.de
N8N_PROTOCOL=https
WEBHOOK_URL=https://automata.dev2null.de/
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=172.17.0.1     # Docker bridge → host PostgreSQL
DB_POSTGRESDB_DATABASE=n8n
N8N_RUNNERS_ENABLED=true
N8N_RUNNERS_MODE=external
N8N_EMAIL_MODE=smtp
N8N_SMTP_HOST=172.17.0.1          # Docker bridge → host Postfix
N8N_SMTP_PORT=25
N8N_SMTP_SENDER=admin@dev2null.de
```

The `N8N_RUNNERS_AUTH_TOKEN` is stored in `/opt/n8n-docker/.env` (gitignored).

## Task Runners

The `worksafety-runners` image is a custom build with Python packages for Code nodes:

```bash
# Rebuild if Python packages change:
cd ~/Worksafety-superassistant/deployment/runners
sudo docker build -t worksafety-runners:latest -f Dockerfile.runners .
sudo docker compose -f /opt/n8n-docker/docker-compose.yml up -d n8n-runners
```

## Email (User Invitations)

SMTP is configured to relay through local Postfix (no auth).
Docker network `172.17.0.0/16` is in Postfix's `mynetworks` trusted list.

To invite a user: `https://automata.dev2null.de/settings/users` → Invite.

## Adding a New N8N Version

```bash
# Edit /opt/n8n-docker/docker-compose.yml
# Change: image: docker.n8n.io/n8nio/n8n:1.113.3  → new version

sudo docker compose -f /opt/n8n-docker/docker-compose.yml pull n8n
sudo docker compose -f /opt/n8n-docker/docker-compose.yml up -d n8n
```

## nginx Config

`/etc/nginx/sites-enabled/automata.dev2null.de`  
Proxies HTTPS → `localhost:5678`.

## Backup

N8N data (workflows, credentials) is in the Docker volume `n8n-docker_n8n_data`.

```bash
# Export workflows via N8N CLI
sudo docker exec n8n-docker-n8n-1 n8n export:workflow --all --output=/home/node/.n8n/workflows-backup.json

# Copy backup locally
sudo docker cp n8n-docker-n8n-1:/home/node/.n8n/workflows-backup.json ./
```
