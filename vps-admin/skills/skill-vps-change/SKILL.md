---
name: skill-vps-change
description: Make safe, audited changes to production VPS servers (dev2null.de, dev2null.website). Provides a checklist, change procedure, verification commands, and rollback steps for nginx, Docker, and systemd services.
---

# skill-vps-change

Use this skill whenever Copilot is asked to make any change on a production VPS server.  
Every change — no matter how small — must follow this procedure and be logged.

> **dev2null.de is the primary production server.** If you are unsure about any step, **stop and ask** before proceeding.

---

## Pre-Change Checklist

Before touching anything on the server:

- [ ] Check `docs/vps-activity-protocol.md` — is there a recent change that could conflict?
- [ ] Identify the exact file or service to be modified
- [ ] Record the current state (service status, config snippet, port list)
- [ ] Backup the target config file:
  ```bash
  sudo cp /path/to/file /path/to/file.bak
  ```
- [ ] Plan the rollback step before making the change
- [ ] Confirm risk level (LOW / MED / HIGH / CRIT) — see protocol for definitions

---

## Change Procedure

1. **Make the smallest change possible** — one file, one service at a time
2. **Validate before applying** (nginx only):
   ```bash
   sudo nginx -t
   # Must show: syntax is ok / test is successful
   ```
3. **Apply the change** — use reload where possible, restart only if required
4. **Test immediately** — verify the service responds correctly
5. **Verify service health** — check status and logs (commands below)
6. **Update the activity log** — add a row to `docs/vps-activity-protocol.md` before closing

---

## Post-Change Verification

### nginx
```bash
sudo nginx -t                          # syntax check (before reload)
sudo systemctl reload nginx            # prefer reload over restart
sudo systemctl status nginx            # confirm active (running)
curl -I https://<domain>               # check HTTP response
```

### Docker / docker compose
```bash
sudo docker compose -f /opt/<service>/docker-compose.yml ps    # container status
sudo docker compose -f /opt/<service>/docker-compose.yml logs --tail=50   # recent logs
curl -s http://localhost:<port>/        # health check against mapped port
```

### systemd service
```bash
sudo systemctl status <service>        # confirm active (running)
sudo journalctl -u <service> -n 50     # recent log output
sudo systemctl is-active <service>     # returns "active" on success
```

---

## Rollback Procedures

### nginx
```bash
sudo cp /etc/nginx/sites-available/<site>.bak /etc/nginx/sites-available/<site>
sudo nginx -t && sudo systemctl reload nginx
```

### Docker (compose service)
```bash
cd /opt/<service-dir>/
sudo docker compose down
sudo cp docker-compose.yml.bak docker-compose.yml
sudo docker compose up -d
sudo docker compose ps
```

### systemd service
```bash
sudo systemctl stop <service>
sudo cp /opt/<service-dir>/<file>.bak /opt/<service-dir>/<file>
sudo systemctl start <service>
sudo systemctl status <service>
```

---

## Emergency / Escalation

| Situation | Action |
|-----------|--------|
| nginx fails to reload | Restore `.bak`, run `nginx -t`, check `journalctl -u nginx -n 50` |
| Docker container won't start | Check `docker compose logs`, restore `.bak`, `docker compose up -d` |
| Service down after change | Rollback immediately, then investigate |
| Unsure about impact | **Stop. Do not proceed. Ask the user.** |
| CRIT risk operation | **Always ask for explicit confirmation before executing** |

**dev2null.de hosts production mail, Nextcloud, N8N, EspoCRM and all customer domains.**  
Downtime has direct user impact. When in doubt, stop.

---

## References

- **Change log:** `docs/vps-activity-protocol.md` — all changes must be recorded here
- **Server details:** `docs/06-vps-dev2null.de.md` — specs, services, containers, nginx vhosts
- **Proxy server:** `docs/07-vps-dev2null.website.md` — VPN/proxy server details
