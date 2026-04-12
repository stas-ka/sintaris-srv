# Sintaris Backup & Recovery

Automated backup system for dev2null.de and dev2null.website.  
Stores archives on a mounted backup volume. Sends Telegram notifications for every event.

---

## Current Backup Status

| Server | backup.sh deployed | Last backup | Nextcloud data | USB backup |
|--------|--------------------|-------------|----------------|------------|
| dev2null.de | ✅ `/opt/sintaris-backup/` | daily 02:00 UTC | ⚠️ manual only (~147 GB) | ✅ 2026-03-25 |
| dev2null.website | ✅ `/opt/sintaris-backup/` | manual (no timer — disk too small) | — | ✅ 2026-03-25 |

### BACKUP_MOUNT configuration

| Server | `BACKUP_MOUNT` | Notes |
|--------|----------------|-------|
| dev2null.de | `/opt/sintaris-backup-data/` | Persistent — survives reboots, used by daily timer |
| dev2null.website | `/tmp/sintaris-backup-run` | OK — always run manually, disk too small for permanent storage |

> **dev2null.website** has only 2.4 GB free disk — no room for a permanent backup mount.
> Run backups manually when needed and pipe results directly to USB (see below).

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

> **dev2null.de:** `nextcloud-docker_nextcloud` (~147 GB of user files) is excluded by default.
> Back it up manually when needed — see [Backup Nextcloud Data](#backup-nextcloud-data-volume).

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
<a name="backup-nextcloud-data-volume"></a>

The `nextcloud-docker_nextcloud` volume is **~147 GB** of user files — excluded from automated backups.

To back it up, pipe tar over SSH directly to a local file (avoids needing free space on the VPS):

```bash
source ../.env

# Pipe Nextcloud data from VPS directly to local file
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo tar -czf - -C /var/lib/docker/volumes/nextcloud-docker_nextcloud/_data .' \
  > /media/stas/Linux-Backup/dev2null.de/nextcloud/nextcloud-data-$(date +%Y-%m-%d).tar.gz

# Monitor progress (in another terminal)
ls -lh /media/stas/Linux-Backup/dev2null.de/nextcloud/

# Verify archive integrity after completion
tar -tzf /media/stas/Linux-Backup/dev2null.de/nextcloud/nextcloud-data-$(date +%Y-%m-%d).tar.gz | tail -5
```

> **Note:** With 147 GB of user data, this takes 1.5–2 hours depending on compression ratio.
> Keep the USB disk mounted until the process completes.

### Running a backup from your local machine (USB disk) — dev2null.de

When no permanent mount is configured on the VPS, run backup locally and rsync to USB:

```bash
source ../.env

# 1. Deploy (or update) scripts on VPS
bash install.sh dev2null.de

# 2. Verify VOLUMES_SKIP is set (skip 147 GB Nextcloud volume)
python3 -c "
import subprocess
r = subprocess.run(['ssh','-i','/home/stas/.ssh/id_ed25519','stas@dev2null.de',
  'grep VOLUMES_SKIP /opt/sintaris-backup/.env'], capture_output=True, text=True)
print(r.stdout or 'NOT SET — add: VOLUMES_SKIP=nextcloud-docker_nextcloud')
"

# 3. Override mount path and run backup
ssh -i ~/.ssh/id_ed25519 ${VPS_USER}@${VPS_HOST} \
  'sudo mkdir -p /tmp/sintaris-backup/backups /tmp/sintaris-backup/logs && \
   sudo chmod 777 /tmp/sintaris-backup/logs && \
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

### Running a backup from your local machine (USB disk) — dev2null.website

The website server has only 2.4 GB free disk — cannot stage backups locally. Pipe directly to USB:

```bash
source ../.env

# 1. Deploy scripts on server (if not already deployed)
sshpass -p "${WEB_PASS}" scp backup.sh ${WEB_USER}@${WEB_HOST}:/tmp/backup.sh
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST} \
  "echo '${WEB_PASS}' | sudo -S cp /tmp/backup.sh /opt/sintaris-backup/backup.sh && \
   sudo chmod +x /opt/sintaris-backup/backup.sh"

# 2. Run backup to /tmp (small output — no Docker volumes)
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST} \
  "sudo mkdir -p /tmp/sintaris-backup-run/backups /tmp/sintaris-backup-run/logs && \
   sudo chmod 777 /tmp/sintaris-backup-run/logs && \
   nohup sudo /opt/sintaris-backup/backup.sh \
   > /tmp/backup-website.log 2>&1 </dev/null &"

# 3. Wait (~10 seconds), then rsync to USB
sleep 15
rsync -avz --progress \
  --rsh="sshpass -p ${WEB_PASS} ssh -o StrictHostKeyChecking=no" \
  ${WEB_USER}@${WEB_HOST}:/tmp/sintaris-backup-run/ \
  /media/stas/Linux-Backup/dev2null.website/$(date +%Y-%m-%d)/sintaris-backup/

# 4. Backup large services not covered by backup.sh (x-ui binary, webinar-bot)
DATE=$(date +%Y-%m-%d)
sshpass -p "${WEB_PASS}" ssh -o StrictHostKeyChecking=no ${WEB_USER}@${WEB_HOST} \
  "echo '${WEB_PASS}' | sudo -S tar -czf - \
   /usr/local/x-ui /etc/x-ui /home/boh/webinar-bot /etc/haproxy \
   2>/dev/null" \
  > /media/stas/Linux-Backup/dev2null.website/${DATE}/website-services-${DATE}.tar.gz
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

### Recovery Order — dev2null.de (full server restore)

1. Fresh OS install (**Ubuntu 24.04 LTS aarch64**)
2. Harden SSH: disable password auth, add `~/.ssh/id_ed25519.pub`, configure `sshd_config`
3. Install prerequisites: `apt install nginx certbot python3-certbot-nginx mysql-server-8.0 postgresql-17 docker.io php8.3-fpm postfix dovecot-imapd fail2ban coturn opendkim spamassassin`
4. Mount backup storage at `BACKUP_MOUNT`
5. Copy backup scripts: `bash install.sh dev2null.de`
6. Restore configs: `sudo /opt/sintaris-backup/recover.sh restore --target configs --date YYYY-MM-DD`
7. Reload services: `systemctl daemon-reload && systemctl reload nginx`
8. Restore databases: `--target mysql` then `--target postgres`
9. Restore Docker compose files + volumes: `--target docker`
10. Start all containers: `cd /opt/nextcloud-docker && docker compose up -d` (repeat for all stacks)
11. **Restore Nextcloud data** (if available on USB):
    ```bash
    tar -xzf /media/stas/Linux-Backup/dev2null.de/nextcloud/nextcloud-data-YYYY-MM-DD.tar.gz \
      -C /var/lib/docker/volumes/nextcloud-docker_nextcloud/_data/
    ```
12. Restore mail data (if `BACKUP_MAIL_DATA=yes` was set): `--target mail`
13. Deploy monitoring: `bash vps-admin/monitoring/install.sh dev2null.de`
14. Verify: `systemctl status nginx postfix postgresql docker` + test all endpoints

### Recovery Order — dev2null.website (full server restore)

1. Fresh OS install (**Ubuntu 22.04 LTS x86_64**)
2. Set up SSH access: user `boh`, password from `${WEB_PASS}` in `.env`
3. Install prerequisites: `apt install nginx haproxy docker.io`
4. **Restore x-ui (VPN):**
   ```bash
   # Extract from USB backup
   tar -xzf website-services-YYYY-MM-DD.tar.gz -C /
   # Re-enable x-ui service
   systemctl enable --now x-ui
   ```
5. **Restore webinar-bot:**
   ```bash
   tar -xzf website-services-YYYY-MM-DD.tar.gz ./home/boh/webinar-bot -C /
   systemctl enable --now webinar.bot
   ```
6. Restore nginx config: extract `configs/etc_nginx.tar.gz` from sintaris-backup archive
7. Restore haproxy config: extract `configs/etc_haproxy.tar.gz`
8. Restore SSL certs: extract `configs/ssl_live.tar.gz` → `/etc/letsencrypt/`
9. **Restore amnezia-wg-easy** (Docker):
   ```bash
   docker compose -f /opt/amnezia-wg-easy/docker-compose.yml up -d
   ```
10. Deploy monitoring: `bash vps-admin/monitoring/install.sh dev2null.website`
11. Deploy backup.sh: see [USB backup section above](#running-a-backup-from-your-local-machine-usb-disk--dev2nullwebsite)

### Key paths for dev2null.website recovery

| Path | Size | Contents |
|------|------|----------|
| `/usr/local/x-ui/` | 222 MB | x-ui binary + web UI + database |
| `/etc/x-ui/x-ui.db` | 76 KB | VPN user/inbound config database |
| `/home/boh/webinar-bot/` | 129 MB | Webinar bot runtime |
| `/etc/nginx/` | — | Nginx config + virtual hosts |
| `/etc/haproxy/` | — | HAProxy config |
| `/etc/letsencrypt/` | 3.5 MB | SSL certificates |
| `/opt/amnezia-wg-easy/` | — | Docker compose + WG config |

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
