# VPS Admin

Copilot workspace for administering the VPS server.

## Usage

Open this directory in GitHub Copilot CLI:

```bash
cd ~/projects/sintaris-srv/vps-admin
copilot
```

Copilot will automatically load `.github/copilot-instructions.md` which gives it
full context about the server stack. Credentials are read from `../.env`.

## Server Stack

- **nginx** — web server / reverse proxy
- **PostgreSQL** — databases
- **n8n** — workflow automation
- **WordPress** — CMS
- **EspoCRM** — CRM
- **Nextcloud** — file storage
- **Mail server** — email (Postfix/Dovecot)

## Setup

Credentials are stored in `../.env` (gitignored). See `../.env.example` for required variables.

## Example Prompts

- *"Check the status of all services"*
- *"Show nginx error logs from the last hour"*
- *"List all PostgreSQL databases and their sizes"*
- *"Check disk space and memory usage"*
- *"Show me the nginx site configs"*
- *"Renew SSL certificates"*
- *"Check if n8n is running and show recent logs"*
