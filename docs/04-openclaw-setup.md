# 04 — OpenClaw Setup

> **Note:** This page is a summary/index. Full documentation is in `../sinta-openclaw/`.

OpenClaw is the **Node.js AI gateway** (not to be confused with `picoclaw` — the Python Telegram bot, which is a separate project at `~/projects/picoclaw/` and must not be modified).

## Project location

```
sintaris-srv/
└── sinta-openclaw/          ← all OpenClaw artifacts
    ├── docs/
    │   ├── install.md       ← full installation guide
    │   └── architecture.md  ← system architecture
    ├── skills/              ← custom skills (symlinked to ~/.openclaw/skills/)
    ├── systemd/             ← service file templates
    ├── mcp/                 ← GitHub Copilot CLI MCP server
    ├── config/              ← openclaw.json template (no secrets)
    └── scripts/setup.sh     ← automated setup script
```

## Quick install on a new machine

```bash
cd ~/projects/sintaris-srv/sinta-openclaw
bash scripts/setup.sh
```

## Key facts

| Item | Value |
|---|---|
| Binary | `~/.local/bin/openclaw` (npm global) |
| Config | `~/.openclaw/openclaw.json` (gitignored secrets) |
| Gateway port | 18789 (bound to all interfaces) |
| Telegram bot | `@suppenclaw_bot` |
| Web UI | https://agents.sintaris.net/openclaw/ |
| Gateway service | `systemctl --user status openclaw-gateway` |
| Tunnel service | `systemctl --user status openclaw-tunnel` |

## See also

- [Full install guide](../sinta-openclaw/docs/install.md)
- [Architecture](../sinta-openclaw/docs/architecture.md)
