# dspy-cli

Deploy [DSPy](https://dspy.ai/) programs as HTTP APIs in minutes.

**Get started** → [Getting Started](getting-started.md)  
**Deploy** → [Deployment Guide](deployment.md)

## What is dspy-cli?

Turns DSPy modules into production-ready HTTP APIs. Scaffolds projects, auto-discovers modules as JSON endpoints, and packages everything in Docker. Use it to ship LLM services fast with minimal ops.

**Three commands:**

- `new` — Create a project with directory structure, initial program, configuration, and Dockerfile
- `generate` — Add programs, signatures, and modules with proper imports
- `serve` — HTTP API with auto-detected modules, hot-reload, and testing UI

## Prerequisites

- Python 3.11+ and `uv` (or pipx/pip) installed
- A model provider API key (e.g., OpenAI)

## Quick Start

```bash
# Install
uv tool install dspy-cli

# Create project (interactive mode - recommended)
dspy-cli new

# Or with arguments
dspy-cli new my-feature -s "text -> summary"

# Serve locally
cd my-feature && dspy-cli serve
```

Access your API at `http://localhost:8000/{ModuleName}` and the testing UI at `http://localhost:8000/`.

## How it works

**Discovery → Routing → Execution**: dspy-cli scans for DSPy modules, creates `POST /{ModuleName}` endpoints with JSON schemas from signatures, validates requests, and runs your module's forward/predict.

**Example:**

```python
import dspy

class Rewrite(dspy.Signature):
    text: str = dspy.InputField()
    cleaned: str = dspy.OutputField()

class Rewriter(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(Rewrite)
    
    def forward(self, text: str) -> dspy.Prediction:
        return self.predict(text=text)
```

**Becomes:** `POST /Rewriter` with body `{"text": "..."}` → response `{"cleaned": "..."}`

**Try it:**

```bash
curl -X POST http://localhost:8000/Rewriter \
  -H "Content-Type: application/json" \
  -d '{"text":"make this shorter"}'
```

## Deploy

Your project includes a production-ready Docker container. Deploy to [Fly.io](deployment.md#flyio), [Render](deployment.md#render), [AWS](deployment.md#aws), or any Docker platform. See the [Deployment Guide](deployment.md).

## Architecture

**Project structure:**

```text
my-feature/
├── modules/       # DSPy modules (exposed as endpoints)
├── signatures/    # DSPy signatures (request/response schema)
├── app/           # Server, discovery, settings
├── Dockerfile
├── .env
├── dspy.config.yaml
└── pyproject.toml

```

**Request flow:** JSON request → validate against signature → module forward/predict → JSON response

**Discovery:** Exposes `dspy.Module` subclasses as `POST /{ClassName}` endpoints with schemas from signatures

## Top Tasks

**Create** — Get up and running with your first DSPy module

- [Getting Started](getting-started.md)
- [Examples](../examples/)

**Configure** — Environment variables and model settings

- [Configuration](configuration.md)
- [Environment variables](configuration.md#environment-variables)
- [Model registry](configuration.md#model-registry)

**Deploy** — Ship to production

- [Deployment Guide](deployment.md)
- [Production checklist](deployment.md#production-checklist)

**Operate** — Test and iterate

- [Testing UI & OpenAPI docs](getting-started.md#testing-ui)
- [Commands Reference](commands/)

## What You Get

- **Project scaffolding** — Standardized structure with DSPy signatures, modules, and Docker configs
- **HTTP interface** — FastAPI endpoints with automatic module discovery and OpenAPI docs
- **Hot-reload server** — Built-in testing UI with live code updates
- **Production-ready** — Deploy to any Docker platform

**Defaults:** Local server at `http://localhost:8000`, testing UI at `/`, no auth (add via platform or middleware)

---

Run `dspy-cli --help` for all commands. View more [examples](../examples/) on GitHub.
