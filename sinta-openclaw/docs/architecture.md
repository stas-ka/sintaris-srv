# OpenClaw — Architecture

This document describes the architecture of the OpenClaw AI gateway and its integration with Sintaris infrastructure.

> **Keep this document up to date** whenever a new skill, service, or integration is added.

---

## Overview

OpenClaw is a Node.js AI gateway that connects Telegram (and other channels) to AI models and custom skills. It runs as a local service on the developer machine and is exposed through the VPS via SSH reverse tunnel + nginx.

```
                        ┌─────────────────────────────────────────────────────┐
                        │               Local Machine (dev)                   │
                        │                                                     │
  Telegram ────────────►│  @suppenclaw_bot                                    │
                        │        │                                            │
                        │        ▼                                            │
                        │  OpenClaw Gateway (port 18789)                     │
                        │  ~/.local/bin/openclaw gateway                     │
                        │  systemd: openclaw-gateway.service                 │
                        │        │                                            │
                        │        ├── AI Models (OpenAI / Codex)              │
                        │        │                                            │
                        │        ├── Custom Skills (~/.openclaw/skills/)     │
                        │        │     skill-n8n       → N8N API             │
                        │        │     skill-postgres  → PostgreSQL          │
                        │        │     skill-espocrm   → EspoCRM (VPS)      │
                        │        │     skill-nextcloud → Nextcloud (VPS)    │
                        │        │                                            │
                        │        └── Built-in Skills (51 bundled)           │
                        │                                                     │
                        │  MCP Server (stdio)                                │
                        │  ~/.local/lib/openclaw-mcp/server.mjs              │
                        │  → Used by GitHub Copilot CLI                     │
                        │                                                     │
                        │  SSH Reverse Tunnel                                │
                        │  systemd: openclaw-tunnel.service                  │
                        │  ssh -R 127.0.0.1:18789:localhost:18789            │
                        └──────────────────┬──────────────────────────────────┘
                                           │ SSH tunnel
                        ┌──────────────────▼──────────────────────────────────┐
                        │                VPS (dev2null.de)                   │
                        │                                                     │
                        │  nginx (agents.sintaris.net)                       │
                        │    /openclaw/ → proxy → 127.0.0.1:18789           │
                        │                                                     │
                        │  Web UI: https://agents.sintaris.net/openclaw/    │
                        └─────────────────────────────────────────────────────┘
```

---

## Components

### 1. OpenClaw Gateway (`openclaw-gateway.service`)

| Property | Value |
|---|---|
| Binary | `~/.local/bin/openclaw` (npm global install) |
| Config | `~/.openclaw/openclaw.json` |
| Port | `18789` (bound to all interfaces: `0.0.0.0`) |
| systemd service | `~/.config/systemd/user/openclaw-gateway.service` |
| Template | `sinta-openclaw/systemd/openclaw-gateway.service` |
| Web UI | `http://localhost:18789/` (React SPA) |

Key config settings in `openclaw.json`:
- `gateway.bind = "lan"` — listens on all interfaces (required for SSH tunnel)
- `gateway.port = 18789`
- `channels.telegram.groupPolicy = "open"` — allows group usage
- `agents.defaults.workspace` — OpenClaw workspace dir

### 2. Telegram Channel

| Property | Value |
|---|---|
| Bot | `@suppenclaw_bot` |
| Token | In `~/.openclaw/openclaw.json` → `channels.telegram.botToken` |
| Access | Paired DMs + open group policy |

### 3. Custom Skills

Skills live in `sinta-openclaw/skills/` and are symlinked into `~/.openclaw/skills/`.

| Skill | Purpose | Key Endpoint |
|---|---|---|
| `skill-n8n` | N8N workflow management | `http://localhost:5678` (local) / `https://automata.dev2null.de` (VPS) |
| `skill-postgres` | PostgreSQL queries | `localhost:5432` (Docker) |
| `skill-espocrm` | EspoCRM CRM data | `https://crm.dev2null.de` |
| `skill-nextcloud` | Nextcloud files | `https://cloud.dev2null.de` |

All skills are SKILL.md files with YAML frontmatter. OpenClaw loads them from `~/.openclaw/skills/` (via `CONFIG_DIR/skills` path resolution in the gateway binary).

### 4. SSH Reverse Tunnel (`openclaw-tunnel.service`)

| Property | Value |
|---|---|
| Command | `ssh -N -R 127.0.0.1:18789:localhost:18789 stas@dev2null.de` |
| systemd service | `~/.config/systemd/user/openclaw-tunnel.service` |
| Template | `sinta-openclaw/systemd/openclaw-tunnel.service` |
| Effect | VPS port 18789 (loopback only) → forwards to local machine port 18789 |

The tunnel binds only on `127.0.0.1` on the VPS, so it's not directly exposed. nginx proxies it.

### 5. nginx Proxy (VPS)

Location block added to `/etc/nginx/sites-enabled/agents.sintaris.net.conf`:

```nginx
location /openclaw/ {
    proxy_pass http://127.0.0.1:18789/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

Public URL: **https://agents.sintaris.net/openclaw/**

### 6. MCP Server (GitHub Copilot CLI integration)

| Property | Value |
|---|---|
| Location | `~/.local/lib/openclaw-mcp/server.mjs` |
| Source | `sinta-openclaw/mcp/server.mjs` |
| Protocol | MCP stdio (Model Context Protocol) |
| Config | `~/.config/github-copilot/mcp.json` |

The MCP server exposes OpenClaw as a tool to GitHub Copilot CLI, allowing Copilot to send messages to the OpenClaw agent and read its responses.

---

## Service Dependencies

```
openclaw-gateway.service
    └── requires: network.target
    └── reads: ~/.openclaw/openclaw.json
    └── loads: ~/.openclaw/skills/* (via symlinks → sinta-openclaw/skills/)

openclaw-tunnel.service
    └── requires: network-online.target
    └── depends on: openclaw-gateway.service (logical, not systemd dep)
    └── requires: SSH access to dev2null.de
```

---

## Data Flow

```
User (Telegram) → @suppenclaw_bot → Telegram API → OpenClaw Gateway
                                                        │
                                          ┌─────────────▼──────────────┐
                                          │      Agent Loop            │
                                          │  1. Parse intent           │
                                          │  2. Load relevant skills   │
                                          │  3. Call AI model (OpenAI) │
                                          │  4. Execute tool calls     │
                                          │  5. Return response        │
                                          └─────────────┬──────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────────┐
                              │                         │                         │
                              ▼                         ▼                         ▼
                     N8N API                   PostgreSQL                  EspoCRM / Nextcloud
                  localhost:5678             localhost:5432               crm.dev2null.de
                                                                         cloud.dev2null.de
```

---

## Credentials & Secrets

| Secret | Location | Notes |
|---|---|---|
| Telegram Bot Token | `~/.openclaw/openclaw.json` | `channels.telegram.botToken` |
| Gateway Auth Token | `~/.openclaw/openclaw.json` | `gateway.auth` — used for Web UI login |
| N8N API Key | `sinta-openclaw/skills/skill-n8n/api-keys.txt` | gitignored |
| OpenAI API Key | `~/.openclaw/openclaw.json` | via agent model config |

All secrets are gitignored. See `sinta-openclaw/config/openclaw.json.template` for the config structure.

---

## Installed Services (This Machine)

| Service | Status | URL |
|---|---|---|
| OpenClaw Gateway | `systemctl --user status openclaw-gateway` | `http://localhost:18789` |
| OpenClaw Tunnel | `systemctl --user status openclaw-tunnel` | SSH → VPS:18789 |
| OpenClaw Web UI | via nginx on VPS | https://agents.sintaris.net/openclaw/ |
| N8N (local) | Docker `local-dev-n8n-1` | http://localhost:5678 |
| PostgreSQL (local) | Docker `local-dev-postgres-1` | localhost:5432 |
