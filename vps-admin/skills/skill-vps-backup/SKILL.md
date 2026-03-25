---
name: skill-vps-backup
description: Backup and recovery operations for Sintaris VPS servers (dev2null.de, dev2null.website). Covers running backups, listing available backups, restoring specific targets, checking backup health, and emergency recovery procedures.
---

# skill-vps-backup

Use this skill whenever Copilot is asked to backup, restore, or check backup status on VPS servers.

> **dev2null.de is production.** Always prefer `--dry-run` first. Never restore on production without owner confirmation.

---

## Architecture Overview

| Component | Location on VPS | Purpose |
|-----------|----------------|---------|
| `backup.sh` | `/opt/sintaris-backup/backup.sh` | Main backup script |
| `recover.sh` | `/opt/sintaris-backup/recover.sh` | Restore script |
| `notify-event.sh` | `/opt/sintaris-backup/notify-event.sh` | System event alerts |
| Config | `/opt/sintaris-backup/.env` | Tokens, mount path, retention |
| State | `/opt/sintaris-backup/.last_backup` | ISO timestamp of last success |
| Timer | `sintaris-backup.timer` | Daily at 02:00 UTC |
| Mount | `$BACKUP_MOUNT` (e.g. `/mnt/backup`) | Where archives are stored |

**Source:** `vps-admin/backup/` in the `sintaris-srv` repository  
**Deploy:** `bash vps-admin/backup/install.sh dev2null.de` or `dev2null.website`

---

## Backup Targets

| Target | What is backed up |
|--------|------------------|
| `configs` | nginx, SSL certs, Postfix/Dovecot, OpenDKIM, HAProxy, x-ui |
| `mysql` | All MySQL/MariaDB databases (mysqldump per DB) |
| `postgres` | All PostgreSQL databases (pg_dump per DB) |
| `docker` | Docker Compose files + named volumes per stack |
| `mail` | Mail data `/var/mail/vhosts/` (opt-in: `BACKUP_MAIL_DATA=yes`) |
| `opt` | `/opt` runtime directories |
| `all` | All of the above (default) |

### Excluded volumes

`nextcloud-docker_nextcloud` (~30 GB of user files) is **excluded** from automated backups via `VOLUMES_SKIP` in `.env`. Back it up manually when needed (see [Backup Nextcloud data manually](#backup-nextcloud-data-manually)).

---

## SSH Access

```bash
source ../.env   # loads VPS_USER, VPS_HOST, WEB_USER, WEB_HOST, WEB_PASS

# dev2null.de (key auth)
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST}

# dev2null.website (password auth via paramiko — sshpass not available)
python3 -c "
import paramiko
from pathlib import Path
lines = {k.strip(): v.strip().strip('\"').strip(\"'\") for line in Path('../.env').read_text().splitlines()
         if (line.strip() and not line.startswith('#') and '=' in line) for k,v in [line.split('=',1)]}
client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(lines['WEB_HOST'], username=lines['WEB_USER'], password=lines['WEB_PASS'], look_for_keys=False)
"
```

---

## Running a Backup

### Full backup (all targets)
```bash
# dev2null.de
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo /opt/sintaris-backup/backup.sh'

# dev2null.website
# (run via paramiko interactive shell — see SSH Access above)
echo '${WEB_PASS}' | sudo -S /opt/sintaris-backup/backup.sh
```

### Dry run first (ALWAYS do this before a real backup)
```bash
sudo /opt/sintaris-backup/backup.sh --dry-run
```

### Single target
```bash
sudo /opt/sintaris-backup/backup.sh --target mysql
sudo /opt/sintaris-backup/backup.sh --target postgres
sudo /opt/sintaris-backup/backup.sh --target docker
sudo /opt/sintaris-backup/backup.sh --target configs
```

### Backup Nextcloud data manually

`nextcloud-docker_nextcloud` is excluded from automated runs (it is ~30 GB). Back up manually when needed:

```bash
DEST=/mnt/sintaris-backup/backups/mail.dev2null.de/manual
sudo mkdir -p $DEST
sudo docker run --rm \
  -v nextcloud-docker_nextcloud:/data:ro \
  -v $DEST:/backup \
  alpine tar -czf /backup/nextcloud-docker_nextcloud-$(date +%Y-%m-%d).tar.gz /data
```

### Running from local machine → USB disk

When no permanent mount is configured on the VPS, run backup to `/tmp` on VPS then rsync to local USB:

```bash
source ../.env

# Run in background on VPS (nohup — survives SSH disconnect)
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo mkdir -p /tmp/sintaris-backup/backups /tmp/sintaris-backup/logs && \
   sudo chmod 777 /tmp/sintaris-backup/logs && \
   nohup sudo BACKUP_MOUNT=/tmp/sintaris-backup /opt/sintaris-backup/backup.sh \
   > /tmp/sintaris-backup/logs/backup-stdout.log 2>&1 &'

# Monitor progress
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'tail -f /tmp/sintaris-backup/logs/backup-stdout.log'

# Rsync to USB when complete
rsync -avz --progress \
  -e "ssh -i ~/.ssh/id_ed25519" \
  stas@${VPS_HOST}:/tmp/sintaris-backup/ \
  /media/stas/Linux-Backup/dev2null.de/

# Clean up on VPS
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo rm -rf /tmp/sintaris-backup'
```

---

## Checking Backup Status

### Check last backup timestamp
```bash
cat /opt/sintaris-backup/.last_backup
# Returns ISO timestamp e.g. 2026-03-25T02:01:33
```

### List available backups
```bash
sudo /opt/sintaris-backup/recover.sh list
```

### Timer status
```bash
systemctl status sintaris-backup.timer
systemctl list-timers sintaris-backup.timer
journalctl -u sintaris-backup.service -n 50 --no-pager
```

### Monitor check (alerts if backup >2 days old)
```bash
sudo python3 /opt/sintaris-monitor/monitor.py check
```

---

## Recovery Procedure

> ⚠️ **CRITICAL — requires owner confirmation before execution on production.**  
> Always `--dry-run` first. Always confirm which date to restore from.

### Step 1 — List available backups
```bash
sudo /opt/sintaris-backup/recover.sh list
```
Output example:
```
Available backups for dev2null.de:
  2026-03-25  (configs mysql postgres docker)
  2026-03-24  (configs mysql postgres docker)
```

### Step 2 — Dry run the restore
```bash
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --dry-run
# or single target:
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --target mysql --dry-run
```

### Step 3 — Confirm with owner, then restore
```bash
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25
# or single target:
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --target postgres
```

### Step 4 — Verify services after restore
```bash
sudo systemctl status nginx postgresql@17-main mysql docker
sudo docker ps
# Check application endpoints:
curl -s https://cloud.dev2null.de/status.php | python3 -m json.tool
curl -s https://automata.dev2null.de/healthz
curl -I https://crm.dev2null.de/
```

---

## Recovery by Target

### MySQL (Nextcloud, Roundcube, PostfixAdmin)
```bash
sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target mysql
# Restores all DB dumps; existing DBs are dropped and recreated
sudo systemctl restart mysql
# Verify:
sudo mysql -e "SHOW DATABASES;"
```

### PostgreSQL (N8N, EspoCRM, pgvector DBs)
```bash
sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target postgres
sudo systemctl restart postgresql@17-main
# Verify:
sudo -u postgres psql -c "\l"
```

### Docker stacks (Nextcloud, N8N, EspoCRM, bots)
```bash
sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target docker
# Stacks are stopped, volumes restored, stacks restarted
# Verify:
sudo docker ps
```

### Configs (nginx, SSL, mail, x-ui)
```bash
sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target configs
sudo nginx -t && sudo systemctl reload nginx
```

---

## Emergency: Full Server Recovery from Scratch

Use this when recovering onto a new/reinstalled VPS.

1. **Install base OS and dependencies** (see `docs/06-vps-dev2null.de.md` — Setup section)

2. **Mount backup storage**
   ```bash
   sudo mount /dev/sdX /mnt/backup   # or NFS/S3
   ```

3. **Copy backup scripts**
   ```bash
   sudo mkdir -p /opt/sintaris-backup
   sudo cp backup.sh recover.sh /opt/sintaris-backup/
   sudo cp backup.env.example /opt/sintaris-backup/.env
   # Fill in BACKUP_MOUNT, TG_BOT_TOKEN, TG_CHAT_ID
   ```

4. **Restore configs first** (nginx, SSL, Postfix)
   ```bash
   sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target configs
   ```

5. **Restore databases**
   ```bash
   sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target mysql
   sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target postgres
   ```

6. **Restore Docker stacks**
   ```bash
   sudo /opt/sintaris-backup/recover.sh restore --date YYYY-MM-DD --target docker
   ```

7. **Verify all services** (run monitor check)
   ```bash
   sudo python3 /opt/sintaris-monitor/monitor.py daily
   ```

---

## Deployment

### Deploy backup system to a server
```bash
# From local machine in sintaris-srv/vps-admin/backup/
bash install.sh dev2null.de       # uses SSH key auth
bash install.sh dev2null.website  # uses password auth (from ../.env)
```

### Update backup scripts on server
```bash
# dev2null.de
scp -i ~/.ssh/id_ed25519 backup.sh recover.sh ${VPS_USER}@${VPS_HOST}:/tmp/
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo cp /tmp/backup.sh /tmp/recover.sh /opt/sintaris-backup/'
```

---

## Telegram Alerts

The backup system sends Telegram notifications for:
- 🔵 Backup started
- ✅ Backup completed (with manifest summary)
- 🔴 Backup failed (with error details)
- ⚠️ Restore started / completed / failed
- 🔔 System events: startup, shutdown, reboot, sleep, resume

Config in `/opt/sintaris-backup/.env`:
```bash
TG_BOT_TOKEN=<token>    # from ../.env in sintaris-srv
TG_CHAT_ID=<chat_id>    # from ../.env in sintaris-srv
BACKUP_MOUNT=/mnt/backup
BACKUP_RETENTION_DAYS=7
BACKUP_MAIL_DATA=no     # set to yes to include /var/mail/vhosts/
VOLUMES_SKIP=nextcloud-docker_nextcloud   # skip large Docker volumes
```

---

## Safety Rules

1. **Always `--dry-run` before a real backup or restore** — check output carefully
2. **Always confirm with owner before restore on production** — use `tg_ask`
3. **Never restore while services are under load** — schedule maintenance window
4. **Keep last 7 days of backups** (configurable via `BACKUP_RETENTION_DAYS`)
5. **Verify after restore** — run monitor.py and check each endpoint
6. **Log every backup/restore operation** in `docs/vps-activity-log.md`

---

## Troubleshooting

| Problem | Command | Resolution |
|---------|---------|-----------|
| Backup mount missing | `df -h \| grep backup` | Mount the backup volume or check NFS |
| Timer not firing | `systemctl status sintaris-backup.timer` | `systemctl enable --now sintaris-backup.timer` |
| Lock file stuck | `ls -la /tmp/sintaris-backup.lock` | `rm /tmp/sintaris-backup.lock` (only if no backup running) |
| DB dump fails | `journalctl -u sintaris-backup -n 100` | Check DB credentials in `.env` |
| Backup >2 days old | Monitor alert | Check timer, check mount, run manually |

---

## References

- **Scripts:** `vps-admin/backup/`
- **README:** `vps-admin/backup/README.md` — full documentation
- **Activity log:** `vps-admin/docs/vps-activity-log.md`
- **Server docs:** `vps-admin/docs/06-vps-dev2null.de.md`, `vps-admin/docs/07-vps-dev2null.website.md`
- **Change skill:** `vps-admin/skills/skill-vps-change/SKILL.md`
