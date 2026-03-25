# VPS — dev2null.website (VPN / Proxy)

Secondary server used as a VPN endpoint and outbound proxy. Not a mail or application server.

> **⚠️ Disk at 91% — investigate and clean up old logs/files before deploying anything new**

---

## Server Specs

| Property | Value |
|----------|-------|
| Host | dev2null.website |
| IP | 82.165.231.93 |
| OS | Ubuntu 22.04.5 LTS (x86_64) |
| CPU | 1 core |
| RAM | 840 MB total — 382 MB used |
| Swap | 511 MB |
| Disk | 9.6 GB total — **8.6 GB used (91% ⚠️)** |
| SSH | Password auth — user `boh`, password in `.env` as `${WEB_PASS}` |

---

## Services

| Service | Role |
|---------|------|
| nginx | Reverse proxy |
| docker | Container runtime |

---

## Docker Containers

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| amnezia-wg-easy | ghcr.io/spcfox/amnezia-wg-easy | 5443/udp, 51825/tcp | AmneziaWG VPN |

---

## Other Processes

| Process | Ports | Notes |
|---------|-------|-------|
| xray | 8443, 9443, 9444, 62789, 11111 | Proxy server |
| x-ui panel | 54321 (local), 2096 (public) | xray management panel |
| python3 service | 8091 | — |

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
