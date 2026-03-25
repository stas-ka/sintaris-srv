# Copilot Notify — Telegram Notification Tools

## When to use these tools

You have access to four Telegram notification tools. Use them proactively to keep the user informed during long-running tasks, pauses, and completions.

### `tg_notify` — One-way notification

Call this when:
- You are about to pause and wait for user input (before `tg_ask`)
- You encounter an error or unexpected situation
- You complete a significant step in a multi-step task
- You are about to run a potentially destructive operation

```
tg_notify(message="Starting deployment to production server", level="warning")
```

### `tg_ask` — Ask and wait for user reply

Call this when:
- You need user confirmation before a critical or irreversible action
- You need a decision that affects implementation approach
- You are uncertain about scope and need clarification

The Copilot session **pauses** until the user replies via Telegram.

```
tg_ask(question="Should I restart the nginx service? This will briefly drop connections.", timeout_sec=120)
```

**Important:** If the user replies `TIMEOUT` or `CANCELLED`, proceed with a safe default.

### `tg_status` — Update current status

Call this at the start of each major work phase so the user can query `/status` at any time.

```
tg_status(status="Analyzing database schema — step 2/5")
```

### `tg_complete` — Task done notification

Call this when all requested tasks are complete. Use `wait_for_task=true` if you want to accept a follow-up task without the user reopening the chat.

```
tg_complete(summary="Deployed monitoring to both VPS servers. All checks passing.", wait_for_task=false)
```

---

## Security

Only the configured authorized user can interact with this bot. All other messages are silently ignored. The authorized user ID is HMAC-signed — changing it requires running `node setup.mjs --set-user-id <new_id>` with the original secret.

## Telegram commands (user can send)

| Command   | Effect                                      |
|-----------|---------------------------------------------|
| `/status` | Returns current status and session ID       |
| `/cancel` | Cancels a pending `tg_ask` (returns to default) |

---

## Instance identification

Every message includes the **instance name** (hostname/repo) and a short **session ID**. This lets you distinguish between multiple simultaneous Copilot sessions in Telegram.
