# VPS — dev2null.website (VPN / Proxy)

Secondary server used as a VPN endpoint and outbound proxy. Not a mail or application server.

> **Disk status:** 75% used (7.1GB / 9.6GB) — cleaned in Sessions 3+4 (was 91%).  
> Last cleanup: 2026-03-25 — journal vacuum, dead bot logs, btmp.1, apt cache, swapfile2 resize.

---

## Server Specs

| Property | Value |
|----------|-------|
| Host | dev2null.website |
| IP | 82.165.231.93 |
| OS | Ubuntu 22.04.5 LTS (x86_64) |
| CPU | 1 core |
| RAM | 840 MB total |
| Swap | 512 MB (/swapfile, active) + 750 MB (/swapfile2, active) = **1.26 GB total** |
| Disk | 9.6 GB total — 7.1 GB used (75%) |
| SSH | Password auth — user `boh`, password in `.env` as `${WEB_PASS}` |

---

## Services

| Service | Type | Role |
|---------|------|------|
| nginx | systemd | Reverse proxy |
| x-ui (3x-ui) | systemd | Xray VPN management panel (port 54321 local, 2096 public) |
| xray | via x-ui | VPN/proxy server (ports 8443, 9443, 9444, 62789, 11111) |
| haproxy | systemd | TCP load balancer / proxy |
| webinar.bot | systemd | Webinar bot service |
| docker | systemd | Container runtime |

---

## Docker Containers

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| amnezia-wg-easy | ghcr.io/imbtqd/amnezia-wg-easy:3 | 5443/udp, 51825/tcp | AmneziaWG VPN (active) |

Other images present (inactive, can be pruned):
- `ghcr.io/wg-easy/wg-easy:latest` (175 MB, 9 months old)
- `ghcr.io/spcfox/amnezia-wg-easy:latest` (80 MB, 19 months old)
- `amneziavpn/amnezia-wg:latest` (21 MB, 2 years old)

---

## Disk Usage Notes

| Path | Size | Notes |
|------|------|-------|
| /var/log/journal | max 200 MB | Limit set permanently in journald.conf (2026-03-25) |
| /var/log/xray | ~165 MB | Rotated every 7 days. Log level: `info` |
| /var/log/btmp | growing | Brute-force SSH login attempts — no fail2ban installed |
| /home/boh | ~542 MB | Bot runtimes, install archives |
| /home/ubuntu | ~397 MB | Old build sources (shadowsocks, mbedtls) |
| /swapfile | 512 MB | Active swap, priority -2 |
| /swapfile2 | 750 MB | Active swap, priority -3 |

**Recommendation:** Install fail2ban to stop brute-force attacks filling `/var/log/btmp`.

---

## Access

```bash
# Connect using credentials from .env
source ../.env
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST}
```

> **Note:** Password-based SSH — consider adding an SSH key for automation to reduce credential exposure.

---

## ⚠️ Known Issues

### Disk at 91%
The disk is critically full. Before any deployment:
```bash
# Check disk usage by directory
du -sh /* 2>/dev/null | sort -rh | head -20

# Check Docker image / container disk usage
docker system df

# Clean up unused Docker resources (safe)
docker system prune -f

# Check large log files
find /var/log -type f -name "*.log" -size +50M
journalctl --disk-usage
sudo journalctl --vacuum-size=200M
```

### Credentials not SSH-key based
Current SSH access uses password (`${WEB_PASS}`). For automation:
```bash
# Add SSH key (run from local machine)
ssh-copy-id -i ~/.ssh/id_ed25519.pub boh@dev2null.website
```

---

## Monitoring

- **Service:** `sintaris-monitor` (same script as dev2null.de)
- **Checks:** nginx, docker, `amnezia-wg-easy` container, disk usage, RAM
- **Script:** `/opt/sintaris-monitor/monitor.py`
- **Config:** `/opt/sintaris-monitor/.env`

```bash
# Check monitor on this host
systemctl status sintaris-monitor.timer
journalctl -u sintaris-monitor.service -n 30
```

---

## Backup

- **Scripts:** `/opt/sintaris-backup/` — **deployed 2026-03-25**
- **Config:** `/opt/sintaris-backup/.env`
- **Last backup:** `2026-03-25T15:01:43` (`.last_backup` confirmed)
- **Schedule:** manual only — disk too small (2.4 GB free) for a daily timer
- **Storage:** runs to `/tmp/sintaris-backup-run/` — pipe results to USB

### `.env` config on this server

```bash
BACKUP_MOUNT=/tmp/sintaris-backup-run
BACKUP_MYSQL=no
BACKUP_POSTGRES=no
BACKUP_DOCKER=yes
BACKUP_NGINX=yes
BACKUP_SSL=yes
BACKUP_OPT=yes
BACKUP_MAIL_DATA=no
VOLUMES_SKIP=
```

### What backup.sh covers on this server

| Target | Paths | Size |
|--------|-------|------|
| nginx config | `/etc/nginx/` | ~8 KB |
| SSL certs | `/etc/letsencrypt/live/` | ~1 KB |
| UFW rules | `/etc/ufw/` | ~4 KB |
| Cron/systemd | `/etc/cron.d/`, `/etc/systemd/system/` | ~8 KB |
| Docker | container configs | ~12 KB |
| /opt | `sintaris-monitor`, `sintaris-backup` | ~28 KB |

### ⚠️ NOT covered by backup.sh — backup manually

These large service directories are not under `/opt` and must be backed up separately:

| Path | Size | Service |
|------|------|---------|
| `/usr/local/x-ui/` | 222 MB | x-ui binary + web panel + data |
| `/etc/x-ui/x-ui.db` | 76 KB | VPN user/inbound config database |
| `/home/boh/webinar-bot/` | 129 MB | Webinar bot |
| `/etc/haproxy/` | 40 KB | HAProxy config |

```bash
# Run backup.sh (to /tmp)
source ../.env
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST} \
  "echo '${WEB_PASS}' | sudo -S /opt/sintaris-backup/backup.sh"

# Dry-run
sshpass -p "${WEB_PASS}" ssh ${WEB_USER}@${WEB_HOST} \
  "sudo /opt/sintaris-backup/backup.sh --dry-run"
```

See `vps-admin/backup/README.md` for full USB backup workflow including large services.

---

## Recovery / New Host Install

Provisioning a fresh dev2null.website replacement server:

### 1. Base setup (Ubuntu 22.04 LTS x86_64)

```bash
apt update && apt upgrade -y
apt install -y nginx haproxy docker.io sshpass
timedatectl set-timezone UTC
hostnamectl set-hostname dev2null.website
```

### 2. Restore nginx + SSL

```bash
# Extract from backup archive
tar -xzf configs/etc_nginx.tar.gz -C /
tar -xzf configs/ssl_live.tar.gz -C /etc/letsencrypt/
systemctl reload nginx
```

### 3. Restore haproxy

```bash
tar -xzf configs/etc_haproxy.tar.gz -C /
systemctl restart haproxy
```

### 4. Restore x-ui (VPN panel)

```bash
# From website-services-YYYY-MM-DD.tar.gz
tar -xzf website-services-YYYY-MM-DD.tar.gz -C / ./usr/local/x-ui ./etc/x-ui
systemctl enable --now x-ui
```

> Access x-ui panel at: `http://<server-ip>:54321` (local) or `https://dev2null.website:2096` (public)

### 5. Restore amnezia-wg-easy

```bash
mkdir -p /opt/amnezia-wg-easy
# Restore compose file from Docker backup archive
# or recreate: pull image ghcr.io/imbtqd/amnezia-wg-easy:3
docker compose -f /opt/amnezia-wg-easy/docker-compose.yml up -d
```

### 6. Restore webinar-bot

```bash
tar -xzf website-services-YYYY-MM-DD.tar.gz -C / ./home/boh/webinar-bot
cp /etc/systemd/system/webinar.bot.service /etc/systemd/system/  # from configs backup
systemctl enable --now webinar.bot
```

### 7. Restore swapfiles

```bash
# swapfile (512 MB)
fallocate -l 512M /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile

# swapfile2 (750 MB)  
fallocate -l 750M /swapfile2 && chmod 600 /swapfile2
mkswap /swapfile2 && swapon /swapfile2

# Make permanent
echo '/swapfile   none  swap  sw  0  0' >> /etc/fstab
echo '/swapfile2  none  swap  sw  0  0' >> /etc/fstab
```

### 8. Redeploy monitoring and backup

```bash
# From local machine
bash vps-admin/monitoring/install.sh dev2null.website
# Deploy backup.sh (see backup README)
```
