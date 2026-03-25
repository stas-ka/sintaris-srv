# Sintaris Backup & Recovery

Automated backup system for dev2null.de and dev2null.website.  
Stores archives on a mounted backup volume. Sends Telegram notifications for every event.

---

## What Gets Backed Up

| Target | Content | Default |
|--------|---------|---------|
| `configs` | nginx, postfix, dovecot, SSL renewals, fail2ban, haproxy, x-ui | ✅ always |
| `mysql` | All user databases (nextcloud, roundcube, postfixadmin) | ✅ always |
| `postgres` | All user databases (n8n, espocrm, ...) + roles/users | ✅ always |
| `docker` | Compose configs (`/opt/*/docker-compose.yml`) + named volumes | ✅ always |
| `opt` | Runtime configs in `/opt/sintaris-backup`, `/opt/sintaris-monitor` | ✅ always |
| `mail` | Raw mail data at `/var/mail/vhosts/` | ⚠️ opt-in (`BACKUP_MAIL_DATA=yes`) |

### Excluding large Docker volumes

Some Docker volumes are very large (e.g. Nextcloud user files) and should be excluded from regular automated backups. Use the `VOLUMES_SKIP` env var in `/opt/sintaris-backup/.env`:

```bash
# Space-separated list of Docker volume names to skip
VOLUMES_SKIP=nextcloud-docker_nextcloud
```

> **dev2null.de:** `nextcloud-docker_nextcloud` (~30 GB) is excluded by default.
> Back it up manually when needed — see [Running Backups](#running-backups).

---

## Directory Structure

```
vps-admin/backup/
├── backup.sh                 Main backup script
├── recover.sh                Recovery / restore script
├── image-backup.py           Provider image/snapshot backup (Netcup + IONOS)
├── notify-event.sh           System event notifier (startup/shutdown/sleep/resume)
├── install.sh                Deploy to VPS
├── test-mockup.sh            Local mockup test (no server needed)
├── backup.env.example        Config template
├── sintaris-backup.service   Systemd service (run backup)
├── sintaris-backup.timer     Systemd timer (daily 02:00 UTC)
├── sintaris-sysevent.service Systemd service (startup/shutdown alerts)
└── sintaris-sleep.sh         Sleep/resume hook for /lib/systemd/system-sleep/
```

---

## Setup

### 1. Configure credentials

On the target VPS, create `/opt/sintaris-backup/.env`:

```bash
sudo mkdir -p /opt/sintaris-backup
sudo nano /opt/sintaris-backup/.env
```

See `backup.env.example` for all options. Minimum required:

```bash
TG_BOT_TOKEN=your_bot_token
TG_CHAT_ID=your_chat_id
BACKUP_MOUNT=/mnt/sintaris-backup    # must be mounted
BACKUP_RETENTION_DAYS=7
# Skip large Docker volumes (space-separated)
VOLUMES_SKIP=nextcloud-docker_nextcloud
```

### 2. Mount backup storage

The backup mount point must exist and be mounted before the first backup run:

```bash
# Example: NFS mount
echo "nas.local:/backups  /mnt/sintaris-backup  nfs  defaults  0 0" | sudo tee -a /etc/fstab
sudo mount -a

# Example: extra disk
echo "/dev/sdb1  /mnt/sintaris-backup  ext4  defaults  0 2" | sudo tee -a /etc/fstab
sudo mount -a

# For testing: just use a local directory
sudo mkdir -p /mnt/sintaris-backup
```

### 3. Deploy

From your local machine:

```bash
cd vps-admin/backup

# Deploy to production server
bash install.sh dev2null.de

# Deploy to VPN server
bash install.sh dev2null.website

# Dry-run first (no changes)
bash install.sh --dry-run dev2null.de
```

The installer:
- Creates `/opt/sintaris-backup/`
- Uploads `backup.sh`, `recover.sh`, `notify-event.sh`
- Creates `/opt/sintaris-backup/.env` (if not present)
- Installs systemd units and enables timer
- Installs sleep hook at `/lib/systemd/system-sleep/99-sintaris-notify.sh`

---

## Running Backups

```bash
# Full backup (all targets)
sudo /opt/sintaris-backup/backup.sh

# Dry-run (print what would be done, no changes)
sudo /opt/sintaris-backup/backup.sh --dry-run

# Single target
sudo /opt/sintaris-backup/backup.sh --target mysql
sudo /opt/sintaris-backup/backup.sh --target postgres
sudo /opt/sintaris-backup/backup.sh --target configs
sudo /opt/sintaris-backup/backup.sh --target docker

# Check timer
systemctl status sintaris-backup.timer
systemctl list-timers sintaris-backup.timer

# View logs
journalctl -u sintaris-backup.service -n 50 --no-pager
```

### Backup the excluded Nextcloud data volume manually

The `nextcloud-docker_nextcloud` volume is skipped in automated backups (it is ~30 GB of user files). To back it up manually when needed:

```bash
DEST=/mnt/sintaris-backup/backups/mail.dev2null.de/manual
sudo mkdir -p $DEST
sudo docker run --rm \
  -v nextcloud-docker_nextcloud:/data:ro \
  -v $DEST:/backup \
  alpine tar -czf /backup/nextcloud-docker_nextcloud-$(date +%Y-%m-%d).tar.gz /data
```

### Running a backup from your local machine (USB disk)

When no permanent mount is configured on the VPS, run backup locally and rsync to USB:

```bash
source ../.env

# 1. Deploy (or update) scripts on VPS
bash install.sh dev2null.de

# 2. Set VOLUMES_SKIP in VPS .env (already set on dev2null.de)
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'grep VOLUMES_SKIP /opt/sintaris-backup/.env || echo "VOLUMES_SKIP=nextcloud-docker_nextcloud" | sudo tee -a /opt/sintaris-backup/.env'

# 3. Override mount path and run backup
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo mkdir -p /tmp/sintaris-backup/backups /tmp/sintaris-backup/logs && sudo chmod 777 /tmp/sintaris-backup/logs && \
   nohup sudo BACKUP_MOUNT=/tmp/sintaris-backup /opt/sintaris-backup/backup.sh \
   > /tmp/sintaris-backup/logs/backup-stdout.log 2>&1 &'

# 4. Monitor progress
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'tail -f /tmp/sintaris-backup/logs/backup-stdout.log'

# 5. Rsync to USB when complete
rsync -avz --progress \
  -e "ssh -i ~/.ssh/id_ed25519" \
  stas@${VPS_HOST}:/tmp/sintaris-backup/ \
  /media/stas/Linux-Backup/dev2null.de/

# 6. Clean up on VPS
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo rm -rf /tmp/sintaris-backup'
```

### Schedule

| Event | Time |
|-------|------|
| Daily backup | 02:00 UTC ± up to 15 min (randomized) |
| Missed run recovery | On next startup (timer is persistent) |
| Retention | 7 days (configurable) |

---

## Recovery

```bash
# List available backups
sudo /opt/sintaris-backup/recover.sh list

# Restore everything from a date
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25

# Restore specific target
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --target mysql
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --target postgres
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --target configs

# Dry-run restore (safe — no changes)
sudo /opt/sintaris-backup/recover.sh restore --date 2026-03-25 --dry-run
```

### Recovery Order (full server restore)

1. Fresh OS install (Ubuntu 24.04)
2. Install prerequisites (nginx, mysql, postgresql, docker, etc.)
3. Mount backup storage at `BACKUP_MOUNT`
4. Restore configs: `recover.sh restore --target configs`
5. Reload services: `systemctl daemon-reload && systemctl reload nginx`
6. Restore databases: `--target mysql` then `--target postgres`
7. Restore Docker: `--target docker` then `docker compose up -d` in each `/opt/*/`
8. Verify services: `systemctl status` + test endpoints

### Alternative: restore from provider image snapshot

If a Netcup snapshot exists (see [Image Backup](#image-backup)), recovery is faster:
```bash
# On local machine:
cd vps-admin/backup
python3 image-backup.py list --server netcup   # find snapshot name
python3 image-backup.py restore --server netcup --snapshot copilot-2026-03-25
```
The server rolls back to the exact snapshot state and reboots. No reinstall needed.

---

## Image Backup (Provider Snapshots)

> **What it is:** A complete disk image of the entire VPS, taken at the hypervisor level.  
> Faster to restore than file-level backup — full server state in one step.  
> Complements (does NOT replace) the file-level `backup.sh`.

### Important: snapshots are manual

Neither Netcup nor IONOS exposes a public REST API for VPS snapshot management.  
Snapshots must be created via each provider's web control panel.

| Server | Provider | Control panel |
|--------|----------|---------------|
| dev2null.de | Netcup | https://www.servercontrolpanel.de |
| dev2null.website | IONOS VPS | https://my.ionos.com |

### `image-backup.py` — guide and tracker

`image-backup.py` helps you manage the process:
- Shows step-by-step instructions per provider
- Sends Telegram reminders to take snapshots
- Records a local history log so you know when snapshots were last taken

```bash
cd vps-admin/backup

# Show instructions for each provider
python3 image-backup.py guide
python3 image-backup.py guide --server netcup

# Send Telegram reminder (includes last snapshot age)
python3 image-backup.py remind

# Record a snapshot you just took manually
python3 image-backup.py log --server netcup --snapshot copilot-2026-03-25
python3 image-backup.py log --server ionos  --snapshot backup-2026-03-25

# Show status (last recorded snapshots per server)
python3 image-backup.py status
```

### Netcup (dev2null.de) — step by step

1. Log in at **https://www.servercontrolpanel.de**
2. Select your vServer (dev2null.de)
3. Click **Snapshots** in the left sidebar
4. Click **Create Snapshot** → enter a name (e.g. `copilot-2026-03-25`)
5. Confirm — takes a few minutes (Copy-on-Write, space-efficient)
6. To restore: click **Restore** next to a snapshot
   > ⚠️ Server stops and reboots. All changes since snapshot are lost.

### IONOS (dev2null.website) — step by step

1. Log in at **https://my.ionos.com**
2. Go to **Server & Cloud → dev2null.website**
3. Click the **Snapshots** tab → **Create Snapshot**
4. Enter a name → confirm
5. To restore: click **Restore** next to a snapshot
   > ⚠️ All changes since snapshot are lost.

### Restore notes

- After restoring from snapshot, verify all services with `monitor.py`
- If the snapshot is old, apply pending updates and re-run `backup.sh` immediately
- Log the restore in `docs/vps-activity-log.md`

### When to use image backup vs. file backup

| Scenario | Use |
|----------|-----|
| Before major upgrades or config changes | Manual snapshot via SCP/IONOS panel |
| Regular daily incremental backup | `backup.sh` (automated) |
| Restore single DB or service | `recover.sh --target ...` |
| Full disaster recovery (complete rollback) | Provider snapshot → Restore |

---

## System Event Notifications

The following events send Telegram alerts automatically:

| Event | Trigger |
|-------|---------|
| 🟢 Server started | `sintaris-sysevent.service` starts with OS |
| 🔴 Server shutting down | `sintaris-sysevent.service` ExecStop |
| 🔄 Server rebooting | Detected automatically on shutdown |
| 😴 Server sleeping | `/lib/systemd/system-sleep/` hook |
| ☀️ Server resumed | `/lib/systemd/system-sleep/` hook |
| 💾 Backup started | `backup.sh` on every run |
| ✅ Backup completed | `backup.sh` on success |
| ❌ Backup failed | `backup.sh` on error |

### Manual event trigger

```bash
sudo /opt/sintaris-backup/notify-event.sh startup
sudo /opt/sintaris-backup/notify-event.sh "custom: my message"
```

---

## Monitoring Integration

`monitoring/monitor.py` checks backup health automatically:
- Alerts if last backup is older than 2 days
- Reports last backup timestamp in daily summary
- State file: `/opt/sintaris-backup/.last_backup`

---

## Testing (Local Mockup)

No VPS access needed. Runs `backup.sh --dry-run` with a temp dir.
Sends real `[MOCKUP]` Telegram notifications.

```bash
cd vps-admin/backup
bash test-mockup.sh

# Without Telegram (fully offline)
bash test-mockup.sh --no-tg
```

Test coverage (29 checks):
- All required files present
- Script syntax (`bash -n`)
- Dry-run for dev2null.de (all 5 targets)
- Dry-run for dev2null.website
- Single-target dry-run
- All 6 notify-event.sh event types
- recover.sh list (empty, graceful)
- recover.sh dry-run restore

---

## Backup Layout on Mount

```
/mnt/sintaris-backup/
├── backups/
│   ├── dev2null.de/
│   │   ├── 2026-03-25/
│   │   │   ├── configs/       ← nginx, postfix, ssl, etc.
│   │   │   ├── mysql/         ← one .sql.gz per database
│   │   │   ├── postgresql/    ← one .pgdump per database + globals
│   │   │   ├── docker/
│   │   │   │   ├── configs/   ← compose dirs as .tar.gz
│   │   │   │   └── volumes/   ← docker volumes as .tar.gz
│   │   │   ├── opt/           ← monitor, backup configs
│   │   │   └── MANIFEST.sha256
│   │   └── 2026-03-26/  ...
│   └── dev2null.website/
│       └── ...
└── logs/
    └── dev2null.de-2026-03-25T02-00-01Z.log
```
