# VPS — dev2null.de (Production)

Primary production server. Hosts mail, Nextcloud, N8N, EspoCRM, Metabase, bots, and all customer-facing domains.

> **⚠️ Production server — all changes must be logged in `docs/vps-activity-protocol.md`**

---

## Server Specs

| Property | Value |
|----------|-------|
| Host | dev2null.de |
| IP | 152.53.224.213 |
| OS | Ubuntu 24.04.2 LTS (Noble Numbat) — aarch64 |
| CPU | 6 cores |
| RAM | 7.7 GB |
| Disk | 504 GB total — 219 GB used, 265 GB free (46%) |
| Swap | 8 GB |
| SSH | Key auth only — user `stas`, key `~/.ssh/id_ed25519` |

```bash
ssh stas@dev2null.de
```

---

## System Services

All services are enabled and running:

| Service | Role |
|---------|------|
| nginx | Reverse proxy / web server |
| postfix | MTA (outgoing mail) |
| dovecot | IMAP / POP3 |
| mysql 8.0 | Relational DB (nextcloud, roundcube, postfixadmin) |
| postgresql@17-main | PostgreSQL 17 with pgvector extension |
| docker | Container runtime |
| fail2ban | Brute-force protection |
| coturn | TURN/STUN server (WebRTC) |
| opendkim | DKIM signing for outgoing mail |
| php8.3-fpm | PHP FastCGI (Roundcube, etc.) |
| spamassassin | Spam filter |
| roundcube | Webmail (served via php8.3-fpm) |

---

## Docker Containers

| Container | Image | Port | URL |
|-----------|-------|------|-----|
| nextcloud-docker-app-1 | nextcloud | 8080 | https://cloud.dev2null.de |
| nextcloud-docker-db-1 | mariadb | 3306 (internal) | — |
| n8n-docker-n8n-1 | n8n:1.113.3 | 5678 | https://automata.dev2null.de |
| n8n-runners | worksafety-runners | 5680 | — (internal) |
| expert-tgrm-bot | expert-tgrm-bot | 8081 | — |
| bot_assistance | universal-tgrm-bot | 8083 | — |
| espocrm | espocrm/espocrm | 8888 | https://crm.dev2null.de |
| metabase | metabase/metabase | 3000 | — |
| pgadmin-pgadmin-1 | pgadmin4 | 9080 | https://db.dev2null.de |

### Docker Compose Locations

| Service | Path |
|---------|------|
| Nextcloud | `/opt/nextcloud-docker/docker-compose.yml` |
| N8N | `/opt/n8n-docker/docker-compose.yml` |
| EspoCRM | `/opt/espocrm/docker-compose.yml` |
| Metabase | `/opt/metabase/docker-compose.yml` |
| PGAdmin | `/opt/pgadmin/docker-compose.yml` |
| Expert bot | `/opt/bots/expert-tgrm-bot/docker-compose.yml` |
| Assistance bot | `/opt/bots/gpt-tgrm-bot/universal-tgrm-bot/docker-compose.yml` |

---

## Nginx Virtual Hosts

| Domain | Backend | Notes |
|--------|---------|-------|
| cloud.dev2null.de | localhost:8080 | Nextcloud |
| automata.dev2null.de | localhost:5678 | N8N |
| crm.dev2null.de | localhost:8888 | EspoCRM |
| mail.dev2null.de | php-fpm | Roundcube webmail |
| webmail.dev2null.de | php-fpm | Roundcube webmail |
| webmail.sintaris.eu | php-fpm | Roundcube webmail |
| webmail.sintaris.net | php-fpm | Roundcube webmail |
| webmail.sintaru.com | php-fpm | Roundcube webmail |
| db.dev2null.de | localhost:9080 | PGAdmin |
| dbview.dev2null.de | localhost:9080 | PGAdmin |
| cloud.sintaris.eu | localhost:8080 | Nextcloud |
| cloud.sintaris.net | localhost:8080 | Nextcloud |
| crm.sintaris.net | localhost:8888 | EspoCRM |
| agents.sintaris.net | — | OpenClaw |
| control.sintaris.net | — | Management UI |
| apps.dev2null.de | localhost:5678 | N8N |
| wp.sintaris.eu | — | WordPress |
| wp.sintaris.net | — | WordPress |
| sintaris.eu | — | Web |
| sintaris.net | — | Web |
| sintaru.com | — | Web |

---

## Databases

### MySQL 8.0 — localhost:3306
```
Databases: nextcloud, roundcube, postfixadmin
User: <mysql_user>
Password: ${MYSQL_PASS}
```

### PostgreSQL 17 — localhost:5432 (pgvector enabled)
```
Databases: n8n, espocrm, app DBs
User: <pg_user>
Password: ${PG_PASS}
```

### MariaDB (Docker) — nextcloud-docker-db-1
```
Internal port: 3306
Used by: Nextcloud Docker instance
Password: ${NEXTCLOUD_DB_PASS}
```

---

## Mail Stack

- **Postfix** — MTA, outgoing and incoming mail
- **Dovecot** — IMAP / POP3 server
- **SpamAssassin** — spam filtering
- **OpenDKIM** — DKIM signing for authenticated outgoing mail

| Component | URL / Path |
|-----------|-----------|
| PostfixAdmin | https://mail.dev2null.de/admin/ |
| Roundcube | https://mail.dev2null.de |
| Mailboxes | `/var/mail/vhosts/<domain>/<user>/` (Maildir format) |

---

## Security

| Component | Details |
|-----------|---------|
| fail2ban | Active — protects SSH, mail (postfix/dovecot), and web |
| coturn | TURN/STUN server — ports 3478 (UDP/TCP), 5349 (TLS) |
| SSL | Let's Encrypt via certbot, auto-renewed |
| UFW | Active firewall |
| SSH | Key-based auth only, password auth disabled |

---

## Monitoring

- **Service:** `sintaris-monitor` (systemd timer, runs every 5 min)
- **Script:** `/opt/sintaris-monitor/monitor.py`
- **Config:** `/opt/sintaris-monitor/.env` — secrets stored here (see main `.env` for values)
- **Daily report:** 08:00 UTC via Telegram

```bash
# Check monitor status
systemctl status sintaris-monitor.timer
systemctl status sintaris-monitor.service
journalctl -u sintaris-monitor.service -n 50
```

---

## Backup

- **Scripts:** `/opt/sintaris-backup/` (deployed via `vps-admin/backup/install.sh`)
- **Config:** `/opt/sintaris-backup/.env`
- **Schedule:** daily at 02:00 UTC (± 15 min)
- **Storage:** `/opt/sintaris-backup-data/` (persistent, survives reboots)
- **Retention:** 7 days

Backup targets: configs (nginx/postfix/ssl/fail2ban), MySQL, PostgreSQL, Docker compose + volumes, /opt

> ⚠️ **Nextcloud data volume excluded from automated backups.**  
> The `nextcloud-docker_nextcloud` volume is **~147 GB** — too large for daily rotation.  
> Set `VOLUMES_SKIP=nextcloud-docker_nextcloud` in `.env` to skip it.

```bash
# Run backup manually (on server)
sudo /opt/sintaris-backup/backup.sh

# Dry-run (no changes)
sudo /opt/sintaris-backup/backup.sh --dry-run

# List available backups
sudo /opt/sintaris-backup/recover.sh list

# Restore from date
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25

# Check timer
systemctl status sintaris-backup.timer
```

### Manual Nextcloud data backup (to USB)

```bash
# Pipe 147 GB Nextcloud volume directly to local USB — takes ~2 hours
source ~/.../sintaris-srv/.env
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo tar -czf - -C /var/lib/docker/volumes/nextcloud-docker_nextcloud/_data .' \
  > /media/stas/Linux-Backup/dev2null.de/nextcloud/nextcloud-data-$(date +%Y-%m-%d).tar.gz
```

See `vps-admin/backup/README.md` for full USB backup workflow.

---

## Recovery / New Host Install

Order of installation steps when provisioning a fresh server:

1. **Ubuntu 24.04 LTS** — base install, locale, timezone, hostname
2. **SSH hardening** — disable password auth, add SSH key, configure `sshd_config`
3. **nginx + certbot** — install nginx, configure firewall (UFW), obtain SSL certs
4. **Postfix + Dovecot + PostfixAdmin + SpamAssassin + OpenDKIM** — full mail stack
5. **MySQL 8.0 + PostgreSQL 17** — install both, enable pgvector extension
6. **PHP 8.3-fpm + Roundcube** — PHP FastCGI pool, Roundcube webmail config
7. **Docker + compose plugin** — install Docker Engine and compose plugin
8. **Deploy containers** — nextcloud, n8n, espocrm, metabase, pgadmin, bots
9. **coturn** — TURN/STUN for WebRTC (Nextcloud Talk, etc.)
10. **fail2ban** — configure jails for SSH, postfix, dovecot, nginx
11. **Monitoring** — deploy `sintaris-monitor` systemd timer
12. **Backup** — deploy `sintaris-backup` via `backup/install.sh`, mount backup storage
13. **Restore data from backups** — `recover.sh restore`, then restart services
