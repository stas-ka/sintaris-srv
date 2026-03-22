# sintaris-srv

Administration and tooling for the Sintaris VPS server.

## Subprojects

| Directory | Description |
|-----------|-------------|
| [vps-admin](./vps-admin/) | GitHub Copilot workspace for administering the VPS (nginx, PostgreSQL, n8n, WordPress, EspoCRM, Nextcloud, mail server) |

## Setup

Copy `.env.example` to `.env` and fill in your server credentials:

```bash
cp .env.example .env
```

> `.env` is gitignored and must never be committed.
