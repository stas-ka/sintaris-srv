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

Edit `~/.taris/bot.env` (created by install script):

```bash
# Telegram
TELEGRAM_TOKEN=<bot token from @BotFather>
TELEGRAM_ADMIN_USER_ID=994963580

# LLM Provider (openrouter / openai / yandex / gemini / anthropic / local)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<key>

# Optional: OpenAI
OPENAI_API_KEY=<key>

# Database (PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=openclaw
DB_USER=openclaw_user
DB_PASS=<password>
```

## Database Setup

OpenClaw uses PostgreSQL (the local-dev stack from `02-local-dev-environment.md`):

```bash
cd ~/projects/sintaris-srv/local-dev
docker compose exec postgres psql -U postgres <<EOF
CREATE USER openclaw_user WITH PASSWORD '<password>';
CREATE DATABASE openclaw OWNER openclaw_user;
GRANT ALL PRIVILEGES ON DATABASE openclaw TO openclaw_user;
EOF
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
