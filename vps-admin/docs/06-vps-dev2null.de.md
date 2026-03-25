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

## Open Ports & Services

### TCP — publicly reachable (0.0.0.0 / [::])

| Port | Protocol | Service | Process | Should be public? |
|------|----------|---------|---------|-------------------|
| 22 | TCP | SSH | sshd | ✅ Yes — key-auth only |
| 25 | TCP | SMTP (receive) | postfix | ✅ Yes — needed for incoming mail |
| 80 | TCP | HTTP | nginx | ✅ Yes — redirect to HTTPS + certbot |
| 110 | TCP | POP3 (unencrypted) | dovecot | ⚠️ Recommended: block — use 995 |
| 143 | TCP | IMAP (unencrypted) | dovecot | ⚠️ Recommended: block — use 993 |
| 443 | TCP | HTTPS | nginx | ✅ Yes — all web services |
| 587 | TCP | SMTP submission | postfix | ✅ Yes — mail clients send here |
| 993 | TCP | IMAPS | dovecot | ✅ Yes — encrypted mail |
| 995 | TCP | POP3S | dovecot | ✅ Yes — encrypted mail |
| 3000 | TCP | Metabase | docker-proxy | ⚠️ Should be localhost only — bind to 127.0.0.1 |
| 3478 | TCP+UDP | STUN/TURN | coturn | ✅ Yes — WebRTC (Nextcloud Talk) |
| 5349 | TCP+UDP | TURNS/STUNS | coturn | ✅ Yes — WebRTC TLS |
| 5432 | TCP | PostgreSQL | postgres | 🔴 **RISK** — database exposed to internet |
| 8000 | TCP | uvicorn (demo) | /home/stas/demos/taskctl/ | 🔴 **RISK** — demo app, not a production service |
| 8080 | TCP | Nextcloud direct | docker-proxy | ⚠️ Should be localhost — bypasses nginx SSL |
| 8081 | TCP | expert-tgrm-bot | docker-proxy | ⚠️ Should be localhost only |
| 8083 | TCP | bot_assistance | docker-proxy | ⚠️ Should be localhost only |
| 8888 | TCP | EspoCRM direct | docker-proxy | ⚠️ Should be localhost — bypasses nginx SSL |

### TCP — localhost only (safe, not reachable from internet)

| Port | Service | Process |
|------|---------|---------|
| 53 | DNS resolver | systemd-resolved |
| 783 | SpamAssassin | spamd |
| 3306 | MySQL | mysqld |
| 5678 | N8N | docker-proxy (127.0.0.1 binding — good) |
| 9080 | PGAdmin | docker-proxy (127.0.0.1 binding — good) |
| 33060 | MySQL X Protocol | mysqld |

---

## Nginx Virtual Hosts

| Domain | HTTP | HTTPS | Backend |
|--------|------|-------|---------|
| cloud.dev2null.de | ✅ redirect | ✅ | Nextcloud (8080) |
| cloud.sintaris.eu | ✅ redirect | ✅ | Nextcloud (8080) |
| cloud.sintaris.net | ✅ redirect | ✅ | Nextcloud (8080) |
| automata.dev2null.de | ✅ redirect | — | N8N (5678, localhost) |
| apps.dev2null.de | ✅ | — | N8N (5678) |
| crm.dev2null.de | ✅ | — | EspoCRM (8888) |
| crm.sintaris.net | ✅ redirect | ✅ | EspoCRM (8888) |
| mail.dev2null.de | ✅ redirect | ✅ | Roundcube (php-fpm) |
| webmail.dev2null.de | ✅ | — | Roundcube |
| webmail.sintaris.eu | ✅ | — | Roundcube |
| webmail.sintaris.net | ✅ | — | Roundcube |
| webmail.sintaru.com | ✅ | — | Roundcube |
| mail.sintaris.net | ✅ | ✅ (shared) | Roundcube |
| mail.sintaris.eu | ✅ | ✅ (shared) | Roundcube |
| mail.sintaru.com | ✅ | ✅ (shared) | Roundcube |
| db.dev2null.de | ✅ | — | PGAdmin (9080, localhost) |
| dbview.dev2null.de | ✅ | — | PGAdmin (9080) |
| pg.dev2null.de | ✅ | — | PGAdmin |
| agents.sintaris.net | ✅ redirect | ✅ | OpenClaw |
| control.sintaris.net | ✅ | — | Management UI |
| sintaris.eu / www | ✅ | — | Web |
| sintaris.net / www | ✅ | — | Web |
| sintaru.com / www | ✅ | — | Web |
| wp.sintaris.eu | ✅ | — | WordPress |
| wp.sintaris.net | ✅ | ✅ | WordPress |
| sqliteweb.dev2null.de | ✅ | — | SQLite Web viewer |

---

## Security

| Component | Details |
|-----------|---------|
| fail2ban | Active — **SSH only** (1 jail). Postfix, dovecot, nginx NOT protected. |
| coturn | TURN/STUN server — ports 3478 (UDP/TCP), 5349 (TLS) |
| SSL | Let's Encrypt via certbot, auto-renewed |
| **UFW** | **⚠️ INACTIVE — no software firewall running** |
| SSH | Key-based auth only, password auth disabled |

### ⚠️ Security issues found (2026-03-25 audit)

| Severity | Issue | Recommendation |
|----------|-------|----------------|
| 🔴 HIGH | UFW is inactive — no firewall | Enable UFW with rules below |
| 🔴 HIGH | PostgreSQL (5432) exposed to internet | Block in UFW; bind to 127.0.0.1 in postgres config |
| 🔴 HIGH | Demo app uvicorn:8000 exposed | Stop or bind to 127.0.0.1 |
| ⚠️ MED | Metabase (3000) exposed to internet | Bind docker to 127.0.0.1:3000 in compose |
| ⚠️ MED | Nextcloud (8080) directly reachable | Bind docker to 127.0.0.1:8080 in compose |
| ⚠️ MED | EspoCRM (8888) directly reachable | Bind docker to 127.0.0.1:8888 in compose |
| ⚠️ MED | Bot ports 8081, 8083 exposed | Bind docker to 127.0.0.1 in compose |
| ⚠️ LOW | POP3 (110) and IMAP (143) unencrypted | Block in UFW — clients should use 993/995 |
| ⚠️ LOW | fail2ban only protects SSH | Add jails: postfix, dovecot, nginx |
| ⚠️ LOW | Docker bypasses UFW by default | Use DOCKER-USER iptables chain or bind ports to 127.0.0.1 |

### Recommended UFW configuration

```bash
# Reset and set defaults
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# === PUBLIC SERVICES ===
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 25/tcp comment 'SMTP - receive mail'
sudo ufw allow 80/tcp comment 'HTTP - nginx + certbot'
sudo ufw allow 443/tcp comment 'HTTPS - nginx'
sudo ufw allow 587/tcp comment 'SMTP submission - mail clients'
sudo ufw allow 993/tcp comment 'IMAPS - encrypted mail'
sudo ufw allow 995/tcp comment 'POP3S - encrypted mail'
sudo ufw allow 3478 comment 'STUN/TURN - Nextcloud Talk WebRTC'
sudo ufw allow 5349 comment 'TURNS/STUNS - Nextcloud Talk WebRTC TLS'

# === BLOCK UNENCRYPTED MAIL ===
# (clients should use 993/995 instead)
# sudo ufw deny 110 comment 'POP3 unencrypted - use 995'
# sudo ufw deny 143 comment 'IMAP unencrypted - use 993'

# Enable
sudo ufw --force enable
sudo ufw status verbose
```

> **⚠️ Docker bypass warning:** UFW rules alone do NOT block Docker-exposed ports.  
> Docker adds its own iptables rules (DOCKER chain) that run before UFW's rules.  
> To properly restrict Docker ports to localhost-only, bind them in `docker-compose.yml`:
> ```yaml
> ports:
>   - "127.0.0.1:8080:80"  # instead of "8080:80"
> ```
> This applies to: Nextcloud (8080), EspoCRM (8888), Metabase (3000), bots (8081, 8083).

### Recommended docker-compose port binding fixes

For each service that should NOT be directly accessible from the internet:

```bash
# dev2null.de — services to restrict to localhost
# Edit each compose file and change port bindings:

# Nextcloud /opt/nextcloud-docker/docker-compose.yml
#   "8080:80"  →  "127.0.0.1:8080:80"

# EspoCRM /opt/espocrm/docker-compose.yml
#   "8888:80"  →  "127.0.0.1:8888:80"

# Metabase /opt/metabase/docker-compose.yml
#   "3000:3000"  →  "127.0.0.1:3000:3000"

# Expert bot /opt/bots/expert-tgrm-bot/docker-compose.yml
#   "8081:8080"  →  "127.0.0.1:8081:8080"

# Assistance bot /opt/bots/gpt-tgrm-bot/.../docker-compose.yml
#   "8083:8082"  →  "127.0.0.1:8083:8082"
```

### Recommended fail2ban jails to add

```bash
# /etc/fail2ban/jail.local
[postfix]
enabled = true
port = smtp,465,587
logpath = /var/log/mail.log
maxretry = 5

[dovecot]
enabled = true
port = pop3,pop3s,imap,imaps,submission,993,995
logpath = /var/log/mail.log
maxretry = 5

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
```

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
