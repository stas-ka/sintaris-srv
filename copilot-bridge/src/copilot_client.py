"""
copilot_client.py — GitHub Copilot API client for the Copilot Bridge.

Provider hierarchy (auto mode):
  1. GitHub Copilot API  (api.githubcopilot.com) — requires Copilot subscription
  2. GitHub Models API   (models.inference.ai.azure.com) — free tier available
  3. gh CLI              (gh copilot suggest) — limited, last resort

Token flow for Copilot API:
  gh auth token  →  POST api.github.com/copilot_internal/v2/token  →  Copilot token (30 min TTL)
"""

import json
import logging
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional

import config

log = logging.getLogger("copilot_bridge.client")

# ── GitHub Copilot API endpoints ──────────────────────────────────────────────
_COPILOT_TOKEN_URL   = "https://api.github.com/copilot_internal/v2/token"
_COPILOT_CHAT_URL    = "https://api.githubcopilot.com/chat/completions"
_GITHUB_MODELS_URL   = "https://models.inference.ai.azure.com/chat/completions"

_EDITOR_VERSION      = "vscode/1.90.0"
_PLUGIN_VERSION      = "copilot-chat/0.17.2"
_INTEGRATION_ID      = "vscode-chat"


# ─────────────────────────────────────────────────────────────────────────────
# Low-level HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

def _http_post(url: str, headers: dict, body: dict, timeout: int) -> dict:
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read(512).decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {body_text[:200]}") from exc


def _http_get(url: str, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# GitHub token — from env or gh CLI
# ─────────────────────────────────────────────────────────────────────────────

def _gh_token() -> str:
    """Return GitHub OAuth token: GH_TOKEN env → `gh auth token` CLI."""
    if config.GH_TOKEN:
        return config.GH_TOKEN
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=10,
        )
        token = result.stdout.strip()
        if token and result.returncode == 0:
            return token
    except Exception as exc:
        log.warning(f"[client] gh auth token failed: {exc}")
    raise RuntimeError("No GitHub token available. Set GH_TOKEN or run `gh auth login`.")


# ─────────────────────────────────────────────────────────────────────────────
# Copilot API token manager (with auto-refresh)
# ─────────────────────────────────────────────────────────────────────────────

class _CopilotTokenManager:
    def __init__(self) -> None:
        self._token: str = ""
        self._expires_at: float = 0.0

    def get(self) -> str:
        """Return a valid Copilot API token, refreshing if needed."""
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        self._refresh()
        return self._token

    def _refresh(self) -> None:
        gh_tok = _gh_token()
        headers = {
            "Authorization": f"token {gh_tok}",
            "Accept": "application/json",
        }
        req = urllib.request.Request(_COPILOT_TOKEN_URL, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Copilot token exchange failed (HTTP {exc.code}). "
                "Check your GitHub Copilot subscription."
            ) from exc

        self._token = data.get("token", "")
        if not self._token:
            raise RuntimeError("Copilot token exchange returned empty token.")

        # Parse ISO 8601 expiry (e.g. "2024-01-01T00:30:00Z")
        try:
            import datetime
            exp_str = data.get("expires_at", "")
            if exp_str:
                exp_dt  = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                self._expires_at = exp_dt.timestamp()
            else:
                self._expires_at = time.time() + 1800  # default 30 min
        except Exception:
            self._expires_at = time.time() + 1800
        log.info("[client] Copilot API token refreshed (expires %s)", data.get("expires_at"))


_copilot_tokens = _CopilotTokenManager()


# ─────────────────────────────────────────────────────────────────────────────
# Provider implementations
# ─────────────────────────────────────────────────────────────────────────────

def _call_copilot_api(
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    system: Optional[str] = None,
) -> str:
    """Call GitHub Copilot chat API (api.githubcopilot.com)."""
    cop_token = _copilot_tokens.get()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cop_token}",
        "Editor-Version": _EDITOR_VERSION,
        "Editor-Plugin-Version": _PLUGIN_VERSION,
        "Copilot-Integration-Id": _INTEGRATION_ID,
        "OpenAI-Intent": "conversation-panel",
    }

    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)

    body = {
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    result = _http_post(_COPILOT_CHAT_URL, headers, body, timeout)
    return result["choices"][0]["message"]["content"].strip()


def _call_github_models(
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    system: Optional[str] = None,
) -> str:
    """Call GitHub Models API (models.inference.ai.azure.com) — free tier available."""
    gh_tok = _gh_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gh_tok}",
    }

    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)

    body = {
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    result = _http_post(_GITHUB_MODELS_URL, headers, body, timeout)
    return result["choices"][0]["message"]["content"].strip()


def _call_gh_cli(messages: list[dict], timeout: int) -> str:
    """Call gh copilot CLI as last resort (suggest mode — limited to commands/explanations)."""
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    if not last_user:
        raise RuntimeError("No user message found for gh CLI")

    result = subprocess.run(
        ["gh", "copilot", "suggest", "--shell-out", last_user],
        capture_output=True, text=True, timeout=timeout,
    )
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0 and not output:
        raise RuntimeError(f"gh copilot suggest exited {result.returncode}")
    return output or "(no response)"


def _list_github_models(timeout: int = 15) -> list[dict]:
    """Fetch available models from GitHub Models API."""
    try:
        gh_tok = _gh_token()
        url = "https://models.inference.ai.azure.com/models"
        data = _http_get(url, {"Authorization": f"Bearer {gh_tok}"}, timeout)
        if isinstance(data, list):
            return [{"id": m.get("id", ""), "object": "model"} for m in data]
        return []
    except Exception as exc:
        log.warning(f"[client] list_github_models failed: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Public API — auto-routing
# ─────────────────────────────────────────────────────────────────────────────

class CopilotClient:
    """Auto-routing Copilot client.  Tries providers in order until one succeeds."""

    def __init__(self) -> None:
        self._provider = config.COPILOT_PROVIDER  # auto | copilot | github_models | gh_cli

    def _providers(self) -> list[str]:
        if self._provider == "auto":
            return ["copilot", "github_models", "gh_cli"]
        return [self._provider]

    def chat(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """Send a chat request and return the response text."""
        mdl    = model or config.COPILOT_MODEL
        toks   = max_tokens or config.DEFAULT_MAX_TOKENS
        temp   = temperature if temperature is not None else config.DEFAULT_TEMPERATURE
        tmt    = timeout or config.UPSTREAM_TIMEOUT

        last_exc: Exception = RuntimeError("no provider attempted")
        for provider in self._providers():
            try:
                if provider == "copilot":
                    return _call_copilot_api(messages, mdl, toks, temp, tmt, system)
                elif provider == "github_models":
                    return _call_github_models(messages, mdl, toks, temp, tmt, system)
                elif provider == "gh_cli":
                    return _call_gh_cli(messages, tmt)
                else:
                    raise RuntimeError(f"Unknown provider: {provider}")
            except Exception as exc:
                log.warning(f"[client] provider '{provider}' failed: {exc}")
                last_exc = exc
                continue

        raise last_exc

    def list_models(self) -> list[dict]:
        """Return list of model objects (OpenAI-compatible format)."""
        models = _list_github_models()
        if not models:
            # Hardcoded fallback list
            models = [
                {"id": "gpt-4o",               "object": "model"},
                {"id": "gpt-4o-mini",           "object": "model"},
                {"id": "claude-3.5-sonnet",     "object": "model"},
                {"id": "claude-3-haiku",        "object": "model"},
            ]
        return models

    def health(self) -> dict:
        """Return health/status info."""
        try:
            token = _gh_token()
            has_token = bool(token)
        except Exception:
            has_token = False

        return {
            "status": "ok" if has_token else "degraded",
            "provider": self._provider,
            "model": config.COPILOT_MODEL,
            "gh_token": has_token,
        }


# Singleton
client = CopilotClient()
