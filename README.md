# sintaris-srv

Administration, tooling and AI infrastructure for the Sintaris server.

## Subprojects

| Directory | Description |
|-----------|-------------|
| [vps-admin](./vps-admin/) | GitHub Copilot workspace for administering the VPS (nginx, PostgreSQL, n8n, EspoCRM, Nextcloud, mail) |
| [sinta-openclaw](./sinta-openclaw/) | OpenClaw AI gateway — skills, systemd services, MCP server, install guide |
| [local-dev](./local-dev/) | Local Docker stack: PostgreSQL 17 + pgvector + N8N |
| [docs](./docs/) | Installation guide and infrastructure documentation |
| [n8n](./n8n/) | N8N workflow exports and project files |

## Setup

```bash
# 1. VPS credentials
cp .env.example .env   # fill in VPS_HOST, VPS_USER, VPS_PASS

# 2. Local dev stack
cd local-dev && cp .env.example .env   # fill in DB passwords
docker compose up -d

# 3. OpenClaw AI gateway
cd sinta-openclaw && bash scripts/setup.sh
```

> All `.env` files are gitignored — never commit them.
