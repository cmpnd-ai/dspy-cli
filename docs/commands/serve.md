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

Starts an HTTP server for local testing or production deployment. Discovers DSPy modules in `src/<package>/modules/` and exposes each as a POST endpoint.

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

Discovers modules in `src/<package>/modules/` and generates endpoints from class names. Schemas generated from `forward()` type hints. See [OpenAPI Reference](../OPENAPI.md).

## Hot Reload

Watches `.py` files in `src/`, `dspy.config.yaml`, and `.env` for changes. Restarts automatically (~2s). Disable with `--no-reload` for production.

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

Logs to console by default. Use `--logs-dir` to write per-module JSON logs with request/response data, execution time, and model info.

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

### Production Mode

```bash
dspy-cli serve --no-reload --host 0.0.0.0 --port 8000
```

Disables hot reload and binds to all network interfaces for production deployment.

## Error Responses

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

See [Configuration](../configuration.md) for environment variable and model configuration details.

## Limitations

- Module discovery requires classes to subclass `dspy.Module`
- `forward()` method must have type hints for schema generation

## See Also

- [dspy-cli new](new.md) - Create new projects
- [Deployment Guide](../deployment.md) - Deploy to production
- [OpenAPI Reference](../OPENAPI.md) - API specification details
- [Configuration Guide](../configuration.md) - Model configuration
