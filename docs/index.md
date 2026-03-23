# Sintaris Server — Installation Guide

This guide documents the complete setup of the Sintaris server infrastructure.
Keep it up to date whenever a new service or tool is installed.

## Contents

| File | Topic |
|------|-------|
| [01-github-setup.md](01-github-setup.md) | GitHub CLI, SSH keys, repository structure |
| [02-local-dev-environment.md](02-local-dev-environment.md) | Local Docker dev stack (PostgreSQL + N8N) |
| [03-vps-server-setup.md](03-vps-server-setup.md) | VPS: nginx, mail server, PostfixAdmin |
| [04-openclaw-setup.md](04-openclaw-setup.md) | OpenClaw / picoclaw local assistant |
| [05-n8n-vps-setup.md](05-n8n-vps-setup.md) | N8N production setup on VPS |

## Infrastructure Overview

```
Local machine (this computer)
  └── sintaris-srv/          git repo
        ├── local-dev/       Docker: PostgreSQL + N8N (localhost:5678)
        ├── vps-admin/       Copilot instructions for VPS management
        ├── docs/            This installation guide
        ├── n8n/             N8N workflow exports
        └── .env             VPS credentials (gitignored)

VPS: dev2null.de (152.53.224.213)
  ├── nginx                  Reverse proxy for all services
  ├── Postfix + Dovecot      Mail server (virtual domains via PostfixAdmin)
  ├── PostfixAdmin           Mail admin UI at https://mail.dev2null.de/admin/
  ├── Roundcube              Webmail at https://webmail.dev2null.de/
  ├── N8N (Docker)           Workflow automation at https://automata.dev2null.de/
  ├── EspoCRM (Docker)       CRM at https://crm.dev2null.de/
  ├── Nextcloud              File storage at https://cloud.dev2null.de/
  └── PostgreSQL             Database server (host install)
```

## Quick Start — VPS Admin

```bash
cd ~/projects/sintaris-srv
source .env
ssh ${VPS_USER}@${VPS_HOST}
```

## Quick Start — Local Dev

```bash
cd ~/projects/sintaris-srv/local-dev
docker compose up -d
# N8N: http://localhost:5678
# PostgreSQL: localhost:5432
```
