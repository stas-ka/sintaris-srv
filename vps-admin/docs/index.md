# Sintaris Server — Installation Guide

This guide documents the complete setup of the Sintaris server infrastructure.
Keep it up to date whenever a new service or tool is installed.

## Contents

| File | Topic |
|------|-------|
| [01-github-setup.md](01-github-setup.md) | GitHub CLI, SSH keys, repository structure |
| [02-local-dev-environment.md](02-local-dev-environment.md) | Local Docker dev stack (PostgreSQL + N8N) |
| [03-vps-server-setup.md](03-vps-server-setup.md) | VPS: nginx, mail server, PostfixAdmin |
| [04-openclaw-setup.md](04-openclaw-setup.md) | OpenClaw AI gateway (Node.js) — see also `../sinta-openclaw/` |
| [05-n8n-vps-setup.md](05-n8n-vps-setup.md) | N8N production setup on VPS |

> **VPS-specific docs** (server maps, change log, monitoring) have moved to [`../vps-admin/docs/`](../vps-admin/docs/)

| File | Topic |
|------|-------|
| [vps-admin/docs/06-vps-dev2null.de.md](../vps-admin/docs/06-vps-dev2null.de.md) | Full infrastructure map — dev2null.de (disaster recovery) |
| [vps-admin/docs/07-vps-dev2null.website.md](../vps-admin/docs/07-vps-dev2null.website.md) | VPN/proxy server — dev2null.website |
| [vps-admin/docs/vps-activity-protocol.md](../vps-admin/docs/vps-activity-protocol.md) | Protocol for logging Copilot-assisted server changes |
| [vps-admin/docs/vps-activity-log.md](../vps-admin/docs/vps-activity-log.md) | Running log of all server changes |

## Infrastructure Overview

```
Local machine (this computer)
  └── sintaris-srv/          git repo
        ├── local-dev/       Docker: PostgreSQL + N8N (localhost:5678)
        ├── sinta-openclaw/  OpenClaw AI gateway (Node.js) — skills, services, MCP
        ├── vps-admin/       ALL VPS admin: docs, monitoring, copilot-notify, skills
        │     ├── docs/      Server maps, activity log, change protocol
        │     ├── monitoring/ Health-check daemon (deployed to both VPS)
        │     ├── copilot-notify/ MCP server — Copilot ↔ Telegram notifications
        │     └── skills/    OpenClaw skills for server operations
        ├── docs/            General setup guides (GitHub, local-dev, OpenClaw)
        ├── n8n/             N8N workflow exports
        └── .env             All credentials (gitignored)

dev2null.de (152.53.224.213) — PRODUCTION — Ubuntu 24.04 / aarch64
  ├── nginx                  Reverse proxy — 20+ virtual hosts
  ├── Postfix + Dovecot      Mail server (PostfixAdmin + SpamAssassin + OpenDKIM)
  ├── Roundcube              Webmail at https://webmail.dev2null.de/
  ├── N8N (Docker)           Workflow automation at https://automata.dev2null.de/
  ├── EspoCRM (Docker)       CRM at https://crm.dev2null.de/
  ├── Nextcloud (Docker)     File storage at https://cloud.dev2null.de/
  ├── Metabase (Docker)      Analytics (port 3000)
  ├── Telegram bots (Docker) expert-tgrm-bot, bot_assistance
  ├── PGAdmin (Docker)       DB admin at https://db.dev2null.de/
  ├── MySQL 8.0              Mail/Nextcloud/Roundcube DBs
  ├── PostgreSQL 17          App DBs (n8n, espocrm, pgvector)
  ├── coturn                 TURN/STUN server
  └── sintaris-monitor       Monitoring → Telegram alerts

dev2null.website (82.165.231.93) — VPN/PROXY — Ubuntu 22.04 / x86_64
  ├── nginx                  Reverse proxy
  ├── amnezia-wg-easy (Docker)  AmneziaWG VPN
  ├── xray                   Proxy (ports 9443, 9444)
  ├── x-ui                   Xray management panel
  └── sintaris-monitor       Monitoring → Telegram alerts
```

## Quick Start — VPS Admin

```bash
cd ~/projects/sintaris-srv
source .env

# dev2null.de (SSH key)
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST}

# dev2null.website (password)
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST}
```

## Quick Start — Local Dev

```bash
cd ~/projects/sintaris-srv/local-dev
docker compose up -d
# N8N: http://localhost:5678
# PostgreSQL: localhost:5432
```
