# Copilot Bridge

A lightweight local HTTP server that exposes **GitHub Copilot** (and GitHub Models) as an OpenAI- and Anthropic-compatible REST API.  
Use it to access GitHub Copilot from **OpenClaw / taris bot** or any other tool that supports the OpenAI or Anthropic API format.

## Architecture

```
OpenClaw / taris bot
        │
        │  POST /v1/chat/completions (OpenAI format)
        │  POST /v1/messages          (Anthropic format)
        ▼
  Copilot Bridge  (localhost:8765)
        │
        ├─ GitHub Copilot API  (api.githubcopilot.com)  ← primary
        ├─ GitHub Models API   (models.inference.ai.azure.com)  ← fallback
        └─ gh copilot CLI                                ← last resort
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Authenticate with GitHub

```bash
gh auth login
```

### 3. Start the bridge

**Windows:**
```bat
start.bat
```

**Linux / macOS:**
```bash
bash start.sh
```

The server starts on `http://127.0.0.1:8765` by default.

### 4. Test

```bash
curl http://127.0.0.1:8765/health
```

```bash
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

## Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `COPILOT_BRIDGE_HOST` | `127.0.0.1` | Bind address |
| `COPILOT_BRIDGE_PORT` | `8765` | Bind port |
| `COPILOT_BRIDGE_API_KEY` | *(empty)* | Optional bearer token for clients |
| `GH_TOKEN` | *(auto)* | GitHub token (auto via `gh auth token`) |
| `COPILOT_PROVIDER` | `auto` | `auto` \| `copilot` \| `github_models` \| `gh_cli` |
| `COPILOT_MODEL` | `gpt-4o` | Default model |
| `DEFAULT_MAX_TOKENS` | `2048` | Max tokens when client doesn't specify |
| `DEFAULT_TEMPERATURE` | `0.7` | Temperature when client doesn't specify |
| `COPILOT_UPSTREAM_TIMEOUT` | `120` | HTTP timeout for upstream calls (seconds) |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` |

## Provider Details

| Provider | Requires | Models |
|---|---|---|
| `copilot` | Active GitHub Copilot subscription | gpt-4o, claude-3.5-sonnet, … |
| `github_models` | GitHub account (free tier available) | gpt-4o-mini, llama, phi-4, … |
| `gh_cli` | `gh` CLI installed & authenticated | Limited (suggest/explain only) |

## Integrating with OpenClaw / taris bot

### Option A — `copilot` provider (recommended)

Add to `~/.taris/bot.env`:

```env
LLM_PROVIDER=copilot
COPILOT_BRIDGE_URL=http://127.0.0.1:8765
# Optional — set COPILOT_BRIDGE_KEY if you enabled API_KEY above
# COPILOT_BRIDGE_KEY=your-secret-key
```

### Option B — OpenAI-compatible (no OpenClaw code changes needed)

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://127.0.0.1:8765
OPENAI_API_KEY=copilot-bridge
OPENAI_MODEL=gpt-4o
```

## API Endpoints

### `GET /health`
Returns bridge status and upstream provider info.

### `GET /v1/models`
Returns available models in OpenAI list format.

### `POST /v1/chat/completions`
OpenAI-compatible chat completions. Accepts standard `messages`, `model`, `max_tokens`, `temperature`.

### `POST /v1/messages`
Anthropic-compatible messages endpoint. Accepts `messages`, `system`, `model`, `max_tokens`, `temperature`.

## GitHub Copilot Token Flow

When `COPILOT_PROVIDER=copilot` or `auto`:

1. Fetches GitHub OAuth token via `gh auth token` (or `GH_TOKEN` env)
2. Exchanges it for a Copilot API token via `api.github.com/copilot_internal/v2/token`
3. Caches the Copilot token (auto-refreshes before 30-min TTL)
4. Calls `api.githubcopilot.com/chat/completions` with the token

If the Copilot subscription exchange fails, the bridge automatically falls back to the GitHub Models API using the same GitHub token.
