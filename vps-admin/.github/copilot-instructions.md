# VPS Admin — Copilot Instructions

## Server

Connection details are stored in `../.env` (gitignored). Load them before running SSH commands:

```bash
source ../.env
# Then use: ssh ${VPS_USER}@${VPS_HOST}
```

- **OS:** Ubuntu Server

## Stack

| Service     | Notes |
|-------------|-------|
| **nginx**   | Web server / reverse proxy |
| **PostgreSQL** | Database server |
| **n8n**     | Workflow automation |
| **WordPress** | CMS site(s) |
| **EspoCRM** | CRM application |
| **Nextcloud** | File storage / collaboration |
| **Mail server** | Email (check `/etc/postfix`, `/etc/dovecot`) |

## How to Work

- Load credentials: `source ../.env`
- Connect via SSH: `ssh ${VPS_USER}@${VPS_HOST}`
- Run commands remotely: `ssh ${VPS_USER}@${VPS_HOST} 'command here'`
- Use `sudo` for privileged operations
- Prefer non-destructive, reversible commands; confirm before deleting data
- When editing config files, back them up first (e.g. `cp file file.bak`)

## Common Tasks

### Services
```bash
source ../.env
# Status of all services
ssh ${VPS_USER}@${VPS_HOST} 'sudo systemctl status nginx postgres n8n'

# Restart a service
ssh ${VPS_USER}@${VPS_HOST} 'sudo systemctl restart <service>'

# View logs
ssh ${VPS_USER}@${VPS_HOST} 'sudo journalctl -u <service> -n 100 --no-pager'
```

### nginx
```bash
source ../.env
ssh ${VPS_USER}@${VPS_HOST} 'sudo nginx -t'
ssh ${VPS_USER}@${VPS_HOST} 'sudo systemctl reload nginx'
ssh ${VPS_USER}@${VPS_HOST} 'ls /etc/nginx/sites-enabled/'
```

### PostgreSQL
```bash
source ../.env
ssh ${VPS_USER}@${VPS_HOST} 'sudo -u postgres psql'
ssh ${VPS_USER}@${VPS_HOST} 'sudo -u postgres psql -c "\l"'
```

### System Health
```bash
source ../.env
ssh ${VPS_USER}@${VPS_HOST} 'df -h && free -h'
ssh ${VPS_USER}@${VPS_HOST} 'sudo systemctl --failed'
```

### Firewall (ufw)
```bash
source ../.env
ssh ${VPS_USER}@${VPS_HOST} 'sudo ufw status verbose'
```

## Notes

- n8n runs in Docker at `/opt/n8n-docker/` — manage with `sudo docker compose`
- EspoCRM runs in Docker (`docker ps | grep espo`) at `crm.dev2null.de`
- Nextcloud config: `/var/www/nextcloud/config/config.php` or Docker volume
- WordPress sites: typically under `/var/www/`
- SSL certificates: managed by Let's Encrypt (`/etc/letsencrypt/`)
- PostfixAdmin: `https://mail.dev2null.de/admin/` — manage all mailboxes here
- Mail stored as Maildir in `/var/mail/vhosts/<domain>/<user>/`

## OpenClaw (Local AI Gateway)

OpenClaw is the local AI gateway (Node.js). **Not** picoclaw (Python bot — leave that untouched).

- **Project:** `../sinta-openclaw/` — all OpenClaw artifacts live here
- **Config:** `~/.openclaw/openclaw.json` — secrets not in git
- **Skills:** `../sinta-openclaw/skills/` symlinked to `~/.openclaw/skills/`
- **Services:** `openclaw-gateway.service`, `openclaw-tunnel.service` (systemd user services)
- **Web UI:** https://agents.sintaris.net/openclaw/
- **MCP server:** `~/.local/lib/openclaw-mcp/server.mjs` (source in `../sinta-openclaw/mcp/`)
- **Architecture:** `../sinta-openclaw/docs/architecture.md`
- **Install guide:** `../sinta-openclaw/docs/install.md`

### When working on OpenClaw:
- New skill → create in `../sinta-openclaw/skills/skill-xxx/SKILL.md`, symlink to `~/.openclaw/skills/`
- Config change → use `openclaw config set key value`, update `../sinta-openclaw/config/openclaw.json.template`
- New service → copy template to `../sinta-openclaw/systemd/`, install to `~/.config/systemd/user/`
- **Always update** `../sinta-openclaw/docs/architecture.md` after any structural change

## Sensitive Data Rule

**ALL credentials, passwords, tokens, and secrets must go in `.env` ONLY — never in documentation, code, or any file that is committed to git.**

- `.env` is gitignored — this is the only place for real values
- `.env.example` contains placeholder keys with empty values — commit only this
- Documentation must use placeholder notation like `${VPS_PASS}` or `<password>` — never real values
- This applies to: SSH passwords, API tokens, bot tokens, DB passwords, setup passwords, and any secret

## Servers

| Host | IP | User | Auth | Role |
|------|----|------|------|------|
| dev2null.de | 152.53.224.213 | stas | SSH key (`~/.ssh/id_ed25519`) | Main production VPS — **HIGHEST PRIORITY** |
| dev2null.website | 82.165.231.93 | boh | password (in `.env` as `WEB_PASS`) | VPN/proxy server |

> ⚠️ **dev2null.de is a live production server.** Always back up config before changes. Prefer `reload` over `restart`. Test with `--dry-run` or `-t` where possible.

SSH helpers:
```bash
source ../.env
# dev2null.de
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST}
# dev2null.website (password auth via sshpass or paramiko)
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST}
```

## Documentation Rule

**Always update docs when installing or configuring a new service, tool, or infrastructure component.**

| What changed | Where to update |
|---|---|
| VPS service | `../docs/03-vps-server-setup.md` |
| N8N config | `../docs/05-n8n-vps-setup.md` |
| OpenClaw skill / integration | `../sinta-openclaw/docs/architecture.md` + `../sinta-openclaw/docs/install.md` |
| New local tool | Relevant file in `../docs/` |
| Completely new component | New file in `../docs/` or `../sinta-openclaw/docs/` |

The guide index is at `../docs/index.md`.
