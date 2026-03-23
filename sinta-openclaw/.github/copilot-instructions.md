# sinta-openclaw — Copilot Instructions

## Project

OpenClaw AI gateway for the Sintaris infrastructure.

- **Repo root:** `~/projects/sintaris-srv/`
- **This subproject:** `~/projects/sintaris-srv/sinta-openclaw/`
- **VPS credentials:** `../. env` (gitignored) — load with `source ../.env`

## OpenClaw

| Item | Path |
|---|---|
| Binary | `~/.local/bin/openclaw` (npm global) |
| Config | `~/.openclaw/openclaw.json` |
| Skills | `skills/` → symlinked to `~/.openclaw/skills/` |
| Gateway service | `systemctl --user status openclaw-gateway` |
| Tunnel service | `systemctl --user status openclaw-tunnel` |
| Web UI | https://agents.sintaris.net/openclaw/ |
| MCP server | `mcp/server.mjs` → installed at `~/.local/lib/openclaw-mcp/` |

## Common Tasks

### Skills
```bash
# List loaded skills
openclaw skills list

# After editing a SKILL.md — changes are live immediately (no restart needed)
# After adding a NEW skill dir — restart gateway:
systemctl --user restart openclaw-gateway.service

# Add a new skill
mkdir -p skills/skill-xxx
# create skills/skill-xxx/SKILL.md with YAML frontmatter
ln -s "$(pwd)/skills/skill-xxx" ~/.openclaw/skills/skill-xxx
systemctl --user restart openclaw-gateway.service
```

### Gateway
```bash
# Status
systemctl --user status openclaw-gateway openclaw-tunnel

# Restart
systemctl --user restart openclaw-gateway.service

# Logs
journalctl --user -u openclaw-gateway.service -n 50 --no-pager

# Config
openclaw config get
openclaw config set key value
```

### Tunnel (VPS Web UI exposure)
```bash
systemctl --user status openclaw-tunnel.service
journalctl --user -u openclaw-tunnel.service -n 20 --no-pager
# Tunnel maps: VPS:127.0.0.1:18789 → localhost:18789
# nginx on VPS proxies: https://agents.sintaris.net/openclaw/
```

### MCP Server (Copilot CLI)
```bash
# Install / update
cp mcp/server.mjs ~/.local/lib/openclaw-mcp/
cd ~/.local/lib/openclaw-mcp && npm install
```

### New machine setup
```bash
bash scripts/setup.sh
```

## Services integration

| Skill | Service | Endpoint |
|---|---|---|
| skill-n8n | N8N (local) | http://localhost:5678 — API key in `skills/skill-n8n/api-keys.txt` |
| skill-n8n | N8N (VPS) | https://automata.dev2null.de — Basic Auth |
| skill-postgres | PostgreSQL (local Docker) | localhost:5432 — `n8n_user` / `n8n_apps`, `sintaris_db` |
| skill-espocrm | EspoCRM (VPS) | https://crm.dev2null.de — Espo-Authorization header |
| skill-nextcloud | Nextcloud (VPS) | https://cloud.dev2null.de — WebDAV + OCS API |

## Documentation Rule

**Always update docs after any change:**

| What changed | Update |
|---|---|
| New skill / integration | `docs/architecture.md` + `docs/install.md` |
| New systemd service | `docs/install.md` + copy template to `systemd/` |
| Config change | `config/openclaw.json.template` |
| Setup script change | `docs/install.md` |

## Docs

- [Architecture](docs/architecture.md)
- [Install Guide](docs/install.md)
- [Main infra docs](../docs/)
