# DSPy Trace Viewer

A minimal, zero-dependency trace viewer for DSPy applications using OpenTelemetry.

## Features

- 🚀 **Simple**: Single Python file, no database, no build process
- 📊 **Real-time**: Auto-refreshes every 3 seconds
- 🌳 **Hierarchical**: Shows full span tree with parent-child relationships
- 🎯 **DSPy-aware**: Displays LLM inputs/outputs, retrieval docs, tool calls
- 💾 **Lightweight**: In-memory storage (last 200 traces)

## Quick Start

### 1. Install Dependencies

```bash
cd dspy-trace-viewer
```

### 2. Start the Viewer

```bash
uvicorn viewer:app --host 0.0.0.0 --port 4318
```

Or simply:

```bash
python viewer.py
```

### 3. Configure Your DSPy App

Install OpenInference instrumentation:

```bash
pip install openinference-instrumentation-dspy opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

Add to your DSPy code:

```python
from openinference.instrumentation.dspy import DSPyInstrumentor
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk import trace as trace_sdk
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

# Setup OTLP exporter pointing to trace viewer
resource = Resource(attributes={"service.name": "my-dspy-app"})
tracer_provider = trace_sdk.TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    SimpleSpanProcessor(
        OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    )
)
trace_api.set_tracer_provider(tracer_provider)

# Instrument DSPy
DSPyInstrumentor().instrument()

# Now run your DSPy program as normal
import dspy
lm = dspy.LM(model='openai/gpt-4o-mini')
dspy.configure(lm=lm)

class QA(dspy.Signature):
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()

predictor = dspy.ChainOfThought(QA)
result = predictor(question="What is DSPy?")
```

### 4. View Traces

Open your browser to: **http://localhost:4318**

## Architecture

### OTLP Receiver
- **Endpoint**: `POST /v1/traces`
- Accepts OTLP/HTTP protobuf format
- Parses spans and organizes by trace_id

### Storage
- In-memory OrderedDict (LRU eviction)
- Keeps last 200 traces
- Builds parent-child index for tree rendering

### API
- `GET /api/traces` - List recent traces
- `GET /api/traces/{trace_id}` - Get full trace tree
- `GET /api/stats` - Viewer statistics
- `POST /api/reset` - Clear all traces

### UI
- Zero-build static HTML + vanilla JavaScript
- Left pane: trace list with service, timestamp, duration
- Right pane: collapsible span tree with:
  - Span kind badges (LLM, CHAIN, RETRIEVER, TOOL, etc.)
  - Inputs/outputs
  - Token usage
  - Events and errors

## Span Types

The viewer recognizes OpenInference span kinds:

- **LLM** / **CHAT_MODEL**: Language model calls (red)
- **CHAIN**: Prediction modules like ChainOfThought (blue)
- **RETRIEVER**: Retrieval operations (orange)
- **TOOL**: Tool invocations (green)
- **AGENT**: Agent operations (purple)
- **PARSER**: Adapter/parsing operations (pink)

## Configuration

### Environment Variables

For your DSPy app:

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_RESOURCE_ATTRIBUTES=service.name=my-dspy-app
```

### Viewer Settings

Edit `viewer.py` to adjust:

```python
MAX_TRACES = 200  # Max traces to keep in memory
```

Run on different port:

```bash
uvicorn viewer:app --host 0.0.0.0 --port 8080
```

## Use Cases

### Local Development
Perfect for debugging DSPy programs during development. See exactly what prompts are sent, what LLM responses come back, and how modules chain together.

### Optimization/Compilation Debugging
Watch how DSPy teleprompters modify your program's behavior across evaluation runs.

### Performance Analysis
Identify slow spans and bottlenecks in your DSPy pipeline.

## Comparison to Alternatives

| Feature | DSPy Trace Viewer | Phoenix | MLflow |
|---------|------------------|---------|---------|
| Setup | 1 command | Docker or pip + config | Full MLflow stack |
| Storage | In-memory | Database | Database + artifact store |
| Build | None | None | None |
| Best for | Quick local dev | Production monitoring | Full ML lifecycle |
| Dependencies | 4 packages | 10+ packages | 20+ packages |

## Limitations

- **In-memory only**: Traces lost on restart
- **No persistence**: Use Phoenix or Jaeger for production
- **Single instance**: No distributed tracing across services
- **No authentication**: For local use only
- **Limited search**: Basic service filtering only

## Advanced Usage

### With MLflow DSPy Callback

You can also use MLflow's callback-based approach (requires MLflow server):

```python
import mlflow
mlflow.dspy.autolog()

# Your DSPy code runs and traces appear in MLflow UI
```

Then export from MLflow to OTLP and point to this viewer.

### Custom Attributes

Add custom metadata to traces:

```python
from openinference.instrumentation import using_attributes

with using_attributes(
    session_id="user-123",
    tags=["production", "experiment-A"],
    metadata={"version": "1.0.0"}
):
    result = predictor(question="...")
```

### Multiple Services

Run multiple DSPy apps with different service names:

```python
Resource(attributes={"service.name": "rag-pipeline"})
Resource(attributes={"service.name": "chatbot"})
```

Filter in UI by service name.

## Troubleshooting

### No traces appearing

1. Check viewer is running: `curl http://localhost:4318/api/stats`
2. Verify DSPy instrumentation is active
3. Check endpoint URL matches in both viewer and app
4. Look for errors in viewer logs

### Spans missing details

- Ensure you're using OpenInference instrumentation (not generic OTEL)
- Check that semantic conventions are being applied
- Verify DSPy version supports the features you're using

### Memory issues

Reduce `MAX_TRACES` if running on constrained systems:

```python
MAX_TRACES = 50  # Keep fewer traces
```

## Development

### Run tests

```bash
# TODO: Add tests
pytest
```

### Format code

```bash
black viewer.py
```

## Contributing

This is a minimal tool by design. For feature requests:
- Simple additions: Open an issue
- Complex features: Consider using Phoenix or Jaeger instead

## License

MIT

## See Also

- [OpenInference](https://github.com/Arize-ai/openinference) - OTEL instrumentation for LLMs
- [Phoenix](https://github.com/Arize-ai/phoenix) - Full-featured LLM observability platform
- [DSPy](https://github.com/stanfordnlp/dspy) - Programming framework for LLMs
