"""
server.py — Copilot Bridge FastAPI server.

Exposes two API-compatible endpoints so OpenClaw (and other clients) can use
GitHub Copilot as an LLM backend:

  POST /v1/chat/completions  — OpenAI-compatible  (use with OPENAI_BASE_URL)
  POST /v1/messages          — Anthropic-compatible (use with LLM_PROVIDER=copilot)
  GET  /v1/models            — list available models
  GET  /health               — health check

Run from copilot-bridge root:
  python src/server.py
  # or
  uvicorn src.server:app --host 127.0.0.1 --port 8765
"""

import sys
from pathlib import Path

# Ensure src/ is on sys.path so sibling imports (config, copilot_client) work
# regardless of the working directory.
_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import logging
import time
import uuid
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
from copilot_client import client

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("copilot_bridge.server")

app = FastAPI(
    title="Copilot Bridge",
    description="Local proxy that exposes GitHub Copilot as an OpenAI/Anthropic-compatible API.",
    version="1.0.0",
)


# ── Auth dependency ───────────────────────────────────────────────────────────

async def _check_auth(authorization: Optional[str] = Header(None)) -> None:
    """Verify bearer token if COPILOT_BRIDGE_API_KEY is configured."""
    if not config.API_KEY:
        return  # auth disabled
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != config.API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")


# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = False


class AnthropicContent(BaseModel):
    type: str = "text"
    text: str


class AnthropicMessage(BaseModel):
    role: str
    content: Any  # str or list


class AnthropicRequest(BaseModel):
    model: Optional[str] = None
    messages: list[AnthropicMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    system: Optional[str] = None
    stream: Optional[bool] = False


# ── Helper — extract text content from Anthropic message.content ──────────────

def _anthropic_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return str(content)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return client.health()


@app.get("/v1/models", dependencies=[Depends(_check_auth)])
async def list_models():
    models = client.list_models()
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions", dependencies=[Depends(_check_auth)])
async def chat_completions(req: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint.

    OpenClaw config:
        LLM_PROVIDER=openai
        OPENAI_BASE_URL=http://127.0.0.1:8765
        OPENAI_API_KEY=copilot-bridge   # any non-empty value
    """
    if req.stream:
        raise HTTPException(status_code=400, detail="Streaming not supported by Copilot Bridge")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Separate system messages (OpenAI puts them in the messages list)
    system_content = None
    user_messages  = []
    for m in messages:
        if m["role"] == "system":
            system_content = m["content"]
        else:
            user_messages.append(m)

    try:
        text = client.chat(
            user_messages,
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            system=system_content,
        )
    except Exception as exc:
        log.error(f"[server] chat/completions failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:16]}"
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or config.COPILOT_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


@app.post("/v1/messages", dependencies=[Depends(_check_auth)])
async def anthropic_messages(req: AnthropicRequest):
    """Anthropic-compatible messages endpoint.

    OpenClaw config (when ANTHROPIC_BASE_URL support is added):
        LLM_PROVIDER=anthropic
        ANTHROPIC_API_KEY=copilot-bridge   # any non-empty value
        ANTHROPIC_BASE_URL=http://127.0.0.1:8765

    Or use the dedicated copilot provider:
        LLM_PROVIDER=copilot
        COPILOT_BRIDGE_URL=http://127.0.0.1:8765
    """
    if req.stream:
        raise HTTPException(status_code=400, detail="Streaming not supported by Copilot Bridge")

    messages = [
        {"role": m.role, "content": _anthropic_content_text(m.content)}
        for m in req.messages
    ]

    try:
        text = client.chat(
            messages,
            model=req.model,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            system=req.system,
        )
    except Exception as exc:
        log.error(f"[server] /v1/messages failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": req.model or config.COPILOT_MODEL,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


@app.exception_handler(Exception)
async def _global_error(request: Request, exc: Exception):
    log.error(f"[server] unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"message": str(exc), "type": "server_error"}},
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    log.info(f"Starting Copilot Bridge on {config.HOST}:{config.PORT}")
    log.info(f"Provider: {config.COPILOT_PROVIDER} | Model: {config.COPILOT_MODEL}")
    if config.API_KEY:
        log.info("API key authentication: enabled")
    else:
        log.info("API key authentication: disabled (local-only mode)")

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )
