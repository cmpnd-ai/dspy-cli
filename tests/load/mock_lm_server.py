"""
Minimal OpenAI-compatible mock server for load testing.

Echoes the requested model name back in the answer so load tests can
verify that per-program model routing is correct under concurrency.

Environment variables:
    MOCK_PORT        - Port to listen on (default: 9999)
    MOCK_DELAY_MS    - Simulated LLM latency in ms (default: 50)
    MOCK_ERROR_RATE  - Fraction of requests that return 500 (0.0-1.0, default: 0.0)
"""
import asyncio
import os
import random
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

MOCK_DELAY_MS = 50


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

    # Simulate LLM errors
    error_rate = float(os.environ.get("MOCK_ERROR_RATE", "0.0"))
    if error_rate > 0 and random.random() < error_rate:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Mock LLM internal error",
                    "type": "server_error",
                    "code": "internal_error",
                }
            },
        )

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
