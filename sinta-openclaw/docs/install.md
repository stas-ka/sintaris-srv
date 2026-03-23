# OpenClaw — Installation Guide

This guide documents every step required to set up OpenClaw from scratch on a new machine and connect it to the Sintaris infrastructure.

> **Automated setup:** Run `bash scripts/setup.sh` to execute steps 3–6 automatically.  
> Steps 1–2 (prerequisites and secrets) must be done manually.

---

## Prerequisites

- Node.js 20+ (`node --version`)
- npm 10+ (`npm --version`)
- SSH access to the VPS (`ssh stas@dev2null.de`)
- GitHub Copilot CLI installed (`gh copilot --version`)

---

## Step 1 — Install OpenClaw

```bash
npm install -g openclaw
openclaw --version
# Expected: OpenClaw 2026.x.x
```

Run the onboarding wizard:
```bash
openclaw onboard
```

The wizard creates `~/.openclaw/openclaw.json` and guides you through connecting a Telegram bot.

---

## Step 2 — Configure Secrets

### 2a — Telegram Bot

1. Create a bot via [@BotFather](https://t.me/botfather) → `/newbot`
2. Set the token in OpenClaw config:
   ```bash
   openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
   openclaw config set channels.telegram.enabled true
   openclaw config set channels.telegram.groupPolicy open
   ```
3. Pair yourself with the bot: send `/start` to the bot on Telegram, then run `openclaw pair` to authorize.

### 2b — Gateway Auth Token

The gateway web UI requires an auth token (shown in `openclaw.json` → `gateway.auth`). Set or retrieve it:
```bash
openclaw config get gateway.auth
```

### 2c — OpenAI API Key

Set via environment variable (add to `~/.bashrc` or `~/.profile`):
```bash
export OPENAI_API_KEY="sk-..."
```
Or configure via `openclaw config set agents.defaults.models."openai/gpt-5.3-codex".apiKey "sk-..."`.

### 2d — N8N API Key

After setting up local N8N (see `../docs/02-local-dev-environment.md`):
1. Log in to N8N at http://localhost:5678
2. Go to Settings → API → Create API Key
3. Copy the key into `sinta-openclaw/skills/skill-n8n/api-keys.txt`:
   ```bash
   echo "YOUR_N8N_API_KEY" > ~/projects/sintaris-srv/sinta-openclaw/skills/skill-n8n/api-keys.txt
   chmod 600 ~/projects/sintaris-srv/sinta-openclaw/skills/skill-n8n/api-keys.txt
   ```

---

## Step 3 — Apply Gateway Config

```bash
openclaw config set gateway.bind lan       # Listen on all interfaces (required for tunnel)
openclaw config set gateway.port 18789
```

---

## Step 4 — Install Custom Skills

Custom skills live in `sinta-openclaw/skills/` and must be symlinked into `~/.openclaw/skills/`:

```bash
cd ~/projects/sintaris-srv/sinta-openclaw
for skill_dir in skills/skill-*; do
  skill_name=$(basename "$skill_dir")
  ln -sf "$(pwd)/$skill_dir" ~/.openclaw/skills/"$skill_name"
  echo "Symlinked: $skill_name"
done
```

Verify skills are detected:
```bash
openclaw skills list
```

---

## Step 5 — Install Systemd Services

### Gateway service

```bash
cp ~/projects/sintaris-srv/sinta-openclaw/systemd/openclaw-gateway.service \
   ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now openclaw-gateway.service
systemctl --user status openclaw-gateway.service
```

Verify: `curl http://localhost:18789/` should return the OpenClaw Web UI HTML.

### SSH Reverse Tunnel service

The tunnel forwards `VPS:127.0.0.1:18789 → localhost:18789` so nginx on the VPS can proxy the web UI.

```bash
cp ~/projects/sintaris-srv/sinta-openclaw/systemd/openclaw-tunnel.service \
   ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now openclaw-tunnel.service
systemctl --user status openclaw-tunnel.service
```

**Requirement:** Passwordless SSH to `stas@dev2null.de` must be configured:
```bash
ssh-copy-id stas@dev2null.de
# Verify: ssh -o BatchMode=yes stas@dev2null.de echo ok
```

---

## Step 6 — Install MCP Server (GitHub Copilot CLI)

The MCP server lets GitHub Copilot CLI communicate with OpenClaw.

```bash
MCP_DIR=~/.local/lib/openclaw-mcp
mkdir -p "$MCP_DIR"
cp ~/projects/sintaris-srv/sinta-openclaw/mcp/server.mjs "$MCP_DIR/"
cp ~/projects/sintaris-srv/sinta-openclaw/mcp/package.json "$MCP_DIR/"
cd "$MCP_DIR" && npm install
```

Configure Copilot CLI MCP (`~/.config/github-copilot/mcp.json`):
```json
{
  "servers": {
    "openclaw": {
      "command": "node",
      "args": ["/home/YOUR_USER/.local/lib/openclaw-mcp/server.mjs"]
    }
  }
}
```

Restart Copilot CLI for the MCP server to load.

---

## Step 7 — VPS nginx Configuration

Add the `/openclaw/` location block to the VPS nginx config for `agents.sintaris.net`.

On the VPS: `/etc/nginx/sites-enabled/agents.sintaris.net.conf`

```nginx
# Inside the HTTPS server block:
location /openclaw/ {
    proxy_pass http://127.0.0.1:18789/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

Apply:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

**Note:** This step only needs to be done once on the VPS. If the VPS config is already set up, skip this.

---

## Verification

```bash
# 1. Gateway is running
systemctl --user status openclaw-gateway.service
curl -s http://localhost:18789/ | grep "OpenClaw"

# 2. Tunnel is up
systemctl --user status openclaw-tunnel.service
ssh stas@dev2null.de 'ss -tlnp | grep 18789'

# 3. Web UI is reachable
curl -sI https://agents.sintaris.net/openclaw/ | grep "HTTP"

# 4. Skills are loaded
openclaw skills list | grep skill-

# 5. Telegram bot is active
# Send a message to @suppenclaw_bot on Telegram
```

---

## Troubleshooting

### Gateway not starting
```bash
journalctl --user -u openclaw-gateway.service -n 50 --no-pager
```

### Tunnel disconnects frequently
The service uses `Restart=on-failure` with 10s delay. For better reliability, install `autossh`:
```bash
sudo apt install autossh
# Then edit openclaw-tunnel.service to use autossh
```

### Skills not showing up
OpenClaw loads skills from `~/.openclaw/skills/`. Check symlinks:
```bash
ls -la ~/.openclaw/skills/
```
Restart the gateway after adding new skills:
```bash
systemctl --user restart openclaw-gateway.service
```

### MCP server not connecting
Check Copilot CLI MCP logs:
```bash
cat ~/.config/github-copilot/copilot-chat.log | grep mcp
```

---

## Updating Skills

To add or update a skill:
1. Edit the `SKILL.md` in `sinta-openclaw/skills/skill-xxx/`
2. The symlink means changes are live immediately (no restart needed for skill content)
3. Commit changes: `git add sinta-openclaw/skills/ && git commit -m "Update skill-xxx"`

---

## Current State (Installed on This Machine)

| Component | Status | Notes |
|---|---|---|
| openclaw binary | ✓ installed | `~/.local/bin/openclaw` (npm global) |
| openclaw.json | ✓ configured | `gateway.bind=lan`, Telegram connected |
| openclaw-gateway.service | ✓ enabled | Running on port 18789 |
| openclaw-tunnel.service | ✓ enabled | SSH reverse tunnel → VPS:18789 |
| skill-n8n | ✓ installed | API key in `skills/skill-n8n/api-keys.txt` |
| skill-postgres | ✓ installed | Local Docker PostgreSQL |
| skill-espocrm | ✓ installed | VPS EspoCRM at crm.dev2null.de |
| skill-nextcloud | ✓ installed | VPS Nextcloud at cloud.dev2null.de |
| MCP server | ✓ installed | `~/.local/lib/openclaw-mcp/server.mjs` |
| VPS nginx /openclaw/ | ✓ configured | https://agents.sintaris.net/openclaw/ |
