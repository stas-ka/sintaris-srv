# VPS Admin

GitHub Copilot workspace for administering the VPS server.

## Usage

```bash
cd ~/projects/sintaris-srv/vps-admin
```

Copilot automatically loads `.github/copilot-instructions.md` — full context about the server stack. Credentials from `../.env`.

## Related subprojects

| Directory | Description |
|---|---|
| [../sinta-openclaw](../sinta-openclaw/) | OpenClaw AI gateway (skills, services, MCP) |
| [../local-dev](../local-dev/) | Local Docker stack (PostgreSQL + N8N) |
| [../docs](../docs/) | Infrastructure documentation |

## Server Stack

- **nginx** — web server / reverse proxy
- **PostgreSQL** — databases
- **n8n** — workflow automation (Docker at `/opt/n8n-docker/`)
- **EspoCRM** — CRM at `crm.dev2null.de`
- **Nextcloud** — file storage at `cloud.dev2null.de`
- **Mail server** — Postfix/Dovecot, managed via PostfixAdmin

## Example Prompts

- *"Check the status of all services"*
- *"Show nginx error logs from the last hour"*
- *"List all PostgreSQL databases and their sizes"*
- *"Check disk space and memory usage"*
- *"Renew SSL certificates"*
