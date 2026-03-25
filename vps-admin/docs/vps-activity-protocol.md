# VPS Activity Protocol — sintaris-srv

Tracks every Copilot-assisted change made to production VPS servers.  
Use this to audit server state, trace incidents, and verify rollback paths.

---

## Format

Each session block contains a table with one row per completed server action:

```
### Session N — YYYY-MM-DD
| # | Time (UTC) | Action | Description | Risk | Result | Rollback |
```

**Column definitions:**

| Column | Description |
|--------|-------------|
| **#** | Sequential row number within the session |
| **Time (UTC)** | UTC timestamp when the change was applied |
| **Action** | Short verb phrase — what was done (e.g. "Edit config", "Deploy service") |
| **Description** | File(s) or service(s) affected + one-line summary of the change |
| **Risk** | Risk level — see scale below |
| **Result** | `done` / `failed` / `partial` / `reverted` |
| **Rollback** | How to undo this change — file path, command, or "N/A" |

**Risk scale:**

| Level | Meaning |
|-------|---------|
| **LOW** | Config view / read-only operation — no state changed |
| **MED** | Service restart, config change, new cron/timer — reversible |
| **HIGH** | Data change, new persistent service, port exposure |
| **CRIT** | Destructive operation, production data at risk, downtime possible |

---

## Safety Rules

1. **Always backup before change** — copy the target file to `<file>.bak` before editing
2. **Test nginx before reload** — run `nginx -t` and confirm `syntax is ok` before any `nginx reload`
3. **Verify service after restart** — run `systemctl status <service>` and check `active (running)`
4. **Prefer reload over restart** — use `nginx -s reload` / `systemctl reload` where possible to minimise downtime
5. **Document every change here** — add a row to the session log before closing the terminal

---

## Rollback Procedures

### nginx
```bash
# Restore backup and reload
sudo cp /etc/nginx/sites-available/<site>.bak /etc/nginx/sites-available/<site>
sudo nginx -t && sudo systemctl reload nginx
```

### Docker (compose service)
```bash
# Bring down, restore docker-compose.yml from backup, bring back up
cd /opt/<service-dir>/
sudo docker compose down
sudo cp docker-compose.yml.bak docker-compose.yml
sudo docker compose up -d
```

### systemd service
```bash
# Stop, restore config/binary, start
sudo systemctl stop <service>
sudo cp /opt/<service-dir>/<file>.bak /opt/<service-dir>/<file>
sudo systemctl start <service>
sudo systemctl status <service>
```

---

## Session Log

---

### Session 1 — 2026-03-25

| # | Time (UTC) | Action | Description | Risk | Result | Rollback |
|---|------------|--------|-------------|------|--------|----------|
| 1 | ~10:00 | Edit config | Set Nextcloud memory limits (1 GB RAM + 500 MB swap) in `/opt/nextcloud-docker/docker-compose.yml` | MED | done | `cp docker-compose.yml.bak docker-compose.yml && docker compose up -d` |
| 2 | ~10:30 | Deploy service | Deploy sintaris-monitor systemd timer to `/opt/sintaris-monitor/` — monitoring every 5 min, daily Telegram report at 08:00 | MED | done | `systemctl stop sintaris-monitor.timer && systemctl disable sintaris-monitor.timer` |
