# Copilot Notify MCP Server v2

Bidirectional Telegram <-> Copilot notification bridge, running as a persistent Docker service.

Notifies you when Copilot pauses, lets you reply via Telegram to unblock it, and sends full task results. Every request/response pair has a unique correlation ID.

## Features

- **Fire-and-forget notifications** — full text, auto-split for Telegram limits
- **Interactive questions** — Copilot pauses and waits for your Telegram reply
- **Inline keyboard buttons** — yes/no, multi-choice, new-task
- **Correlation IDs** — every message has a `#reqId`; replies are precisely matched
- **reply_to_message routing** — just reply to a bot message to answer it
- **`/help /status /cancel /task`** commands
- **HMAC-signed user authorization** — only you can control the bot
- **Persistent Docker service** — survives reboots, handles multiple Copilot sessions
- **HTTP/SSE MCP transport** — `{ "url": "http://localhost:7340/sse" }`

## Install (Docker)

```bash
cd monitoring/copilot-notify
npm install          # deps needed for setup.mjs only
node setup.mjs       # interactive config: bot token, user ID, instance name
docker compose up -d # start persistent service
curl http://localhost:7340/health  # verify
```

## Register with Copilot CLI

`~/.copilot/mcp-config.json`:

```json
{
  "mcpServers": {
    "copilot-notify": {
      "url": "http://localhost:7340/sse"
    }
  }
}
```

## Add to Copilot environments

Include `AGENT.md` in `.github/copilot-instructions.md` or reference it in your system prompt. It tells Copilot when and how to use each tool.

## MCP Tools

| Tool | Description |
|------|-------------|
| `tg_notify(message, level?)` | Send notification — full text, auto-split |
| `tg_ask(question, options?, timeout_sec?)` | Ask user, wait for Telegram reply |
| `tg_status(status)` | Update `/status` queryable state |
| `tg_complete(summary, wait_for_task?)` | Send full results, optionally wait for new task |

## Telegram Commands

| Command | Effect |
|---------|--------|
| `/status` | Current status + session info |
| `/help` | Full command guide |
| `/cancel [reqId]` | Skip pending question |
| `/task Your text` | Send new task to Copilot |

## Inline Buttons

- `tg_ask(options=["Yes","No"])` → Yes / No / Skip buttons
- `tg_ask(options=[...])` → Custom choice buttons
- `tg_complete(wait_for_task=true)` → "New task" + "Status" buttons

## Correlation ID System

Every message shows `#reqId` (6-char hex) in the header.
The user can answer a specific question by:
1. Tapping inline buttons (reqId embedded in callback_data)
2. Replying directly to the bot message (reply_to_message correlation)
3. Sending `abc123 my answer` (explicit reqId prefix)
4. Sending free text (attributed to most recent unanswered request)

## Security

The authorized user ID is HMAC-SHA256 signed:
```bash
node setup.mjs --verify               # check config
node setup.mjs --set-user-id <id>     # change authorized user
```
The secret key (`NOTIFY_SECRET`) must be kept safe — it's required to re-sign a new user ID.

## Sensitive Data Rules

- `NOTIFY_BOT_TOKEN`, `NOTIFY_SECRET`, `ALLOWED_USER_ID_SIG` live in `.env` only
- `.env` is git-ignored — never committed
- `.env.example` contains empty placeholders

## Docker Management

```bash
docker compose up -d        # start
docker compose down         # stop
docker compose logs -f      # live logs
docker compose restart      # restart after config change
```
