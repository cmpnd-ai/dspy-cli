# dspy-cli serve

Start HTTP API server for DSPy programs — instantly exposes your programs as REST endpoints.

## Usage

```bash
dspy-cli serve [OPTIONS]
```

## What Happens

```bash
$ dspy-cli serve
Starting DSPy API server...

✓ Configuration loaded

Discovered Programs:

  • QaBotPredict
    POST /QaBotPredict

Additional Endpoints:

  GET /programs - List all programs and their schemas

============================================================
Server starting on http://localhost:8000
============================================================
```

## Options

- `--port` - Server port [default: 8000]
- `--host` - Bind host [default: 0.0.0.0]
- `--logs-dir` - Logs directory [default: ./logs]
- `--ui`, `-u` - Enable web UI
- `--python` - Python interpreter path
- `--system` - Use system Python (skip venv)

## Examples

```bash
# Simple: Start with defaults (port 8000)
dspy-cli serve


# Custom port: Avoid conflicts
dspy-cli serve --port 8080

# With UI: Interactive testing interface
dspy-cli serve --ui

# Production: External access + specific port
dspy-cli serve --host 0.0.0.0 --port 8000
```

## Endpoints

```bash
GET  /programs                # List available programs
POST /{ModuleClassName}       # Call program (e.g., /QaBotPredict)
```

## Testing

```bash
# List programs
curl http://localhost:8000/programs

# Call a program
curl -X POST http://localhost:8000/QaBotPredict \
  -H "Content-Type: application/json" \
  -d '{"question": "What is DSPy?"}'
```
