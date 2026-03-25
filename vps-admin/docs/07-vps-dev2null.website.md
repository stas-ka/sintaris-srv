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
