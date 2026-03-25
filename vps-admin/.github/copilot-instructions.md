# VPS Admin — Copilot Instructions

All VPS administration artifacts live in this directory (`vps-admin/`).  
Credentials are in `../.env` (gitignored — never commit real values).

---

## 📲 Telegram Notifications — MANDATORY

The `copilot-notify` MCP server runs at `http://localhost:7340/sse` and is always available.  
**You MUST use these tools in every session — not just when you remember to:**

| When | Tool | What to send |
|------|------|-------------|
| Start of every major step | `tg_status` | Current phase, e.g. `"Analyzing disk usage on dev2null.website"` |
| Before a critical action | `tg_ask` | Describe action + risk + Yes/No buttons — **wait for reply** |
| After completing a significant step | `tg_notify` | Full result / output |
| Task is fully done | `tg_complete` | Full summary, `wait_for_task=true` |

**Failure to call `tg_complete` at the end of a task is a bug.**  
Full usage instructions: `./copilot-notify/AGENT.md`

---

## Servers

| Host | IP | User | Auth | Role |
|------|----|------|------|------|
| dev2null.de | 152.53.224.213 | stas | SSH key `~/.ssh/id_ed25519` | **PRODUCTION — HIGHEST PRIORITY** |
| dev2null.website | 82.165.231.93 | boh | password (`WEB_PASS` in `../.env`) | VPN/proxy server |

> ⚠️ **dev2null.de is a live production server.** Back up configs before changes. Prefer `reload` over `restart`. Test with `--dry-run` / `-t` where possible.

SSH helpers:
```bash
source ../.env
# dev2null.de (key auth)
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST}
# dev2null.website (password auth)
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST}
```

---

## Directory Structure

```
vps-admin/
├── .github/copilot-instructions.md   ← this file
├── docs/
│   ├── 06-vps-dev2null.de.md         full infrastructure map (disaster recovery)
│   ├── 07-vps-dev2null.website.md    VPN/proxy server docs
│   ├── vps-activity-protocol.md      how to log every server change
│   ├── vps-activity-log.md           running log of all Copilot-assisted changes
│   └── vps-coding-protocol.md        ← SESSION PROTOCOL (mandatory, like vibe-coding-protocol.md)
├── monitoring/
│   ├── monitor.py                    health check daemon (deployed to both VPS)
│   ├── monitor.env.example           config template for monitor
│   ├── install.sh                    installer (deploys monitor to a VPS)
│   └── sintaris-monitor*.service/timer  systemd unit files
├── copilot-notify/
│   ├── server.mjs                    MCP server v2 (HTTP/SSE, Docker)
│   ├── setup.mjs                     interactive setup + HMAC sign
│   ├── docker-compose.yml            Docker service (port 7340)
│   ├── AGENT.md                      Copilot tool usage instructions
│   └── README.md                     full documentation
├── skills/
│   └── skill-vps-change/SKILL.md    OpenClaw skill for safe server ops
└── README.md                         hub index
```

---

## Sensitive Data Rule

**ALL credentials, passwords, tokens, and secrets → `../.env` ONLY. Never in docs or code.**

- `../.env` is gitignored — the only place for real values
- `../.env.example` has empty placeholders — commit only this
- Docs use `${VAR_NAME}` or `<placeholder>` notation — never real values
- Applies to: SSH passwords, API tokens, bot tokens, DB passwords, secrets

---

## ⛔ Owner Confirmation Rule — MANDATORY

> **Critical operations on any host ALWAYS require explicit confirmation from the owner (Stas).**  
> This rule applies even if Copilot has full permissions, is running in autopilot mode, or was given a broad open-ended task.

### What counts as a critical operation (always ask first):

| Category | Examples |
|----------|---------|
| **Delete / remove data** | rm files, truncate logs, drop databases, docker prune, remove swap |
| **Stop / restart services** | systemctl stop/restart, docker compose down, reboot |
| **Change system config** | fstab, journald.conf, sshd_config, nginx, firewall rules |
| **Network changes** | firewall rules, port bindings, VPN config |
| **Disk / memory layout** | swap create/delete, partition changes, disk format |
| **Security changes** | user creation/deletion, sudo rules, SSH keys, permissions |
| **Package install/remove** | apt install/remove, pip install system-wide |
| **Container changes** | docker rm, image prune, compose stack changes on production |

### How to ask:

Before each critical step, **use `tg_ask` (Telegram MCP) as the primary confirmation channel**, so the owner receives the request on their phone even when not watching the Copilot chat. Fall back to `ask_user` only if the MCP server is unavailable.

```
tg_ask(
  question="Step N — [Server]: [What will be done]\nRisk: MED\nExpected: [outcome]\n\nProceed?",
  options=["Yes", "No"]
)
```

- A clear description of **what** will be done
- **Why** it is needed
- **Risk** level (LOW / MED / HIGH)
- Expected outcome

**Never batch multiple critical steps into a single confirmation.** Ask one step at a time.

### 🚫 If the owner is unavailable (tg_ask/ask_user returns TIMEOUT / no response):

**STOP. Do not proceed with the critical operation.**

This is strictly forbidden reasoning — never use it:
> *"The user is unavailable. I will proceed autonomously because the task was explicitly requested / I have full permissions / autopilot mode is on."*

A broad task request (e.g. "clean disk", "resize swap") is **NOT** confirmation for individual critical steps.  
Confirmation must be an **explicit YES** via Telegram or Copilot chat, given in real time.

**When blocked by unavailability:**
1. Complete all safe (read-only / non-destructive) steps that don't need confirmation
2. Send a `tg_notify` summarising what was done and what is **waiting for confirmation**
3. List each pending critical step with its risk and expected outcome
4. Stop and wait — do not execute any critical step until the owner responds

### Exceptions (no confirmation needed):
- Read-only inspection commands (`df`, `ls`, `cat`, `docker ps`, `systemctl status`)
- Writing/editing local files in the git repo (not on the server)
- Running tests or dry-runs that make no changes
- Steps the owner confirmed explicitly and in real time in the current message

---

## Safety Rules for Server Changes

1. **Read before write** — understand what is running before changing it
2. **Backup first** — `cp file file.bak` before editing any config
3. **Test before apply** — `nginx -t`, `--dry-run`, etc.
4. **Prefer reload** — `systemctl reload` instead of `restart` where possible
5. **Log every change** — update `./docs/vps-activity-log.md` after each session
6. **Write session protocol** — add a row to `./docs/vps-coding-protocol.md` for every request (analog to `sintaris-pl/doc/vibe-coding-protocol.md`). **Mandatory — not optional.**
6. **Reversible steps** — keep old configs until new ones are verified
7. **Ask before acting** — see Owner Confirmation Rule above

---

## How to Work

```bash
source ../.env   # load all credentials

# SSH to dev2null.de
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST}

# Run a remote command
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'sudo systemctl status nginx'

# SSH to dev2null.website
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST}
```

---

## Common Tasks

### Services
```bash
source ../.env
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'sudo systemctl status nginx postgresql docker'
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'sudo systemctl restart <service>'
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'sudo journalctl -u <service> -n 100 --no-pager'
```

### nginx
```bash
source ../.env
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'sudo nginx -t && sudo systemctl reload nginx'
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'ls /etc/nginx/sites-enabled/'
```

### Docker services
```bash
source ../.env
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'docker ps'
# Manage a compose stack (e.g. nextcloud):
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'cd /opt/nextcloud-docker && sudo docker compose ps'
```

### PostgreSQL
```bash
source ../.env
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'sudo -u postgres psql -c "\l"'
```

### System health
```bash
source ../.env
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} 'df -h && free -h && sudo systemctl --failed'
```

---

## Stack — dev2null.de

| Service | Location | URL |
|---------|----------|-----|
| nginx | systemd | — |
| PostgreSQL | systemd | — |
| Postfix/Dovecot | systemd | mail.dev2null.de |
| n8n | Docker `/opt/n8n-docker/` | automata.dev2null.de |
| EspoCRM | Docker | crm.dev2null.de |
| Nextcloud | Docker `/opt/nextcloud-docker/` | cloud.dev2null.de |
| PGAdmin | Docker | db.dev2null.de |
| Roundcube | systemd/web | webmail.dev2null.de |
| SpamAssassin | systemd (`spamd`) | — |

Full infra map: `./docs/06-vps-dev2null.de.md`

## Stack — dev2null.website

| Service | Location |
|---------|----------|
| nginx | systemd |
| x-ui (Xray VPN) | systemd |
| haproxy | systemd |
| webinar.bot | systemd |
| amnezia-wg-easy | Docker |

Full docs: `./docs/07-vps-dev2null.website.md`

---

## Monitoring

Health-check daemon deployed to both VPS servers.

- **Source:** `./monitoring/monitor.py`
- **Deploy:** `bash ./monitoring/install.sh`
- **Config:** `./monitoring/monitor.env.example` → copy to `/opt/sintaris-monitor/.env` on VPS
- **Schedule:** every 5 min + 08:00 daily summary
- **Alerts:** Telegram bot (`TG_BOT_TOKEN` + `TG_CHAT_ID` from `../.env`)

Monitored on dev2null.de: nginx, spamd, postgresql, docker + 9 containers + 5 HTTP endpoints  
Monitored on dev2null.website: nginx, docker, x-ui, haproxy, webinar.bot

---

## Copilot Notify (MCP Server)

Bidirectional Telegram ↔ Copilot notifications. Runs as persistent Docker service.

- **Source:** `./copilot-notify/`
- **Docs:** `./copilot-notify/README.md`
- **Agent instructions:** `./copilot-notify/AGENT.md` ← include in Copilot prompts
- **MCP endpoint:** `http://localhost:7340/sse`
- **Manage:**
  ```bash
  cd ./copilot-notify
  docker compose up -d        # start
  docker compose logs -f      # logs
  curl http://localhost:7340/health
  ```
- **Registered in:** `~/.copilot/mcp-config.json`

### Copilot Notify Tool Usage

Include `./copilot-notify/AGENT.md` in every session where you want Telegram notifications.

Quick reference:
- `tg_notify(message, level?)` — send notification (always use for pauses, errors, milestones)
- `tg_ask(question, options?, timeout_sec?)` — ask user, wait for reply; use `options=["Yes","No"]` for buttons
- `tg_status(status)` — update `/status` queryable state at each major phase
- `tg_complete(summary, wait_for_task?)` — send FULL results, optionally show "New task" button

---

## VPS Change Skill (OpenClaw)

Safe server operation skill for OpenClaw AI gateway.

- **Source:** `./skills/skill-vps-change/SKILL.md`
- **Deployed:** `~/.openclaw/skills/skill-vps-change/` (symlink)
- **Update symlink after move:**
  ```bash
  ln -sfn /home/stas/projects/sintaris-srv/vps-admin/skills/skill-vps-change ~/.openclaw/skills/skill-vps-change
  ```

---

## Activity Log

**Log every Copilot-assisted server change** in `./docs/vps-activity-log.md` before session ends.

Format: `./docs/vps-activity-protocol.md`

```markdown
| # | Time (UTC) | Server | Action | Description | Risk | Result |
```

---

## OpenClaw (Local AI Gateway)

OpenClaw lives outside `vps-admin/` — do not move its artifacts here.

- **Project:** `../sinta-openclaw/`
- **Skills:** `../sinta-openclaw/skills/` symlinked to `~/.openclaw/skills/`
- **MCP server:** `~/.local/lib/openclaw-mcp/server.mjs`
- **Architecture:** `../sinta-openclaw/docs/architecture.md`
- **Install guide:** `../sinta-openclaw/docs/install.md`

---

## Documentation Rule

**Update docs whenever a service is installed, configured, or changed.**

| What changed | Update |
|---|---|
| dev2null.de service/config | `./docs/06-vps-dev2null.de.md` |
| dev2null.website service/config | `./docs/07-vps-dev2null.website.md` |
| VPS general setup procedure | `../docs/03-vps-server-setup.md` |
| N8N config | `../docs/05-n8n-vps-setup.md` |
| OpenClaw skill | `../sinta-openclaw/docs/architecture.md` |
| Any Copilot session with changes | `./docs/vps-activity-log.md` |
| New component in vps-admin | `./README.md` |

General doc index: `../docs/index.md`
