# sinta-openclaw

OpenClaw AI gateway setup for the Sintaris server infrastructure.

OpenClaw is a Node.js AI gateway that connects Telegram (and other channels) to AI models,
custom skills, and the local Sintaris service stack.

## Quick Start (New Machine)

```bash
cd ~/projects/sintaris-srv/sinta-openclaw
bash scripts/setup.sh
```

Then follow the prompts to add secrets (Telegram bot token, API keys).

## Structure

```
sinta-openclaw/
├── scripts/
│   └── setup.sh           # Full install script
├── skills/                # Custom OpenClaw skills (symlinked to ~/.openclaw/skills/)
│   ├── skill-n8n/         # N8N workflow automation
│   ├── skill-postgres/    # PostgreSQL database
│   ├── skill-espocrm/     # EspoCRM CRM
│   └── skill-nextcloud/   # Nextcloud file storage
├── systemd/               # Systemd service templates
│   ├── openclaw-gateway.service
│   └── openclaw-tunnel.service
├── mcp/                   # GitHub Copilot CLI MCP server
│   ├── server.mjs
│   └── package.json
├── config/
│   └── openclaw.json.template   # Config template (no secrets)
└── docs/
    ├── install.md         # Full installation guide
    └── architecture.md   # System architecture
```

## Docs

- [Installation Guide](docs/install.md)
- [Architecture](docs/architecture.md)

## Web UI

**https://agents.sintaris.net/openclaw/**  
(requires SSH tunnel to be active: `systemctl --user status openclaw-tunnel`)

## Service Status

```bash
systemctl --user status openclaw-gateway openclaw-tunnel
```
