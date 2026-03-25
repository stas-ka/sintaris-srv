# Copilot Notify v2 — Telegram Notification Instructions

## When to use these tools

You have four Telegram notification tools. Use them proactively throughout every task.

### `tg_status` — Update current phase

Call this at the START of every major work phase so the user can query status at any time.

```
tg_status(status="Analyzing database schema — step 2 of 5")
```

### `tg_notify` — Send full results or alerts

Call whenever you pause for input, encounter an error, complete a significant step, or are about to run something potentially destructive. **Send the FULL text** — it is auto-split for Telegram's limit.

```
tg_notify(message="Here are the full test results:\n..." , level="info")
tg_notify(message="Deployment failed: permission denied on /etc/nginx", level="error")
tg_notify(message="All 47 tests passed. Build successful.", level="success")
```

Levels: `info` (default), `warning`, `error`, `success`

### `tg_ask` — Ask user and wait for reply

Use when you need confirmation before a critical action, or when a decision affects the implementation. **Copilot pauses** until the user replies or timeout expires.

For yes/no, use `options=["Yes","No"]` — inline buttons appear automatically.

```
tg_ask(question="Should I restart nginx? This will briefly drop connections.", options=["Yes","No"])
tg_ask(question="Which environment should I deploy to?", options=["staging","production","cancel"])
tg_ask(question="What domain name should I use?", timeout_sec=180)
```

Returns: user reply text, `TIMEOUT`, or `CANCELLED`.

**⛔ On TIMEOUT or CANCELLED for a critical VPS operation: STOP. Do not proceed.**  
Notify the user via `tg_notify` listing what is pending and why it is blocked.  
Never use "no response = proceed" logic for destructive or system-changing operations.

### `tg_complete` — Signal task done, optionally wait for next task

Call when ALL requested tasks are complete. Pass the **full** summary — no truncation needed.
Set `wait_for_task=true` to show a "New task" button and wait for the user's next instruction.

```
tg_complete(
  summary="Deployed monitoring to both VPS servers. All checks passing.\n\nChanges:\n- ...",
  wait_for_task=True
)
```

---

## Message format

Every message shows `[InstanceName] #reqId` in the header.
Each `#reqId` is a unique 6-character hex ID correlating a specific request/response pair.
The user can reference this ID in their reply: `abc123 My answer here`

---

## What the user can do in Telegram

| Action | How |
|--------|-----|
| Answer yes/no | Tap inline buttons |
| Answer question | Reply to the bot message, or send `reqId answer` |
| Check what Copilot is doing | `/status` |
| Skip a question | `/cancel` or `/cancel reqId` |
| Send a new task | Tap `New task` button, or `/task Your instructions` |
| Get help | `/help` |

---

## Security

Only user ID `ALLOWED_USER_ID` (HMAC-signed) can interact with this bot.
All other messages are silently ignored.
