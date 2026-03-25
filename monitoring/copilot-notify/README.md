# Copilot Notify MCP Server

Bidirectional Telegram ↔ Copilot notification bridge. Notifies you via Telegram when Copilot pauses, lets you reply to unblock it, and updates you on task completion.

## Features

- 🔔 **Instant notifications** when Copilot stops for input
- ❓ **Interactive questions** — Copilot waits for your Telegram reply
- 📊 **Status queries** — send `/status` to the bot anytime to see what Copilot is doing
- ✅ **Task complete alerts** with optional new-task input
- 🔒 **HMAC-signed user authorization** — only you can control the bot; ID is tamper-proof but changeable
- 🏷️ **Instance names** — identify which Copilot session sent each message

## Install

```bash
cd monitoring/copilot-notify
npm install
node setup.mjs        # interactive config wizard
```

Setup will ask for:
- Bot token (use: `8321745142:AAFA6DZwq-...` — stored in `.env` only)
- Your Telegram user ID (`994963580`)
- Instance name (e.g. `dev-machine/sintaris-srv`)

## Register with Copilot CLI

Add to `~/.copilot/mcp-config.json`:

```json
{
  "mcpServers": {
    "copilot-notify": {
      "command": "node",
      "args": ["/path/to/monitoring/copilot-notify/server.mjs"]
    }
  }
}
```

## Add instructions to Copilot environments

Include `AGENT.md` in your `.github/copilot-instructions.md`:

```markdown
<!-- Telegram notifications -->
[instructions from monitoring/copilot-notify/AGENT.md]
```

Or reference the file path in your MCP config.

## MCP Tools

| Tool | Description |
|------|-------------|
| `tg_notify(message, level?)` | Send a notification (info/warning/error/success) |
| `tg_ask(question, timeout_sec?)` | Ask user, wait for Telegram reply |
| `tg_status(status)` | Update queryable status |
| `tg_complete(summary, wait_for_task?)` | Signal task done |

## Telegram Commands

| Command | Effect |
|---------|--------|
| `/status` | Returns current status + session ID |
| `/cancel` | Cancels pending `tg_ask` and lets Copilot continue |

## Security

The authorized user ID is stored alongside an HMAC-SHA256 signature. The server verifies the signature at startup — if the `.env` is tampered with, startup fails.

To change the authorized user ID:
```bash
node setup.mjs --set-user-id <new_telegram_id>
```

To verify the current config:
```bash
node setup.mjs --verify
```

## Sensitive Data Rules

- `NOTIFY_BOT_TOKEN`, `ALLOWED_USER_ID_SIG`, `NOTIFY_SECRET` live in `.env` only
- `.env` is git-ignored — never committed
- `.env.example` contains placeholder keys only
