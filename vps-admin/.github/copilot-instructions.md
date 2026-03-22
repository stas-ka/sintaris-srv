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

- n8n likely runs as a systemd service or via Docker — verify with `systemctl status n8n` or `docker ps`
- Nextcloud config: `/var/www/nextcloud/config/config.php` or Docker volume
- WordPress sites: typically under `/var/www/`
- EspoCRM: typically under `/var/www/`
- SSL certificates: managed by Let's Encrypt (`/etc/letsencrypt/`)
