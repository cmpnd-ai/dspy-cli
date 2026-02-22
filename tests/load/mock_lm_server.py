"""
Minimal OpenAI-compatible mock server for load testing.

Echoes the requested model name back in the answer so load tests can
verify that per-program model routing is correct under concurrency.
"""
import asyncio
import os
import time

import uvicorn
from fastapi import FastAPI, Request
from typing import Any

app = FastAPI()

MOCK_DELAY_MS = 50  # Simulate minimal LLM latency. Set via env var MOCK_DELAY_MS.


@app.post("/v1/chat/completions")
async def chat(request: Request):
    """Accept any JSON body — no strict schema validation.

    LiteLLM sends varying extra fields (stream, n, tools, etc.)
    depending on the call path. A strict Pydantic model rejects those.

    The response embeds the requested model name in the answer field
    so callers can verify the correct model was routed.
    """
    body = await request.json()
    model = body.get("model", "unknown")
    delay = float(os.environ.get("MOCK_DELAY_MS", MOCK_DELAY_MS)) / 1000
    await asyncio.sleep(delay)
    return {
        "id": "mock-completion",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": f'[[ ## answer ## ]]\nmodel={model}\n\n[[ ## completed ## ]]'
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_PORT", 9999))
    uvicorn.run(app, host="127.0.0.1", port=port)
