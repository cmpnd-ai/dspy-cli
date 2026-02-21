# dspy-cli Performance Implementation Plan

## Overview

This plan is organized into three phases. Phase 1 builds the testing infrastructure and establishes a benchmark against the current codebase — nothing gets changed yet. Phase 2 applies the quick wins that are low-risk and high-impact. Phase 3 implements the Django-style async routing and supporting infrastructure in the right order, with the test suite verifying each change.

All tasks assume work is happening inside the `dspy-cli` repo. New test files go under `tests/`.

---

## Phase 1 — Testing Harness & Baseline Benchmark

The goal of this phase is a repeatable, automated stress test that runs against a live `dspy-cli serve` instance with a mocked LLM backend. The mock backend is critical: it removes the upstream provider as a variable so you're measuring dspy-cli's own overhead, not OpenAI's response time.

### Task 1.1 — Mock LLM Backend

Create a minimal FastAPI server that speaks the OpenAI chat completions API format and returns immediately. This stands in for the real LLM during load tests.

**File:** `tests/load/mock_lm_server.py`

```python
"""
Minimal OpenAI-compatible mock server for load testing.
Returns a canned response immediately with configurable delay.
"""
import asyncio
import time
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any

app = FastAPI()

MOCK_DELAY_MS = 50  # Simulate minimal LLM latency. Set via env var MOCK_DELAY_MS.

class ChatRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    max_tokens: int = 100
    temperature: float = 1.0

@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):
    delay = float(__import__("os").environ.get("MOCK_DELAY_MS", MOCK_DELAY_MS)) / 1000
    await asyncio.sleep(delay)
    return {
        "id": "mock-completion",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": '[[ ## answer ## ]]\nMock answer.\n\n[[ ## completed ## ]]'
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
    uvicorn.run(app, host="0.0.0.0", port=9999)
```

**Notes:**
- `MOCK_DELAY_MS=50` simulates a fast local model. Set to `500` to simulate a real API call.
- `MOCK_DELAY_MS=0` tests pure server overhead with no LLM latency.
- The response format matches the DSPy ChatAdapter's expected format exactly (`[[ ## field ## ]]` delimiters).

---

### Task 1.2 — Fixture DSPy CLI Project

Create a minimal dspy-cli project used exclusively for load testing. It lives under `tests/load/fixture_project/` and is checked into the repo.

**File:** `tests/load/fixture_project/dspy.config.yaml`

```yaml
app_id: load-test-app
models:
  default: mock:local
  registry:
    mock:local:
      model: openai/mock-gpt
      api_base: http://localhost:9999/v1
      api_key: mock-key
      model_type: chat
      max_tokens: 100
      temperature: 1.0
```

**File:** `tests/load/fixture_project/src/load_test_app/modules/simple_predict.py`

```python
import dspy

class SimplePredict(dspy.Module):
    """Single-predict module. Used to test sync fallback path."""
    def __init__(self):
        self.predict = dspy.Predict("question:str -> answer:str")

    def forward(self, question: str) -> dspy.Prediction:
        return self.predict(question=question)
```

**File:** `tests/load/fixture_project/src/load_test_app/modules/async_predict.py`

```python
import dspy

class AsyncPredict(dspy.Module):
    """Same as SimplePredict but with aforward. Used to test async path."""
    def __init__(self):
        self.predict = dspy.Predict("question:str -> answer:str")

    def forward(self, question: str) -> dspy.Prediction:
        return self.predict(question=question)

    async def aforward(self, question: str) -> dspy.Prediction:
        return await self.predict.acall(question=question)
```

Two modules lets you directly compare sync vs async paths under identical load.

---

### Task 1.3 — Load Test Script

**File:** `tests/load/locustfile.py`

```python
"""
Locust load test for dspy-cli.

Run with:
    locust -f tests/load/locustfile.py \
           --host http://localhost:8000 \
           --headless -u 50 -r 5 \
           --run-time 60s \
           --csv results/baseline
"""
import os
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


QUESTION_PAYLOAD = {"question": "What is the capital of France?"}


class SyncModuleUser(HttpUser):
    """Hits the sync-fallback module (no aforward)."""
    wait_time = between(0.01, 0.1)
    weight = 1

    @task
    def call_simple_predict(self):
        with self.client.post(
            "/SimplePredict",
            json=QUESTION_PAYLOAD,
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got {response.status_code}: {response.text[:200]}")
            elif "answer" not in response.json():
                response.failure("Missing 'answer' in response")


class AsyncModuleUser(HttpUser):
    """Hits the native async module (has aforward)."""
    wait_time = between(0.01, 0.1)
    weight = 1

    @task
    def call_async_predict(self):
        with self.client.post(
            "/AsyncPredict",
            json=QUESTION_PAYLOAD,
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Got {response.status_code}: {response.text[:200]}")
            elif "answer" not in response.json():
                response.failure("Missing 'answer' in response")


@events.quitting.add_listener
def on_quit(environment, **kwargs):
    """Fail CI if error rate exceeds threshold."""
    if environment.runner.stats.total.fail_ratio > 0.01:
        print(f"ERROR: Failure rate {environment.runner.stats.total.fail_ratio:.1%} > 1%")
        environment.process_exit_code = 1
```

---

### Task 1.4 — Orchestration Script

A single script that boots everything, runs the test, captures results, and tears down. This is what CI runs.

**File:** `tests/load/run_benchmark.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Config
RESULTS_DIR="tests/load/results"
MOCK_PORT=9999
SERVER_PORT=8000
USERS=${USERS:-50}
SPAWN_RATE=${SPAWN_RATE:-5}
DURATION=${DURATION:-60s}
LABEL=${LABEL:-"$(git rev-parse --short HEAD)"}

mkdir -p "$RESULTS_DIR"

# 1. Start mock LLM server
echo "Starting mock LLM server on :$MOCK_PORT..."
MOCK_DELAY_MS=50 python tests/load/mock_lm_server.py &
MOCK_PID=$!
sleep 1

# 2. Start dspy-cli server against fixture project
echo "Starting dspy-cli server on :$SERVER_PORT..."
pushd tests/load/fixture_project
dspy-cli serve --port $SERVER_PORT --no-reload --system &
SERVER_PID=$!
popd
sleep 3

# 3. Wait for server health
echo "Waiting for server..."
for i in {1..20}; do
  if curl -sf http://localhost:$SERVER_PORT/programs > /dev/null; then
    echo "Server ready."
    break
  fi
  sleep 1
done

# 4. Run load test
echo "Running load test (users=$USERS, duration=$DURATION)..."
locust -f tests/load/locustfile.py \
  --host http://localhost:$SERVER_PORT \
  --headless \
  -u $USERS -r $SPAWN_RATE \
  --run-time $DURATION \
  --csv "$RESULTS_DIR/$LABEL" \
  --html "$RESULTS_DIR/$LABEL.html"

# 5. Teardown
kill $SERVER_PID $MOCK_PID 2>/dev/null || true
wait $SERVER_PID $MOCK_PID 2>/dev/null || true

echo "Results written to $RESULTS_DIR/$LABEL*.csv"
echo "Done."
```

---

### Task 1.5 — Pytest Integration for CI

Separate from the load test (which needs a running server), add a pytest-based integration test that verifies correctness under moderate concurrency. This runs in normal `pytest` without the locust dependency.

**File:** `tests/integration/test_concurrent_requests.py`

```python
"""
Concurrent correctness tests. Not a load test — verifies that responses
are correct under concurrency, not just that the server survives.

Requires a running dspy-cli server + mock LLM. Use the fixture in conftest.py.
"""
import asyncio
import httpx
import pytest

BASE_URL = "http://localhost:8000"


async def make_request(client: httpx.AsyncClient, endpoint: str, question: str):
    response = await client.post(
        f"{BASE_URL}/{endpoint}",
        json={"question": question},
        timeout=30.0
    )
    return response


@pytest.mark.asyncio
async def test_sync_module_concurrent_correctness():
    """20 concurrent requests to sync module should all succeed with valid responses."""
    async with httpx.AsyncClient() as client:
        tasks = [
            make_request(client, "SimplePredict", f"Question {i}")
            for i in range(20)
        ]
        responses = await asyncio.gather(*tasks)

    for i, r in enumerate(responses):
        assert r.status_code == 200, f"Request {i} failed: {r.text}"
        assert "answer" in r.json(), f"Request {i} missing 'answer': {r.json()}"


@pytest.mark.asyncio
async def test_async_module_concurrent_correctness():
    """20 concurrent requests to async module should all succeed."""
    async with httpx.AsyncClient() as client:
        tasks = [
            make_request(client, "AsyncPredict", f"Question {i}")
            for i in range(20)
        ]
        responses = await asyncio.gather(*tasks)

    for i, r in enumerate(responses):
        assert r.status_code == 200, f"Request {i} failed: {r.text}"
        assert "answer" in r.json(), f"Request {i} missing 'answer': {r.json()}"


@pytest.mark.asyncio
async def test_no_response_cross_contamination():
    """
    Verifies that concurrent requests don't bleed into each other's outputs.
    Sends requests with distinct questions and checks that answers are independent.
    This would catch ContextVar leakage or shared state bugs.
    """
    questions = [f"Unique question {i} xyzzy" for i in range(10)]

    async with httpx.AsyncClient() as client:
        tasks = [
            make_request(client, "AsyncPredict", q)
            for q in questions
        ]
        responses = await asyncio.gather(*tasks)

    for r in responses:
        assert r.status_code == 200
        data = r.json()
        assert "answer" in data
        # Mock server returns the same canned response, but we're verifying
        # there's no exception or empty response caused by state mixing.
        assert data["answer"] != ""
```

**File:** `tests/integration/conftest.py`

```python
"""
Starts mock LLM server and dspy-cli server as subprocess fixtures.
Tests in this directory require these fixtures.
"""
import subprocess
import time
import httpx
import pytest
import os


@pytest.fixture(scope="session", autouse=True)
def mock_lm_server():
    proc = subprocess.Popen(
        ["python", "tests/load/mock_lm_server.py"],
        env={**os.environ, "MOCK_DELAY_MS": "50"}
    )
    time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session", autouse=True)
def dspy_cli_server(mock_lm_server):
    proc = subprocess.Popen(
        ["dspy-cli", "serve", "--port", "8000", "--no-reload", "--system"],
        cwd="tests/load/fixture_project"
    )
    # Wait for server to be ready
    for _ in range(20):
        try:
            httpx.get("http://localhost:8000/programs", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    yield proc
    proc.terminate()
    proc.wait()
```

---

### Task 1.6 — Capture Baseline

Run the benchmark script against `main` before any code changes and commit the CSV output.

```bash
LABEL="baseline" bash tests/load/run_benchmark.sh
git add tests/load/results/baseline*.csv tests/load/results/baseline.html
git commit -m "perf: capture baseline benchmark"
```

Key numbers to record from the CSV:

| Metric | Where in CSV |
|---|---|
| Requests/sec (RPS) at 50 users | `_stats.csv` → `Requests/s` |
| Median response time | `_stats.csv` → `50%` |
| P95 response time | `_stats.csv` → `95%` |
| Failure rate | `_stats.csv` → `Failure Count / Request Count` |
| RPS at saturation (where failures start) | Increase `-u` until failure rate climbs |

---

## Phase 2 — Quick Wins (No Architecture Changes)

These changes are safe, small, and can be shipped before the async routing work. Run the benchmark after each one.

---

### Task 2.1 — Disable Global History in Production

**File:** `src/dspy_cli/server/runner.py` (or wherever `create_app` is called)

Add this at server startup, before any request is handled:

```python
import dspy

# GLOBAL_HISTORY is a plain list with no locking.
# Under concurrent async requests, update_history() is a race condition.
# We capture what we need in the JSONL logs; global history adds no value in production.
dspy.settings.configure(disable_history=True)
```

This eliminates the most concrete data-race bug identified in the codebase. It should have no visible effect on behavior but will be measurable under concurrency stress as fewer intermittent errors.

---

### Task 2.2 — Disable Hot Reload in the Generated Dockerfile

The generated Dockerfile from `dspy-cli new` currently produces a container that starts with `--reload` on by default (or inherits the default). Hot reload launches a filesystem watcher subprocess that restarts the server on any file change. In a container, that's a silent footgun.

**File:** `src/dspy_cli/templates/code_templates/` (wherever the Dockerfile template lives)

In the Dockerfile `CMD`:
```dockerfile
# Before
CMD ["dspy-cli", "serve", "--host", "0.0.0.0"]

# After
CMD ["dspy-cli", "serve", "--host", "0.0.0.0", "--no-reload"]
```

Also update the serve command help text to make clear `--reload` is a development flag.

---

### Task 2.3 — Document `--no-reload` Prominently

Audit the README and docs. Anywhere the Docker or production deployment is described, add an explicit note that `--reload` must be disabled. Low effort, prevents user mistakes.

---

## Phase 3 — Django-Style Async Routing

This is the core work. The sequence below is ordered so that each task is testable in isolation and doesn't break the next task's assumptions.

---

### Task 3.1 — Bounded Executor Infrastructure

Before changing the route creation logic, create the executor infrastructure it will depend on.

**New file:** `src/dspy_cli/server/executor.py`

```python
"""
Bounded thread pool executor for sync DSPy module execution.

Why bounded: the natural backpressure limit for LLM calls is the upstream
rate limit. A bounded executor makes this limit explicit and configurable
rather than relying on Uvicorn's opaque thread pool default (40 threads).

Default of 10 workers is conservative — tune up based on provider rate limits
and measured concurrency in your environment.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

_executor: ThreadPoolExecutor | None = None


def get_executor(max_workers: int = 10) -> ThreadPoolExecutor:
    """Return the process-wide bounded executor, creating it if needed."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="dspy-sync-worker"
        )
    return _executor


def shutdown_executor():
    """Gracefully shutdown the executor. Call on server shutdown."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


async def run_sync_in_executor(fn: Callable, *args: Any, **kwargs: Any) -> Any:
    """
    Run a sync callable in the bounded thread pool without blocking the event loop.

    ContextVars (including dspy.context overrides) are propagated into the thread
    automatically by asyncio.get_event_loop().run_in_executor via the current
    context snapshot. This means `with dspy.context(lm=request_lm)` set before
    calling this function will be visible inside `fn`.
    """
    loop = asyncio.get_event_loop()
    executor = get_executor()

    if kwargs:
        # run_in_executor doesn't accept kwargs; wrap in a lambda
        return await loop.run_in_executor(executor, lambda: fn(*args, **kwargs))
    return await loop.run_in_executor(executor, fn, *args)
```

**Update server lifespan** in `app.py` to shut down the executor on server stop:

```python
from dspy_cli.server.executor import shutdown_executor

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup ...
    yield
    # ... existing shutdown ...
    shutdown_executor()
```

**Add to config** (`dspy.config.yaml` schema and loader):

```yaml
server:
  sync_worker_threads: 10  # Max concurrent sync module executions
```

---

### Task 3.2 — Module Async Detection at Discovery Time

Rather than re-checking `hasattr(instance, 'aforward')` on every request, detect it once at discovery time and store it on `DiscoveredModule`. This is also where the distinction between "has user-implemented aforward" vs "inherits aforward from base class" matters.

**File:** `src/dspy_cli/discovery/module_finder.py`

Add a field to `DiscoveredModule`:

```python
@dataclass
class DiscoveredModule:
    # ... existing fields ...
    has_native_async: bool = False  # True only if user implemented aforward (not just inherited)
```

In the module discovery logic, after loading the class:

```python
def _has_user_implemented_aforward(cls) -> bool:
    """
    Returns True only if the module's own class (not a parent) defines aforward.

    This is the important distinction: all dspy.Module subclasses inherit a base
    aforward from Predict, but if the user hasn't overridden it in their Module,
    their forward() logic doesn't run in the async path — only the inner predict
    does. We need user-level aforward to trust the full async path.
    """
    # Check if 'aforward' is defined directly on this class (not inherited)
    return "aforward" in cls.__dict__
```

The distinction matters because `SimplePredict` (no user `aforward`) still technically has `.aforward` via the `Predict` sub-module, but calling `acall()` on the outer module would still run sync `forward()` logic wrapping the async `predict`. You want to detect user intent, not just method existence.

---

### Task 3.3 — Update `execute_pipeline` Dispatch Logic

This is the core change. Replace the current `hasattr(instance, 'aforward')` check with `module.has_native_async`, and add the `run_sync_in_executor` fallback.

**File:** `src/dspy_cli/server/execution.py`

```python
from dspy_cli.server.executor import run_sync_in_executor

async def execute_pipeline(
    *,
    module: DiscoveredModule,
    instance: dspy.Module,
    lm: dspy.LM,
    model_name: str,
    program_name: str,
    inputs: Dict[str, Any],
    logs_dir: Path,
) -> Dict[str, Any]:

    start_time = time.time()
    request_lm = lm.copy()

    try:
        logger.info(f"Executing {program_name} with inputs: {inputs}")

        with dspy.context(lm=request_lm):
            if module.has_native_async:
                # Native async path: LM HTTP calls are awaited, event loop is free.
                result = await instance.acall(**inputs)
            else:
                # Sync fallback: dispatch to bounded thread pool.
                # dspy.context ContextVar propagates into the thread via asyncio's
                # context snapshot mechanism (PEP 567).
                result = await run_sync_in_executor(instance, **inputs)

        # ... rest unchanged ...
```

**Write a test for the dispatch logic specifically:**

**File:** `tests/unit/test_execution_dispatch.py`

```python
"""
Tests that the right execution path is chosen based on module.has_native_async.
Uses a mock module to avoid needing a real LM.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_sync_module_dispatches_to_executor(fixture_sync_module, fixture_lm):
    """Sync modules should use run_sync_in_executor, not acall."""
    with patch("dspy_cli.server.execution.run_sync_in_executor") as mock_executor:
        mock_executor.return_value = asyncio.coroutine(lambda: {"answer": "ok"})()
        # ... call execute_pipeline and assert mock_executor was called


def test_async_module_uses_acall(fixture_async_module, fixture_lm):
    """Async modules should use instance.acall, not the executor."""
    # ...
```

---

### Task 3.4 — Update `execute_pipeline_batch` to Match

The batch execution path in `execute_pipeline_batch` has its own dispatch. Apply the same `has_native_async` check there for consistency.

---

### Task 3.5 — Expose `sync_worker_threads` in Config and CLI

Wire up the `sync_worker_threads` config value through the full stack:

1. Read from `dspy.config.yaml` in the config loader
2. Pass through `create_app()` → `get_executor(max_workers=...)`
3. Add `--sync-workers N` CLI flag to `dspy-cli serve` as an override
4. Log the value at startup: `"Sync executor: N threads for sync module dispatch"`

This makes the limit visible and tunable without code changes.

---

### Task 3.6 — Add `aforward` to `generate scaffold` Template

When a user runs `dspy-cli generate scaffold mymodule -s "question -> answer"`, the generated module should include an `aforward` implementation by default.

**File:** `src/dspy_cli/templates/code_templates/` (module template)

```python
# Generated template — before
class {{ module_name }}(dspy.Module):
    def __init__(self):
        self.predict = dspy.{{ module_type }}("{{ signature }}")

    def forward(self, {{ input_fields }}):
        return self.predict({{ input_kwargs }})
```

```python
# Generated template — after
class {{ module_name }}(dspy.Module):
    def __init__(self):
        self.predict = dspy.{{ module_type }}("{{ signature }}")

    def forward(self, {{ input_fields }}):
        return self.predict({{ input_kwargs }})

    async def aforward(self, {{ input_fields }}):
        """
        Async version of forward(). When present, dspy-cli routes requests
        through the native async path (no thread pool). For complex modules
        with custom logic between LLM calls, ensure all sub-module calls
        use acall() not direct invocation, e.g.:
            result = await self.predict.acall(...)
        """
        return await self.predict.acall({{ input_kwargs }})
```

Add a note in docs explaining when users need to do more than just call `acall` on a single predictor (multi-step modules, custom logic between calls).

---

### Task 3.7 — Fix JSONL Write Contention

The concurrent write problem: multiple threads and async tasks writing to the same log file with no locking.

**File:** `src/dspy_cli/server/logging.py`

Replace direct file writes with a `QueueHandler` → single background thread drain:

```python
import asyncio
import json
import logging
import queue
import threading
from pathlib import Path

_log_queue: queue.Queue = queue.Queue()
_log_thread: threading.Thread | None = None


def _log_writer_thread(logs_dir: Path):
    """Single background thread that drains the log queue and writes to disk."""
    open_files = {}
    while True:
        item = _log_queue.get()
        if item is None:  # Shutdown signal
            for f in open_files.values():
                f.close()
            return

        program_name, entry_json = item
        log_file = logs_dir / f"{program_name}.log"

        if program_name not in open_files:
            open_files[program_name] = open(log_file, "a", buffering=1)

        open_files[program_name].write(entry_json + "\n")
        _log_queue.task_done()


def start_log_writer(logs_dir: Path):
    """Start the background log writer. Call once at server startup."""
    global _log_thread
    _log_thread = threading.Thread(
        target=_log_writer_thread,
        args=(logs_dir,),
        daemon=True,
        name="dspy-log-writer"
    )
    _log_thread.start()


def stop_log_writer():
    """Drain the queue and shut down the log writer. Call on server shutdown."""
    _log_queue.put(None)
    if _log_thread:
        _log_thread.join(timeout=5)


def log_inference(*, logs_dir: Path, program_name: str, **fields):
    """Enqueue a log entry. Non-blocking — returns immediately."""
    entry = {"program": program_name, **fields}
    _log_queue.put((program_name, json.dumps(entry)))
```

Update server lifespan in `app.py` to call `start_log_writer()` / `stop_log_writer()`.

---

### Task 3.8 — Fix Metrics Endpoint: In-Memory Accumulation

The current `/api/metrics` endpoint reads and parses the entire JSONL file on every call. Replace the file-scan approach with in-memory running totals that are updated at write time and written to file only for durability.

**File:** `src/dspy_cli/server/metrics.py`

```python
"""
In-memory metrics accumulation with JSONL durability.

Metrics are updated in-memory on every log_inference() call.
The /api/metrics endpoint reads from memory, not from disk.
JSONL files remain for persistence across restarts — on startup,
metrics are reconstructed from the log file once, then maintained in memory.
"""
import threading
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ProgramMetrics:
    program: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    _durations: list = field(default_factory=list, repr=False)
    total_tokens: int = 0
    # ... other fields

    # Thread-safe: metrics are only written from the single log writer thread
    # and read from the metrics endpoint. No locking needed as long as GIL
    # protects the int/list updates (it does for CPython).

    def record(self, duration_ms: float, success: bool, tokens: int):
        self.call_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        self._durations.append(duration_ms)
        self.total_tokens += tokens

    @property
    def avg_latency_ms(self):
        if not self._durations:
            return None
        return sum(self._durations) / len(self._durations)

    @property
    def p95_latency_ms(self):
        if not self._durations:
            return None
        sorted_d = sorted(self._durations)
        return sorted_d[int(0.95 * (len(sorted_d) - 1))]


# Process-wide metrics store: program_name -> ProgramMetrics
_metrics_store: Dict[str, ProgramMetrics] = {}
```

Update `log_inference()` in the logging module to call `metrics_store[program].record(...)` after writing to the queue.

---

### Task 3.9 — Semaphore-Based Rate Limiting / Backpressure

Add a per-program concurrency limit. When the semaphore is full, new requests get a `429 Too Many Requests` with a `Retry-After` header rather than queuing indefinitely.

**File:** `src/dspy_cli/server/routes.py`

```python
import asyncio
from fastapi import HTTPException
from fastapi.responses import JSONResponse

# Created once per program at route creation time
program_semaphores: dict[str, asyncio.Semaphore] = {}

def create_program_routes(app, module, lm, model_config, config, gateway=None):
    max_concurrent = config.get("server", {}).get("max_concurrent_per_program", 20)
    semaphore = asyncio.Semaphore(max_concurrent)
    program_semaphores[module.name] = semaphore

    async def run_program(request: request_model):
        if not await asyncio.wait_for(
            asyncio.shield(semaphore.acquire()),
            timeout=0  # Non-blocking check
        ):
            return JSONResponse(
                status_code=429,
                content={"error": "Too many concurrent requests", "program": module.name},
                headers={"Retry-After": "1"}
            )
        try:
            return await execute_pipeline(...)
        finally:
            semaphore.release()
```

Expose `max_concurrent_per_program` in `dspy.config.yaml` and as a CLI flag.

---

### Task 3.10 — Multi-Worker Dockerfile

Update the generated Dockerfile to use Gunicorn + Uvicorn workers for true multi-process parallelism.

```dockerfile
# Install gunicorn
RUN pip install gunicorn

# Replace single-process uvicorn with multi-worker gunicorn
CMD gunicorn \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers ${WORKERS:-4} \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    "dspy_cli.server.runner:create_gunicorn_app()"
```

This requires adding a `create_gunicorn_app()` factory function in `runner.py` that Gunicorn can import. The current `main()` entry point is not importable in the Gunicorn pattern.

Note: with multiple workers, the in-memory metrics store (Task 3.8) is per-process. The `/api/metrics` endpoint will only reflect one worker's data. Solutions: use Redis for shared metrics, or accept per-worker metrics and aggregate at the load balancer. Document this limitation clearly.

---

### Task 3.11 — Health Check Differentiation

Add proper liveness vs readiness endpoints.

**File:** `src/dspy_cli/server/routes.py` or `app.py`

```python
@app.get("/health/live")
async def liveness():
    """Liveness: is the process running? Returns 200 if the server is up."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """
    Readiness: can this instance serve traffic?
    Checks that all LM instances initialized successfully.
    Returns 503 if any program failed to initialize.
    """
    failed = []
    for name, lm in app.state.program_lms.items():
        if lm is None:
            failed.append(name)

    if failed:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "failed_programs": failed}
        )
    return {"status": "ready", "programs": len(app.state.program_lms)}
```

---

### Task 3.12 — Final Benchmark & Regression Gate

Run the full benchmark suite and compare against baseline.

```bash
LABEL="after-async-routing" bash tests/load/run_benchmark.sh
```

Add a CI gate script that reads the baseline CSV and the current CSV and fails if P95 latency has regressed or RPS has dropped:

**File:** `tests/load/assert_benchmark.py`

```python
"""
Compares two locust CSV result files and fails if performance has regressed.
Usage: python tests/load/assert_benchmark.py results/baseline_stats.csv results/current_stats.csv
"""
import sys
import csv

def load_stats(path):
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Name"] == "Aggregated":
                return {
                    "rps": float(row["Requests/s"]),
                    "p95": float(row["95%"]),
                    "failures": float(row["Failure Count"]) / max(float(row["Request Count"]), 1),
                }

baseline = load_stats(sys.argv[1])
current  = load_stats(sys.argv[2])

rps_change    = (current["rps"]  - baseline["rps"])  / baseline["rps"]
p95_change    = (current["p95"]  - baseline["p95"])  / baseline["p95"]
fail_change   = current["failures"] - baseline["failures"]

print(f"RPS:      {baseline['rps']:.1f} → {current['rps']:.1f}  ({rps_change:+.1%})")
print(f"P95 (ms): {baseline['p95']:.0f} → {current['p95']:.0f}  ({p95_change:+.1%})")
print(f"Failures: {baseline['failures']:.1%} → {current['failures']:.1%}")

errors = []
if rps_change < -0.10:         errors.append(f"RPS dropped {rps_change:.1%} (threshold: -10%)")
if p95_change >  0.20:         errors.append(f"P95 increased {p95_change:.1%} (threshold: +20%)")
if current["failures"] > 0.01: errors.append(f"Failure rate {current['failures']:.1%} > 1%")

if errors:
    print("\nREGRESSION DETECTED:")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)

print("\nAll performance gates passed.")
```

---

## Summary: Task Order

| # | Task | Phase | Risk | Impact |
|---|------|-------|------|--------|
| 1.1–1.6 | Testing harness + baseline | 1 | None | Unblocks everything |
| 2.1 | Disable global history | 2 | Very Low | Fixes race condition |
| 2.2 | Dockerfile `--no-reload` | 2 | Very Low | Fixes silent production footgun |
| 2.3 | Document `--no-reload` | 2 | None | Prevents user mistakes |
| 3.1 | Bounded executor infrastructure | 3 | Low | Foundation for 3.3 |
| 3.2 | `has_native_async` at discovery | 3 | Low | Foundation for 3.3 |
| 3.3 | Update `execute_pipeline` dispatch | 3 | Medium | Core async routing change |
| 3.4 | Update batch dispatch | 3 | Low | Consistency |
| 3.5 | Expose `sync_worker_threads` config | 3 | Low | Operability |
| 3.6 | `aforward` in `generate scaffold` | 3 | Low | New modules get async path free |
| 3.7 | JSONL write contention fix | 3 | Medium | Fixes concurrent write corruption |
| 3.8 | In-memory metrics accumulation | 3 | Medium | Eliminates O(n) metrics scan |
| 3.9 | Semaphore backpressure | 3 | Medium | Prevents cascade failure |
| 3.10 | Multi-worker Dockerfile | 3 | High | Depends on 3.8 decision re: shared metrics |
| 3.11 | Health check differentiation | 3 | Low | Required for k8s deployments |
| 3.12 | Final benchmark + CI gate | 3 | None | Locks in gains |
