# Copilot Bridge — Deployment Guide

## Overview

This guide covers installing and running the Copilot Bridge on:
- **TariStation2** (IniCoS-1, Lubuntu 24.04) — primary OpenClaw engineering target
- Any Linux/macOS host
- Windows dev machine

---

## Automated Deployment to TariStation2

Use the provided deploy script from your Windows dev machine:

```bat
cd sintaris-srv\copilot-bridge
deploy\deploy_taristation2.sh
```

Or from PowerShell (using pscp/plink from PuTTY tools):

```powershell
# From sintaris-openclaw directory (credentials in .env)
.\deploy\deploy_taristation2.ps1
```

The script:
1. Copies `src/`, `requirements.txt`, `.env.example` to `/home/stas/copilot-bridge/` on TariStation2
2. Installs Python dependencies via pip3
3. Creates/enables the systemd user service `copilot-bridge.service`
4. Starts the service and verifies it is reachable at `http://127.0.0.1:8765/health`

---

## Manual Installation (Linux)

### 1. Prerequisites

```bash
# Python 3.10+ and pip3
python3 --version   # must be ≥ 3.10
pip3 --version

# Optionally install gh CLI (only needed if GH_TOKEN is not set in .env)
# https://cli.github.com/manual/installation
```

### 2. Copy files to target

```bash
# From dev machine — or clone the repo on the target:
git clone https://github.com/stas-ka/sintaris-srv.git
cd sintaris-srv/copilot-bridge
```

### 3. Install Python dependencies

```bash
pip3 install --user -r requirements.txt
```

### 4. Configure

```bash
cp .env.example .env
nano .env   # set GH_TOKEN and any overrides
```

Minimum required `.env` for TariStation2 (no `gh` CLI auth on remote host):

```env
GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx   # your GitHub personal access token
COPILOT_PROVIDER=auto
COPILOT_MODEL=gpt-4o
COPILOT_BRIDGE_HOST=127.0.0.1
COPILOT_BRIDGE_PORT=8765
LOG_LEVEL=INFO
```

> **GH_TOKEN**: use your existing token from `gh auth token` on the dev machine.  
> The token needs at least `repo` scope; Copilot API also requires an active
> GitHub Copilot subscription associated with your account.

### 5. Start manually

```bash
bash scripts/start.sh
```

### 6. Verify

```bash
curl http://127.0.0.1:8765/health
# Expected: {"status":"ok","provider":"auto","model":"gpt-4o","gh_token":true}

curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say: bridge works"}]}'
```

---

## Systemd Service (Linux — auto-start on boot)

### Install the service

```bash
mkdir -p ~/.config/systemd/user
cp deploy/copilot-bridge.service ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable copilot-bridge
systemctl --user start  copilot-bridge
systemctl --user status copilot-bridge
```

### Useful commands

```bash
# View logs
journalctl --user -u copilot-bridge -f

# Restart after config change
systemctl --user restart copilot-bridge

# Stop
systemctl --user stop copilot-bridge
```

---

## OpenClaw Integration

After the bridge is running on the same host as OpenClaw, add to `~/.taris/bot.env`:

### Option A — dedicated `copilot` provider (recommended)

```env
LLM_PROVIDER=copilot
COPILOT_BRIDGE_URL=http://127.0.0.1:8765
COPILOT_MODEL=gpt-4o
COPILOT_TIMEOUT=120
# Optional — only if you set COPILOT_BRIDGE_API_KEY in the bridge .env
# COPILOT_BRIDGE_KEY=your-secret-key
```

Then restart the OpenClaw bot:

```bash
systemctl --user restart taris
```

### Option B — OpenAI-compatible (no OpenClaw code changes)

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://127.0.0.1:8765
OPENAI_API_KEY=copilot-bridge
OPENAI_MODEL=gpt-4o
```

---

## Windows (Dev Machine)

```bat
cd sintaris-srv\copilot-bridge
copy .env.example .env
REM Edit .env and set GH_TOKEN (or ensure `gh auth login` was run)
scripts\start.bat
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `gh_token: false` in /health | Set `GH_TOKEN` in `.env`, or run `gh auth login` |
| HTTP 502 from bridge | Check bridge logs — Copilot subscription may be inactive; bridge auto-falls back to GitHub Models |
| `Connection refused` from OpenClaw | Bridge not running — check `systemctl --user status copilot-bridge` |
| `HTTP 401` from upstream | Token expired or invalid scope — regenerate token |
| Port 8765 in use | Change `COPILOT_BRIDGE_PORT` in `.env` and update `COPILOT_BRIDGE_URL` in `bot.env` |

---

## Updating the Bridge

```bash
cd ~/copilot-bridge
git pull   # if deployed from git
pip3 install --user -r requirements.txt
systemctl --user restart copilot-bridge
```
