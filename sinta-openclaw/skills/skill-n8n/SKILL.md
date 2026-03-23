---
name: skill-n8n
description: Interact with N8N workflow automation. List, inspect, trigger, and manage workflows via the N8N REST API.
---

# N8N Workflow Automation Skill

## Endpoints

| Environment | URL | Auth |
|---|---|---|
| Local (dev) | `http://localhost:5678` | API key (header) |
| VPS (prod) | `https://automata.dev2null.de` | API key (header) |

Default to **local** unless user says "production" or "VPS".

## Authentication

Use the header `X-N8N-API-KEY` with the API key stored in `~/.openclaw/skills/skill-n8n/api-keys.txt`.

```bash
N8N_KEY=$(head -1 ~/.openclaw/skills/skill-n8n/api-keys.txt)
curl -s -H "X-N8N-API-KEY: $N8N_KEY" http://localhost:5678/api/v1/workflows
```

## Common Operations

### List workflows
```bash
curl -s -H "X-N8N-API-KEY: $N8N_KEY" \
  "http://localhost:5678/api/v1/workflows?limit=50" | python3 -m json.tool
```

### Get workflow by ID
```bash
curl -s -H "X-N8N-API-KEY: $N8N_KEY" \
  "http://localhost:5678/api/v1/workflows/{id}"
```

### Execute a workflow (must be active + have webhook/manual trigger)
```bash
curl -s -X POST -H "X-N8N-API-KEY: $N8N_KEY" \
  -H "Content-Type: application/json" \
  -d '{"startNodes":[],"destinationNode":""}' \
  "http://localhost:5678/api/v1/workflows/{id}/run"
```

### Activate / Deactivate
```bash
PATCH http://localhost:5678/api/v1/workflows/{id}
Body: {"active": true}
```

### List executions
```bash
curl -s -H "X-N8N-API-KEY: $N8N_KEY" \
  "http://localhost:5678/api/v1/executions?limit=10&workflowId={id}"
```

### Trigger webhook workflow
```bash
curl -s -X POST "http://localhost:5678/webhook/{webhook-path}" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

## Notes

- All imported Worksafety workflows are currently **inactive** — credentials need to be set up in N8N UI before activating
- N8N API v1 base path: `/api/v1/`
- Pagination: use `limit` and `cursor` params
- For VPS (v2.2.3) use Basic Auth: `Authorization: Basic <base64(user:pass)>`
