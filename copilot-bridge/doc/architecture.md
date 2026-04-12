# Copilot Bridge — Architecture Overview

## System Context

```
┌────────────────────────────────────────────────────────────┐
│  Client Machine (TariStation1/2 or Dev PC)                 │
│                                                            │
│  ┌──────────────────┐       ┌────────────────────────┐     │
│  │  OpenClaw / taris│       │  Any OpenAI/Anthropic  │     │
│  │  Telegram Bot    │       │  compatible client     │     │
│  └────────┬─────────┘       └──────────┬─────────────┘     │
│           │  LLM_PROVIDER=copilot      │  OPENAI_BASE_URL   │
│           │  (or openai + base_url)    │  http://localhost  │
│           └──────────┬─────────────────┘                   │
│                      ▼                                      │
│           ┌──────────────────────┐                         │
│           │   Copilot Bridge     │  port 8765 (default)    │
│           │   (FastAPI server)   │                         │
│           │   src/server.py      │                         │
│           └──────────┬───────────┘                         │
│                      │                                      │
└──────────────────────┼──────────────────────────────────────┘
                       │  HTTPS  (outbound)
         ┌─────────────┼─────────────────────────┐
         │             │                          │
         ▼             ▼                          ▼
  ┌─────────────┐ ┌──────────────────┐ ┌──────────────────┐
  │  GitHub     │ │  GitHub Models   │ │  gh copilot CLI  │
  │  Copilot   │ │  API             │ │  (last resort)   │
  │  API        │ │  (free tier)     │ │                  │
  │  api.github-│ │  models.inferenc-│ └──────────────────┘
  │  copilot.com│ │  e.ai.azure.com  │
  └─────────────┘ └──────────────────┘
```

## Component Breakdown

### `src/server.py` — FastAPI HTTP Server

The public interface of the bridge.  Clients send standard LLM API requests; the
server translates them, delegates to the client layer, and returns a compatible
response.

| Endpoint | Format | Purpose |
|---|---|---|
| `GET  /health` | — | Liveness + provider status |
| `GET  /v1/models` | OpenAI | List available upstream models |
| `POST /v1/chat/completions` | **OpenAI** | Primary integration endpoint |
| `POST /v1/messages` | **Anthropic** | Alternative (Claude-format) endpoint |

Optional bearer-token auth via `COPILOT_BRIDGE_API_KEY`.

### `src/copilot_client.py` — Upstream API Client

Handles all communication with GitHub services.

**Provider selection** (`COPILOT_PROVIDER`):

| Value | Backend | Notes |
|---|---|---|
| `auto` *(default)* | Tries 1 → 2 → 3 in order | Recommended |
| `copilot` | GitHub Copilot API | Requires active Copilot subscription |
| `github_models` | GitHub Models API | Free tier; gpt-4o-mini, llama, phi-4… |
| `gh_cli` | `gh copilot suggest` CLI | Limited — command suggestions only |

**GitHub token flow (auto-mode):**

```
1. Read GH_TOKEN env var  ─────────────────────────────────────┐
   (or run `gh auth token` if GH_TOKEN is empty)              │
                                                               ▼
2. POST api.github.com/copilot_internal/v2/token  ──→  Copilot token (30 min TTL)
   ├─ Success → use api.githubcopilot.com/chat/completions
   └─ Failure (no subscription) → fall back to step 3

3. POST models.inference.ai.azure.com/chat/completions
   (uses the same GitHub token directly — no exchange needed)

4. gh copilot suggest "<prompt>"  (last resort, limited API)
```

The Copilot token is **cached in memory** and refreshed 60 seconds before expiry.

### `src/config.py` — Configuration

All settings are read from environment variables, with `.env` file support
(loaded from the bridge root directory, one level above `src/`).

### Provider Fallback Chain

```
Primary attempt
    │
    ├── OK  → return response
    └── FAIL
         │
         ├── github_models attempt
         │       ├── OK  → return response
         │       └── FAIL
         │               │
         │               └── gh_cli attempt
         │                       ├── OK  → return response
         │                       └── FAIL → raise last error
```

## OpenClaw Integration

OpenClaw (`sintaris-openclaw`) uses the bridge as the `copilot` LLM provider.
The integration is defined in:

- `src/core/bot_config.py` — `COPILOT_BRIDGE_URL`, `COPILOT_BRIDGE_KEY`, `COPILOT_MODEL`, `COPILOT_TIMEOUT`
- `src/core/bot_llm.py` — `_ask_copilot()`, `_ask_copilot_with_history()`, entry in `_DISPATCH`

```
OpenClaw ask_llm(prompt)
    │
    └─ provider = "copilot"
            │
            └─ POST http://127.0.0.1:8765/v1/chat/completions
                    {model, messages, max_tokens, temperature}
                    │
                    └─ response["choices"][0]["message"]["content"]
```

Multi-turn chat (`ask_llm_with_history`) sends the full `messages` array to the
same endpoint, preserving conversation context.

## Security Model

- The bridge binds to **127.0.0.1 only** by default — not reachable from the network.
- `COPILOT_BRIDGE_API_KEY` adds bearer-token auth for multi-user environments.
- The GitHub token is never logged or returned to clients.
- No conversation data is persisted by the bridge.

## Repository Layout

```
sintaris-srv/copilot-bridge/
├── src/
│   ├── server.py          # FastAPI server (entry point)
│   ├── copilot_client.py  # GitHub Copilot / Models API client
│   └── config.py          # Env-based configuration
├── doc/
│   ├── architecture.md    # ← this file
│   └── deployment.md      # Installation & deployment guide
├── scripts/
│   ├── start.sh           # Linux/macOS quick-start
│   └── start.bat          # Windows quick-start
├── deploy/
│   ├── deploy_taristation2.sh  # Automated deploy to TariStation2
│   ├── install.sh              # Remote install script (runs on target)
│   └── copilot-bridge.service # systemd unit file
├── requirements.txt
├── .env.example
└── README.md
```

## Runtime Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | 3.12 tested |
| `fastapi` ≥ 0.100 | Via pip |
| `uvicorn` ≥ 0.22 | Via pip |
| `gh` CLI or `GH_TOKEN` | For GitHub token; `gh` optional if env set |
| Outbound HTTPS | To `api.githubcopilot.com` / `models.inference.ai.azure.com` |
| Active GitHub account | Copilot subscription for primary provider; free account for Models fallback |
