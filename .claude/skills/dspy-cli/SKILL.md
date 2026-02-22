---
name: dspy-cli
description: Reference for using dspy-cli to create, develop, test, and deploy DSPy projects. Use when working in a dspy-cli project or when the user needs help with dspy-cli commands, configuration, modules, gateways, or deployment.
---

# dspy-cli

CLI tool for creating and serving [DSPy](https://dspy.ai) projects. Handles scaffolding, module discovery, and running a FastAPI server that exposes DSPy modules as HTTP endpoints.

```bash
dspy-cli new my-project                                    # Create project
cd my-project
dspy-cli g scaffold analyzer -m CoT -s "text -> summary"   # Add program
dspy-cli serve                                             # Dev server
dspy-cli serve --no-reload --auth                          # Production
```

## Commands

### `dspy-cli new [project_name]`

Interactive if name omitted. Options:

- `-p, --program-name` — Initial program name (default: derived from project)
- `-s, --signature` — Inline signature (default: `"question -> answer"`)
- `-m, --module-type` — Module type: `Predict`, `CoT`, `ReAct`, `PoT`, `Refine`, `MultiChainComparison`
- `--model` — LiteLLM model string (e.g. `openai/gpt-4o`)
- `--api-key` — Stored in `.env`

### `dspy-cli g scaffold <name>`

Generate signature + module. Alias: `generate scaffold`.

- `-m, --module` — Module type (default: `Predict`)
- `-s, --signature` — Inline signature

Creates: `src/<pkg>/signatures/<name>.py` and `src/<pkg>/modules/<name>_<suffix>.py`

### `dspy-cli g signature <name>`

Signature file only. `-s` for inline signature.

### `dspy-cli g module <name>`

Module file only. `-m` for module type.

### `dspy-cli g gateway <name>`

- `-t, --type` — `api` (default) or `cron`
- `-p, --path` — Custom HTTP path (API gateways)
- `-s, --schedule` — Cron expression (default: `"0 * * * *"`)
- `--public/--private` — Auth requirement (default: `--private`)

### `dspy-cli serve`

Alias: `s`. Start FastAPI server.

- `--port` (8000), `--host` (0.0.0.0)
- `--reload/--no-reload` (default: reload on)
- `--auth/--no-auth` — Bearer token via `DSPY_API_KEY`
- `--mcp` — Enable Model Context Protocol at `/mcp`
- `--sync-workers` — Thread pool size (default: `min(32, cpu+4)`)
- `--save-openapi/--no-save-openapi`, `--openapi-format json|yaml`
- `--python` — Path to interpreter, `--system` — Use system Python
- `--logs-dir` — Inference log directory (default: `./logs`)

## Project Structure

```
my-project/
├── src/my_project/
│   ├── modules/       # DSPy modules (auto-discovered)
│   ├── signatures/    # Signature definitions
│   ├── gateways/      # API/Cron gateways (optional)
│   ├── optimizers/    # Optimizer configs
│   ├── metrics/       # Evaluation metrics
│   └── utils/
├── logs/              # JSONL inference logs (one per program)
├── dspy.config.yaml   # Model registry + server config
├── .env               # API keys (gitignored)
├── pyproject.toml
└── Dockerfile
```

**Naming:** project dirs use hyphens (`blog-categorizer`), packages use underscores (`blog_categorizer`), files lowercase, classes PascalCase.

## Configuration

### dspy.config.yaml

```yaml
app_id: my-project

models:
  default: my-model
  registry:
    my-model:
      model: openai/gpt-4o-mini       # LiteLLM model string
      api_key: ${{ env.OPENAI_API_KEY }}
      # model_type: chat  max_tokens: 1000  temperature: 0.7  cache: false
    local:
      model: openai/llama3
      api_base: http://localhost:11434/v1  # Ollama, vLLM, etc.
      api_key: not-needed

program_models:                        # Per-program model overrides
  ExpensiveProgram: claude-opus

server:                                # All optional
  sync_worker_threads: 16
  max_concurrent_per_program: 20       # 429 when exceeded
  cors_origins: "*"                    # Or: ["https://app.example.com"]
```

### .env

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DSPY_API_KEY=...           # For --auth mode
DSPY_CORS_ORIGINS=*        # Overrides config
```

## Module Types

| `-m` value | Suffix | DSPy class |
|-----------|--------|------------|
| `Predict` | `_predict` | `dspy.Predict` |
| `CoT` | `_cot` | `dspy.ChainOfThought` |
| `PoT` | `_pot` | `dspy.ProgramOfThought` |
| `ReAct` | `_react` | `dspy.ReAct` |
| `MultiChainComparison` | `_mcc` | `dspy.MultiChainComparison` |
| `Refine` | `_refine` | `dspy.Refine` |

## Signatures

Pattern: `inputs -> outputs`. Types: `str`, `int`, `float`, `bool`, `list[str]`, `dict[str, int]`, `dspy.Image`.

```
"question -> answer"
"text -> summary, sentiment: bool"
"context: list[str], question -> answer, confidence: float"
```

## Module Discovery

Server scans `src/<package>/modules/*.py`. Valid modules must:
1. Subclass `dspy.Module`
2. Be defined in that file (not imported)
3. Not start with `_`
4. Have `forward()`

No `pip install -e .` needed — uses `importlib.util.spec_from_file_location`.

```python
import dspy

class QA(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question: str) -> dspy.Prediction:
        return self.predict(question=question)
```

### Async support

Add `aforward()` to bypass the thread pool (runs on event loop directly):

```python
async def aforward(self, question: str) -> dspy.Prediction:
    return await self.predict.acall(question=question)
```

`forward()` is required by DSPy's `__call__` (optimizers, notebooks, scripts depend on it). `aforward()` is server-only. If you keep both, logic must stay in sync.

## Server Endpoints

- `POST /{ProgramName}` — Execute program
- `POST /{ProgramName}/{GatewayName}` — Execute through gateway
- `GET /programs` — List programs
- `GET /health/live` — Liveness (200 if running)
- `GET /health/ready` — Readiness (200 when LMs init'd, 503 otherwise)
- `GET /openapi.json` — OpenAPI spec
- `GET /` — Web UI
- `GET /api/metrics` — Metrics (`?sort_by=calls&order=desc`)
- `GET /api/logs/{program_name}` — Inference logs

## Gateways

### API Gateway

```python
from dspy_cli.gateway import APIGateway

class SlackWebhook(APIGateway):
    path = "/webhooks/slack"
    requires_auth = False

    def to_pipeline_inputs(self, request):
        return {"text": request["event"]["text"]}

    def from_pipeline_output(self, output):
        return {"text": output["response"]}

class MyModule(dspy.Module):
    gateway = SlackWebhook()
```

### Cron Gateway

```python
from dspy_cli.gateway import CronGateway

class HourlyCheck(CronGateway):
    schedule = "0 * * * *"
    use_batch = True
    num_threads = 4

    async def get_pipeline_inputs(self):
        return [{"text": item["content"], "_meta": {"id": item["id"]}}
                for item in await fetch_pending()]

    async def on_complete(self, inputs, output):
        await update_record(inputs["_meta"]["id"], output)

class MyModule(dspy.Module):
    gateway = HourlyCheck()
```

## Concurrency

- **Sync modules:** Bounded thread pool (`min(32, cpu+4)` default). `dspy.context()` propagates into workers.
- **Async modules:** Event loop direct. No thread overhead.
- **Backpressure:** Per-program semaphore (default 20). Queues up to 30s, then 429.

## Auth

`dspy-cli serve --auth` — requires `DSPY_API_KEY` env var. Auto-generates if unset.

```bash
curl -H "Authorization: Bearer $DSPY_API_KEY" http://localhost:8000/MyProgram \
  -H "Content-Type: application/json" -d '{"question": "hello"}'
```

Web UI uses session cookies via `/login`.

## Testing

```bash
uv sync --dev && pytest
```

```python
import dspy
from my_project.modules.qa_predict import QAPredict

dspy.settings.configure(lm=dspy.LM("openai/gpt-4o-mini"))
result = QAPredict()(question="What is DSPy?")
```

## Deployment

```bash
docker build -t my-project .
docker run -p 8000:8000 --env-file .env my-project
```

Generated Dockerfile: Python 3.11 slim, `uv sync`, serves with `--auth --no-reload`.

Production flags: `--no-reload --auth --host 0.0.0.0 --sync-workers N`
