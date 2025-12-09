# DSPy CLI Tracing Documentation

## Overview

The dspy-cli includes comprehensive execution tracing that captures hierarchical call structures, token usage, timing information, and rich metadata from DSPy programs. Traces are stored in JSON log files and are identical whether using the standard or streaming endpoints.

## Features

### Hierarchical Span Tracking
- **Parent-Child Relationships**: Full call hierarchies showing how modules, LM calls, tools, and adapters nest
- **Depth Tracking**: Each span includes its depth in the call tree
- **Duration Measurement**: Millisecond timing for every operation

### Token Usage Aggregation
- **Per-Span Tracking**: Each LM call records input/output token counts
- **Per-Model Aggregation**: Token usage grouped by model
- **Total Counts**: Overall input/output totals across all LM calls

### Rich Metadata
- **Module Attributes**: Signatures, class names, LM configurations
- **Credential Filtering**: API keys and sensitive data automatically stripped
- **Input/Output Data**: Cleaned and serialized for logging

## Configuration

Add trace settings to your `dspy.config.yaml`:

```yaml
# Global trace settings
tracing:
  enabled: true             # Enable/disable tracing globally (default: true)
  store_in_logs: true       # Store traces in log files (default: true)
  max_trace_depth: 50       # Maximum call stack depth (default: 50)

# Per-program overrides
program_tracing:
  MyExpensiveProgram:
    enabled: false          # Disable for performance-critical programs
  MyDebugProgram:
    enabled: true
    max_trace_depth: 100    # Allow deeper traces for debugging
```

## Log Format

Traces are stored in `logs/{program_name}.log` as JSON (one entry per line):

```json
{
  "timestamp": "2024-12-04T10:30:00.123456",
  "program": "categorizer",
  "model": "anthropic/claude-sonnet-4",
  "duration_ms": 1234.56,
  "inputs": {"post": "My blog post content..."},
  "outputs": {"tags": ["python", "dspy", "ai"]},
  "success": true,
  "trace": {
    "trace_id": "uuid-...",
    "root_call_ids": ["call_1"],
    "spans": [...],
    "token_usage": {
      "total_input_tokens": 150,
      "total_output_tokens": 20,
      "by_model": {
        "anthropic/claude-sonnet-4": {"input": 150, "output": 20}
      }
    },
    "span_count": 2
  }
}
```

## Span Types

| Type | Description | Key Fields |
|------|-------------|------------|
| **module** | DSPy Module execution | `module_name`, `attributes.signature`, `inputs`, `outputs`, `token_usage` |
| **lm** | Language Model API call | `model`, `model_type`, `messages`, `outputs`, `token_usage` |
| **tool** | Tool invocation | `tool_name`, `description`, `inputs`, `outputs` |
| **adapter** | Adapter format/parse | `adapter_type`, `outputs` (parse only) |

## Span Structure

### Module Span
```json
{
  "call_id": "abc123",
  "parent_call_id": null,
  "type": "module",
  "name": "CategorizerCoT",
  "depth": 0,
  "start_time": 1701234567.123,
  "end_time": 1701234568.456,
  "duration_ms": 1333,
  "inputs": {"post": "..."},
  "outputs": {"tags": ["python", "dspy"]},
  "token_usage": {
    "total_input_tokens": 150,
    "total_output_tokens": 20,
    "by_model": {"anthropic/claude-sonnet-4": {"input": 150, "output": 20}}
  },
  "success": true,
  "error": null,
  "children": ["def456"],
  "attributes": {
    "class": "CategorizerCoT",
    "signature": "post -> tags: list[str]",
    "model": "anthropic/claude-sonnet-4"
  }
}
```

### LM Span
```json
{
  "call_id": "def456",
  "parent_call_id": "abc123",
  "type": "lm",
  "name": "LM(anthropic/claude-sonnet-4)",
  "depth": 1,
  "duration_ms": 1100,
  "model": "anthropic/claude-sonnet-4",
  "model_type": "chat",
  "lm_config": {"temperature": 0.7},
  "messages": [{"role": "user", "content": "..."}],
  "outputs": "The tags are: python, dspy",
  "token_usage": {
    "input_tokens": 150,
    "output_tokens": 20,
    "total_tokens": 170
  },
  "success": true,
  "children": []
}
```

### Tool Span
```json
{
  "call_id": "ghi789",
  "parent_call_id": "abc123",
  "type": "tool",
  "name": "Tool(search_web)",
  "depth": 1,
  "duration_ms": 500,
  "description": "Search the web for information",
  "inputs": {"query": "dspy tutorial"},
  "outputs": {"results": [...]},
  "success": true,
  "children": []
}
```

### Adapter Parse Span
```json
{
  "call_id": "jkl012",
  "parent_call_id": "def456",
  "type": "adapter",
  "name": "Adapter.parse(ChatAdapter)",
  "depth": 2,
  "duration_ms": 5,
  "outputs": {"tags": ["python", "dspy"]},
  "success": true
}
```

## API Usage

### Accessing Traces via Log API

```bash
# Get recent logs with traces
curl http://localhost:8000/api/logs/categorizer
```

### Programmatic Usage

```python
from dspy_cli.server.trace_builder import TraceBuilder
from dspy_cli.server.streaming import StreamingCallback
from queue import Queue
import dspy

# Create callback and trace builder
event_queue = Queue()
callback = StreamingCallback(event_queue, max_depth=50)
trace_builder = TraceBuilder()

# Execute with DSPy context
with dspy.context(lm=my_lm, callbacks=[callback]):
    result = my_module(**inputs)

# Build trace from collected events
for event in callback.collected_events:
    trace_builder.add_event(event)

trace = trace_builder.build()
print(f"Total tokens: {trace['token_usage']}")
print(f"Span count: {trace['span_count']}")
```

## Architecture

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `StreamingCallback` | `server/streaming.py` | Captures DSPy callback events with metadata |
| `TraceBuilder` | `server/trace_builder.py` | Aggregates events into hierarchical traces |
| `log_inference()` | `server/logging.py` | Persists traces to JSON log files |
| `get_trace_config()` | `config/loader.py` | Loads per-program trace settings |

### Data Flow

1. **Callback Registration**: `StreamingCallback` registered via `dspy.context(callbacks=[...])`
2. **Event Capture**: Callback methods fire on module/LM/tool/adapter start/end
3. **Event Storage**: Events queued and stored in `callback.collected_events`
4. **Trace Building**: `TraceBuilder.add_event()` processes events into spans
5. **Aggregation**: `TraceBuilder.build()` creates final trace with token totals
6. **Persistence**: `log_inference()` writes JSON to `logs/{program}.log`

### Identical Traces

Both endpoints produce identical traces:
- `POST /{program}` - Standard endpoint, trace built after execution
- `POST /{program}/stream` - Streaming endpoint, trace built from `collected_events`

## Performance

### Overhead
- Callback hooks: <1% latency impact
- Token extraction: Uses DSPy's built-in usage tracking
- Trace building: Minimal CPU, ~1ms for typical traces

### Disabling Tracing

For performance-critical scenarios:

```yaml
# Disable for specific program
program_tracing:
  HighVolumeProgram:
    enabled: false

# Or disable globally
tracing:
  enabled: false
```

## Benefits

1. **Debugging**: See exact execution flow and identify failures
2. **Performance Analysis**: Identify bottlenecks with precise timing
3. **Token Optimization**: Monitor usage across nested calls
4. **Training Data**: Structured traces for fine-tuning
5. **Cost Tracking**: Token counts enable cost estimation
