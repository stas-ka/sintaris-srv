# 04 — OpenClaw Setup

OpenClaw is the local AI assistant (Telegram bot + web UI). Based on the `picoclaw` project.

**Repo:** `~/projects/picoclaw`  
**Config dir:** `~/.taris/`

## Prerequisites

```bash
sudo apt install python3 python3-venv python3-pip ffmpeg portaudio19-dev git
```

## Installation

```bash
cd ~/projects/picoclaw
bash install_openclaw_user.sh
```

The script:
1. Creates `~/.taris/` directory structure (files, logs, audio)
2. Creates Python virtualenv at `~/.taris/venv`
3. Downloads Vosk Russian STT model (~48 MB)
4. Downloads Piper TTS binary + Russian voice model
5. Installs all Python dependencies

## Configuration

Edit `~/.taris/bot.env` (created by install script). Key sections:

```bash
# Telegram
BOT_TOKEN=<bot token from @BotFather>
ALLOWED_USERS=<comma-separated Telegram chat IDs>
ADMIN_USERS=<admin chat IDs>

# LLM Provider (openai | gemini | anthropic | yandexgpt | local)
LLM_PROVIDER=openai
OPENAI_API_KEY=<key>
OPENAI_BASE_URL=https://openrouter.ai/api/v1   # use OpenRouter as proxy
OPENAI_MODEL=openai/gpt-4o-mini

# Storage backend
STORE_BACKEND=postgres
STORE_PG_DSN=postgresql://taris:taris_openclaw_2026@localhost:5432/taris
```

### Sintaris Services Access

Add to `bot.env` to enable OpenClaw to interact with local and VPS services:

```bash
# Nextcloud (VPS)
NEXTCLOUD_URL=https://cloud.dev2null.de
NEXTCLOUD_USER=<nextcloud username>
NEXTCLOUD_PASS=<app password>

# N8N local dev instance
N8N_LOCAL_URL=http://localhost:5678
N8N_LOCAL_API_KEY=<jwt api key from N8N Settings → API>

# N8N VPS instance (basic auth — user management disabled on v2.2.3)
N8N_VPS_URL=https://automata.dev2null.de
N8N_VPS_USER=admin
N8N_VPS_PASS=<password>

# EspoCRM (VPS, port 8888)
ESPOCRM_URL=http://dev2null.de:8888
ESPOCRM_USER=admin
# ESPOCRM_PASS — stored separately, see .credentials/

# PostgreSQL for apps/workflows (local)
PG_LOCAL_DSN=postgresql://n8n_user:N8Nzusammen2019@localhost:5432/n8n_apps
```

## Database Setup

OpenClaw uses a dedicated `taris` database in the local-dev PostgreSQL stack:

```bash
cd ~/projects/sintaris-srv/local-dev
docker compose exec postgres psql -U postgres -c "CREATE USER taris WITH PASSWORD 'taris_openclaw_2026';"
docker compose exec postgres psql -U postgres -c "CREATE DATABASE taris OWNER taris;"
docker compose exec postgres psql -d taris -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

On VPS PostgreSQL (for when OpenClaw runs on server):
```bash
sudo -u postgres createuser taris --pwprompt   # use: taris_openclaw_2026
sudo -u postgres createdb taris --owner=taris
sudo -u postgres psql -d taris -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Running

```bash
cd ~/projects/picoclaw
source ~/.taris/venv/bin/activate
python bot.py
```

Or as a systemd user service:
```bash
systemctl --user start openclaw
systemctl --user enable openclaw   # start on login
```

## Web UI

Runs on HTTPS port 8080 locally.  
Externally accessible via VPS reverse proxy at `https://agents.sintaris.net/picoassist/`.

## GitHub Copilot CLI Integration

The `openclaw-openclaw_agent` tool in Copilot CLI connects to the running OpenClaw gateway.
Requires the OpenClaw gateway to be running locally.

```bash
# Check gateway status
# (available as Copilot CLI tool: openclaw-openclaw_health)
```
