"""
config.py — Copilot Bridge configuration (loaded from environment / .env file).

Priority:  environment variables  >  .env file  >  defaults
"""

import os
from pathlib import Path


def _load_env(path: str) -> None:
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    except FileNotFoundError:
        pass


# Load .env from the bridge root (parent of src/)
_load_env(str(Path(__file__).parent.parent / ".env"))

# ── Server ────────────────────────────────────────────────────────────────────
HOST = os.getenv("COPILOT_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("COPILOT_BRIDGE_PORT", "8765"))

# Optional bearer token that clients must send in Authorization header.
# Leave empty to disable auth (bridge is local-only by default).
API_KEY = os.getenv("COPILOT_BRIDGE_API_KEY", "")

# ── GitHub Copilot ────────────────────────────────────────────────────────────
# GH_TOKEN: personal GitHub token.  Leave empty to auto-fetch via `gh auth token`.
GH_TOKEN = os.getenv("GH_TOKEN", "")

# Which backend to use: auto | copilot | github_models | gh_cli
# auto → tries copilot first, then github_models, then gh_cli
COPILOT_PROVIDER = os.getenv("COPILOT_PROVIDER", "auto")

# Default model sent to the upstream API.
# For github_models: "gpt-4o", "gpt-4o-mini", "Meta-Llama-3.1-70B-Instruct", …
# For copilot:       "gpt-4o", "claude-3.5-sonnet", …
COPILOT_MODEL = os.getenv("COPILOT_MODEL", "gpt-4o")

# ── Generation defaults (used when client doesn't specify) ────────────────────
DEFAULT_MAX_TOKENS  = int(os.getenv("DEFAULT_MAX_TOKENS", "2048"))
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))

# HTTP timeout for upstream API calls (seconds)
UPSTREAM_TIMEOUT = int(os.getenv("COPILOT_UPSTREAM_TIMEOUT", "120"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
