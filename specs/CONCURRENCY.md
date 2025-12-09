# Concurrency Model: FastAPI + DSPy Integration

## Overview

This document describes how dspy-cli handles concurrent requests when serving DSPy modules via FastAPI. The design ensures thread safety, proper context isolation, and non-blocking async operation.

## The Problem

Integrating DSPy with FastAPI presents several concurrency challenges:

1. **DSPy modules are synchronous** - Most DSPy modules use sync `forward()` methods that make blocking LLM API calls
2. **FastAPI is async** - Running sync code in async handlers blocks the event loop, preventing concurrent request handling
3. **DSPy uses context-local state** - `dspy.context()` sets the active LM and callbacks, which must be isolated between requests
4. **LM instances have history** - Each `dspy.LM` instance accumulates a `history` list of calls, which could leak between requests

## How DSPy Context Works

DSPy uses Python's `contextvars` module for context management:

```python
# From dspy/dsp/utils/settings.py
thread_local_overrides = contextvars.ContextVar("context_overrides", default=dotdict())

@contextmanager
def context(self, **kwargs):
    original_overrides = thread_local_overrides.get().copy()
    new_overrides = dotdict({**main_thread_config, **original_overrides, **kwargs})
    token = thread_local_overrides.set(new_overrides)
    try:
        yield
    finally:
        thread_local_overrides.reset(token)
```

**Key insight**: `contextvars` are designed for async context isolation - each async task gets its own copy. However, they do NOT automatically propagate to new threads created with `threading.Thread()` or `asyncio.to_thread()`.

## Our Solution

### 1. Fresh LM Copy Per Request

Each request gets an independent LM instance:

```python
# Instead of using shared LM:
# with dspy.context(lm=lm, ...):

# Create fresh copy with isolated history:
request_lm = lm.copy()
with dspy.context(lm=request_lm, callbacks=callbacks):
```

`lm.copy()` creates a deep copy with:
- Independent `history` list (reset to empty)
- Same model configuration
- No shared mutable state

### 2. Thread Pool Execution for Sync Modules

Sync modules run in a thread pool to avoid blocking:

```python
if hasattr(instance, 'aforward'):
    # Async module - run directly
    with dspy.context(lm=request_lm, callbacks=callbacks):
        result = await instance.acall(**inputs)
else:
    # Sync module - run in thread pool
    def run_sync_with_context():
        # Re-establish context in worker thread
        with dspy.context(lm=request_lm, callbacks=callbacks):
            return instance(**inputs)

    result = await asyncio.to_thread(run_sync_with_context)
```

**Why re-establish context in the worker thread?**

`asyncio.to_thread()` runs the function in a thread pool executor. While it does copy `contextvars` from the calling context, we explicitly re-establish the DSPy context inside the worker thread to ensure:
- The LM and callbacks are definitely active
- No race conditions during context setup
- Consistent behavior regardless of contextvar propagation details

### 3. Per-Request Callback Instances

Each request creates its own `StreamingCallback`:

```python
callback = StreamingCallback(event_queue, max_depth=max_depth)
```

The callback stores events in `collected_events` list, which is:
- Instance-specific (not shared)
- Thread-safe for appending
- Independent of queue consumption

### 4. Trace Building from Collected Events

After execution, traces are built from the callback's collected events:

```python
if trace_builder and callback:
    for event in callback.collected_events:
        trace_builder.add_event(event)
```

This is more reliable than draining the queue because:
- Events are stored regardless of queue consumption timing
- Works consistently for both sync and async execution paths
- No race conditions between event production and consumption

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Server                            │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Request 1     │  │   Request 2     │  │   Request 3     │ │
│  │                 │  │                 │  │                 │ │
│  │  request_lm_1   │  │  request_lm_2   │  │  request_lm_3   │ │
│  │  = lm.copy()    │  │  = lm.copy()    │  │  = lm.copy()    │ │
│  │                 │  │                 │  │                 │ │
│  │  callback_1     │  │  callback_2     │  │  callback_3     │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
│           ▼                    ▼                    ▼          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Thread Pool Executor                    │   │
│  │                                                          │   │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐         │   │
│  │   │ Worker 1 │    │ Worker 2 │    │ Worker 3 │         │   │
│  │   │          │    │          │    │          │         │   │
│  │   │ dspy.    │    │ dspy.    │    │ dspy.    │         │   │
│  │   │ context  │    │ context  │    │ context  │         │   │
│  │   │ (lm_1)   │    │ (lm_2)   │    │ (lm_3)   │         │   │
│  │   └──────────┘    └──────────┘    └──────────┘         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  app.state.program_lms = {                                      │
│      "categorizer": LM(claude-sonnet),  # Template for copies   │
│      "summarizer": LM(gpt-4),           # Template for copies   │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Request Lifecycle

### Standard Endpoint (`POST /{program}`)

```
1. Request arrives
   ↓
2. Create fresh LM copy: request_lm = lm.copy()
   ↓
3. Create callback instance (if tracing enabled)
   ↓
4. Check if module has async forward:
   │
   ├─ Yes (aforward): Run with dspy.context() directly
   │
   └─ No (sync): Submit to thread pool via asyncio.to_thread()
                 Re-establish dspy.context() in worker thread
   ↓
5. Await result (event loop not blocked)
   ↓
6. Build trace from callback.collected_events
   ↓
7. Log inference and return response
```

### Streaming Endpoint (`POST /{program}/stream`)

```
1. Request arrives
   ↓
2. Create fresh LM copy: streaming_lm = lm.copy()
   ↓
3. Create callback instance and event queue
   ↓
4. Create asyncio.Task for execution
   ↓
5. Return StreamingResponse immediately
   ↓
6. In background task:
   - Run module (async or in thread pool)
   - Callbacks fire and emit events to queue
   - Events also stored in collected_events
   ↓
7. SSE generator yields events from queue in real-time
   ↓
8. After completion, build trace from collected_events
```

## What This Prevents

| Issue | How It's Prevented |
|-------|-------------------|
| **Event loop blocking** | Sync modules run in thread pool via `asyncio.to_thread()` |
| **LM history leakage** | Fresh `lm.copy()` per request with empty history |
| **Context pollution** | Per-request callback instances, context re-established in workers |
| **Race conditions** | Thread-safe queue + collected_events list for trace building |
| **Model cross-contamination** | Per-program LM instances in `app.state.program_lms` |

## Performance Considerations

### Thread Pool Sizing

`asyncio.to_thread()` uses the default thread pool executor. Under high load:
- Default pool size is `min(32, os.cpu_count() + 4)`
- DSPy modules are I/O-bound (waiting for LLM APIs), so many threads can run concurrently
- Consider configuring a larger pool for high-throughput scenarios

### LM Copy Overhead

`lm.copy()` performs a deep copy:
- Typically < 1ms overhead
- Worth it for isolation guarantees
- History reset prevents memory growth across requests

### Callback Overhead

`StreamingCallback` adds minimal overhead:
- Event emission: ~0.1ms per event
- Queue operations are thread-safe and fast
- `collected_events` append is O(1)

## Historical Context

This design evolved through several iterations:

1. **Initial approach**: Shared LM instance, sync execution in async handler
   - Problem: Blocked event loop, history leaked between requests

2. **First fix**: Added `dspy.context()` for per-request LM
   - Problem: Context didn't propagate to threads, still blocked event loop

3. **Streaming implementation**: Used `asyncio.to_thread()` with context re-establishment
   - Worked well for streaming endpoint

4. **Final unification**: Applied streaming patterns to standard endpoint
   - Fresh LM copy + thread pool + context re-establishment
   - Both endpoints now have identical concurrency safety

## Related Documentation

- [STREAMING.md](./STREAMING.md) - Real-time event streaming implementation
- [TRACING.md](./TRACING.md) - Execution trace capture and logging
