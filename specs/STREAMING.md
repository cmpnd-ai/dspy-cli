# Real-time Streaming in DSPy-CLI

## Overview

The dspy-cli web UI supports streaming DSPy callback events via Server-Sent Events (SSE). This provides real-time visibility into the execution flow as your DSPy modules run.

## What's Displayed

The streaming UI shows the following events:

| Event | Icon | Information Shown |
|-------|------|-------------------|
| **Module Start** | 📦 | Module name, signature (truncated with expand) |
| **Module End** | ✅/❌ | Module name, duration, token usage, output preview |
| **LM Start** | 🤖 | Model type badge, model name, message count with role breakdown (S/U/A), prompt preview |
| **LM End** | ✅ | Duration, token usage (input→output), tokens/second, response preview |
| **Tool Start** | 🔧 | Tool name, description, argument preview |
| **Tool End** | ✅/❌ | Duration, result (expandable) |
| **Adapter Parse End** | 📋 | Structured output data extracted from LLM response |

**Filtered Events** (not shown to reduce noise):
- `adapter_format_start` / `adapter_format_end`
- `adapter_parse_start`

## Architecture

### Backend Components

1. **StreamingCallback** (`src/dspy_cli/server/streaming.py`)
   - Custom DSPy callback that captures all execution events
   - Queues events thread-safely via `queue.Queue`
   - Stores events in `collected_events` list for trace building
   - Extracts rich metadata: signatures, token usage, model config, etc.

2. **Streaming Endpoint** (`POST /{program_name}/stream`)
   - Creates StreamingCallback and TraceBuilder
   - Executes module with callbacks via `dspy.context()`
   - Streams events via SSE as they occur
   - Builds trace log after completion (same format as non-streaming)

3. **Event Stream Generator** (`event_stream_generator`)
   - Async generator yielding SSE-formatted events
   - Sends keepalive comments every 0.5s to prevent buffering
   - Drains remaining events after execution completes

### Frontend Components

1. **Event Handlers** (`script.js`)
   - `handleModuleStart()` / `handleModuleEnd()` - Hierarchical module display
   - `createEventElement()` - Renders LM, tool, and adapter events
   - `toggleDetails()` - Expand/collapse with preserved button labels

2. **User Controls**
   - Streaming toggle (preference saved to localStorage)
   - Auto-detection: Complex modules (CoT, ReAct) auto-enable streaming

## Real-Time Streaming

The implementation uses **thread-based execution** to enable true real-time streaming:

1. Synchronous DSPy module execution runs in a worker thread via `asyncio.to_thread()`
2. DSPy context (LM and callbacks) is re-established in the worker thread
3. Main thread's event loop remains unblocked and yields SSE events immediately
4. Callbacks fire from the worker thread and use thread-safe `Queue.put()`

### Key Technical Details

**Thread Safety:**
- Python's `queue.Queue` handles cross-thread communication
- DSPy context is re-established in worker thread, not transferred
- `collected_events` list stores events independently of queue consumption

**Duplicate Prevention:**
- Callbacks registered ONLY via `dspy.context(callbacks=[callback])`
- NOT added to LM instance to avoid DSPy's decorator combining both

**Trace Building:**
- Both streaming and non-streaming endpoints build identical trace logs
- TraceBuilder aggregates callback events into hierarchical spans
- Traces include token usage, timing, and full event metadata

## Event Data Structure

### LM Events

```javascript
// lm_start
{
  type: "lm_start",
  call_id: string,
  model: string,           // e.g., "claude-3-5-sonnet-20241022"
  model_type: string,      // e.g., "anthropic"
  messages: [{role, content}, ...],
  lm_config: object,       // temperature, etc. (API keys excluded)
  depth: number
}

// lm_end
{
  type: "lm_end",
  call_id: string,
  duration_ms: number,
  outputs: string,
  token_usage: {
    input_tokens: number,
    output_tokens: number,
    total_tokens: number
  },
  success: boolean,
  error: string | null
}
```

### Module Events

```javascript
// module_start
{
  type: "module_start",
  call_id: string,
  module_name: string,     // e.g., "CategorizerCoT"
  attributes: {
    signature: string,     // e.g., "post -> tags: list[str]"
    model: string,
    lm_config: object
  },
  inputs: object,
  depth: number
}

// module_end
{
  type: "module_end",
  call_id: string,
  duration_ms: number,
  outputs: object,
  token_usage: {           // Aggregated from all child LM calls
    total_input_tokens: number,
    total_output_tokens: number,
    by_model: { [model]: { input, output } }
  },
  success: boolean,
  error: string | null
}
```

### Tool Events

```javascript
// tool_start
{
  type: "tool_start",
  call_id: string,
  tool_name: string,
  description: string,
  inputs: object,
  depth: number
}

// tool_end
{
  type: "tool_end",
  call_id: string,
  duration_ms: number,
  outputs: object,
  success: boolean,
  error: string | null
}
```

### Adapter Parse Event

```javascript
// adapter_parse_end - Contains structured output from LLM response
{
  type: "adapter_parse_end",
  call_id: string,
  duration_ms: number,
  outputs: object,         // Parsed structured data matching signature fields
  success: boolean,
  error: string | null
}
```

## Code Locations

| Component | File | Key Functions |
|-----------|------|---------------|
| StreamingCallback | `src/dspy_cli/server/streaming.py` | `on_module_start`, `on_lm_start`, etc. |
| TraceBuilder | `src/dspy_cli/server/trace_builder.py` | `add_event`, `build` |
| Streaming Route | `src/dspy_cli/server/routes.py` | `run_program_streaming` |
| Event Generator | `src/dspy_cli/server/streaming.py` | `event_stream_generator` |
| UI Event Display | `src/dspy_cli/templates/ui/static/script.js` | `handleStreamingEvent`, `createEventElement` |

## Extending the System

1. **Add new callback types**: Implement methods in `StreamingCallback` following DSPy's `BaseCallback`
2. **Custom event filtering**: Modify the `switch` statement in `createEventElement()`
3. **New UI displays**: Add cases to `createEventElement()` with appropriate HTML/CSS
4. **Trace enrichment**: Extend `TraceBuilder` to capture additional metadata
