# vps-admin — VPS Administration Hub

All artifacts for managing, monitoring, and documenting the Sintaris VPS infrastructure.

## Servers

| Host | Role |
|------|------|
| **dev2null.de** | Production VPS — nginx, PostgreSQL, n8n, EspoCRM, Nextcloud, mail |
| **dev2null.website** | VPN/proxy — x-ui, haproxy, webinar.bot |

Credentials in `../.env` (gitignored). See `.github/copilot-instructions.md` for SSH helpers.

---

## Contents

### `docs/` — Infrastructure documentation

| File | Description |
|------|-------------|
| [06-vps-dev2null.de.md](docs/06-vps-dev2null.de.md) | Full infra map — dev2null.de (disaster recovery) |
| [07-vps-dev2null.website.md](docs/07-vps-dev2null.website.md) | VPN/proxy server — dev2null.website |
| [vps-activity-protocol.md](docs/vps-activity-protocol.md) | Protocol for logging Copilot-assisted server changes |
| [vps-activity-log.md](docs/vps-activity-log.md) | Running log of all server changes |
| [vps-coding-protocol.md](docs/vps-coding-protocol.md) | Session protocol — every Copilot request logged (like vibe-coding-protocol.md) |

### `monitoring/` — Health check daemon

Deployed to both VPS servers. Sends Telegram alerts on failures.

```bash
# Deploy to a server
bash monitoring/install.sh
# Or manually: copy monitor.py + .env to /opt/sintaris-monitor/ on the VPS
```

| File | Description |
|------|-------------|
| [monitor.py](monitoring/monitor.py) | Health check script (services, Docker, HTTP) |
| [install.sh](monitoring/install.sh) | Installer — deploys to VPS, enables systemd timers |
| [monitor.env.example](monitoring/monitor.env.example) | Config template |
| `sintaris-monitor*.service/timer` | Systemd unit files |

### `copilot-notify/` — Copilot ↔ Telegram MCP Server

Persistent Docker service. Sends Telegram notifications when Copilot pauses, waits for your reply.

```bash
cd copilot-notify
docker compose up -d              # start service
curl http://localhost:7340/health # verify
```

MCP endpoint: `http://localhost:7340/sse`  
Registered in: `~/.copilot/mcp-config.json`

| File | Description |
|------|-------------|
| [server.mjs](copilot-notify/server.mjs) | MCP HTTP/SSE server v2 |
| [setup.mjs](copilot-notify/setup.mjs) | Setup wizard (run once) |
| [AGENT.md](copilot-notify/AGENT.md) | Copilot instructions — include in any session |
| [README.md](copilot-notify/README.md) | Full documentation |
| [docker-compose.yml](copilot-notify/docker-compose.yml) | Docker service config |

### `skills/` — OpenClaw skills

| File | Description |
|------|-------------|
| [skills/skill-vps-change/SKILL.md](skills/skill-vps-change/SKILL.md) | Safe server change skill for OpenClaw |

Symlink: `~/.openclaw/skills/skill-vps-change` → `vps-admin/skills/skill-vps-change`

---

## Copilot Usage

Open `vps-admin/` in a Copilot session — it automatically loads `.github/copilot-instructions.md` with full server context, SSH helpers, safety rules, and tool instructions.

**Quick start:**
```bash
cd ~/projects/sintaris-srv/vps-admin
# Start Copilot CLI here
source ../.env   # load credentials
```

**Telegram notifications** during long tasks:
```
tg_status(status="Checking nginx config on dev2null.de")
tg_notify(message="Found 3 warnings in nginx config", level="warning")
tg_ask(question="Restart nginx now?", options=["Yes","No"])
tg_complete(summary="...", wait_for_task=True)
```

---

## Documentation Rule — MANDATORY

> **Any new implementation, configuration change, or new service must update all relevant documentation before the session ends.**

| What changed | What to update |
|-------------|---------------|
| New service on VPS | `docs/06-*.md` or `docs/07-*.md`, `monitoring/monitor.py` profiles |
| New Copilot tool / skill | `skills/`, `copilot-notify/AGENT.md`, `.github/copilot-instructions.md` |
| New safety rule or process | `.github/copilot-instructions.md`, `docs/vps-activity-protocol.md`, `skills/skill-vps-change/SKILL.md` |
| Any session work | `docs/vps-activity-log.md` + `docs/vps-coding-protocol.md` (both mandatory) |
| Paths / structure changed | `README.md`, directory tree in `copilot-instructions.md`, any README that references old paths |

---

## Activity Log

Every Copilot-assisted server change must be logged in `docs/vps-activity-log.md`.  
Format described in `docs/vps-activity-protocol.md`.
