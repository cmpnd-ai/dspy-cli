# dspy-cli serve

Start an HTTP server that exposes DSPy modules as REST API endpoints.

## Synopsis

```bash
dspy-cli serve [OPTIONS]
```

## Usage

```bash
# Start server with default settings
dspy-cli serve

# Production configuration
dspy-cli serve --no-reload --host 0.0.0.0 --port 8000

# Development with UI
dspy-cli serve --ui --port 3000

# Enable MCP tools
dspy-cli serve --mcp
```

## Description

Starts an HTTP server for local testing or production deployment. Discovers DSPy modules in `src/<package>/modules/` and exposes each as a POST endpoint. Generates request/response schemas from module type hints and provides OpenAPI documentation.

The server watches source files and configuration, restarting automatically on changes (unless `--no-reload` is specified).

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `8000` | Port to run server on (1-65535) |
| `--host` | `0.0.0.0` | Host to bind to |
| `--logs-dir` | `./logs` | Directory for log files |
| `--ui` / `-u` | disabled | Enable web UI for testing |
| `--reload` / `--no-reload` | enabled | Auto-reload on file changes |
| `--save-openapi` / `--no-save-openapi` | enabled | Save OpenAPI spec to file |
| `--openapi-format` | `json` | OpenAPI format (`json` or `yaml`) |
| `--python` | auto-detect | Path to Python interpreter |
| `--system` | disabled | Use system Python instead of venv |
| `--mcp` | disabled | Enable MCP server at `/mcp` |

## Auto-Discovery

The server scans `src/<package>/modules/` for classes that subclass `dspy.Module`, analyzes their `forward()` method signatures, and generates POST endpoints automatically.

**Example module:**

```python
# src/blog_tools/modules/summarizer_predict.py
import dspy
from blog_tools.signatures.summarizer import SummarizerSignature
from typing import Literal, Optional

class SummarizerPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(SummarizerSignature)

    def forward(
        self, 
        blog_post: str, 
        summary_length: Literal['short', 'medium', 'long'], 
        tone: Optional[str]
    ) -> dspy.Prediction:
        return self.predictor(
            blog_post=blog_post, 
            summary_length=summary_length, 
            tone=tone
        )
```

**Generates:**

```
POST /SummarizerPredict
```

### Endpoint Naming

Endpoints match module class names:
- `SummarizerPredict` → `/SummarizerPredict`
- `HeadlineGeneratorCoT` → `/HeadlineGeneratorCoT`
- `TweetExtractorPredict` → `/TweetExtractorPredict`

### Schema Generation

Type hints from `forward()` parameters become JSON request schemas. Default values become optional fields.

**Python signature:**

```python
def forward(
    self,
    text: str,
    options: list[str],
    confidence_threshold: float = 0.8
) -> dspy.Prediction:
    ...
```

**Generated request schema:**

```json
{
  "type": "object",
  "properties": {
    "text": {"type": "string"},
    "options": {
      "type": "array",
      "items": {"type": "string"}
    },
    "confidence_threshold": {
      "type": "number",
      "default": 0.8
    }
  },
  "required": ["text", "options"]
}
```

## Hot Reload

The server watches for changes to:
- All `.py` files in `src/` directory
- `dspy.config.yaml` configuration file
- `.env` environment variables

Saving any watched file triggers an automatic restart (~2 seconds). Disable with `--no-reload` for production deployments.

## Endpoints

Every deployment provides:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/<ModuleName>` | POST | Execute module with JSON request body |
| `/programs` | GET | List all discovered modules and their schemas |
| `/openapi.json` | GET | OpenAPI specification |

With `--ui` enabled:
- `/` serves interactive testing interface

With `--mcp` enabled:
- `/mcp` provides Model Context Protocol server

## Logging

Requests are logged to console by default. Use `--logs-dir` to persist logs per module:

```bash
dspy-cli serve --logs-dir ./logs
```

Creates:
- `logs/SummarizerPredict.log`
- `logs/HeadlineGeneratorPredict.log`

Each log entry includes timestamp, request inputs, response outputs, execution time, and model used.

## Examples

### Basic Usage

```bash
dspy-cli serve
```

Server starts on `http://localhost:8000`. Call modules:

```bash
curl -X POST http://localhost:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{
    "blog_post": "Article text...",
    "summary_length": "short",
    "tone": "professional"
  }'
```

Response:

```json
{
  "summary": "Generated summary text."
}
```

### Development Mode

```bash
dspy-cli serve --ui --logs-dir ./logs --port 3000
```

Enables:
- Interactive web UI at `http://localhost:3000`
- Hot reload on file changes
- Persistent logs in `./logs/`

### Production Mode

```bash
dspy-cli serve --no-reload --host 0.0.0.0 --port 8000
```

Disables hot reload and binds to all network interfaces for production deployment.

### Multiple Parameters

```bash
curl -X POST http://localhost:8000/TaggerPredict \
  -H "Content-Type: application/json" \
  -d '{
    "blog_post": "Content here",
    "max_tags": 5,
    "style": "casual"
  }'
```

### Error Responses

**Validation error (422):**

```bash
curl -X POST http://localhost:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{"blog_post": 123}'
```

```json
{
  "detail": [
    {
      "type": "string_type",
      "loc": ["body", "blog_post"],
      "msg": "Input should be a valid string",
      "input": 123
    }
  ]
}
```

**Missing required field (422):**

```bash
curl -X POST http://localhost:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{}'
```

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "blog_post"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

## Environment Variables

Configure via environment variables or `.env` file:

- `OPENAI_API_KEY` - OpenAI API key
- Model-specific configuration in `dspy.config.yaml`

## Limitations

- Module discovery requires classes to subclass `dspy.Module`
- `forward()` method must have type hints for schema generation

## See Also

- [dspy-cli new](new.md) - Create new projects
- [Deployment Guide](../deployment.md) - Deploy to production
- [OpenAPI Generation](../OPENAPI.md) - API specification details
- [Configuration Guide](../configuration.md) - Model configuration
