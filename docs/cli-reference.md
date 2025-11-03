# CLI Reference

Complete reference for all dspy-cli commands.

## dspy-cli new

Create a new DSPy project with boilerplate structure.

```bash
dspy-cli new PROJECT_NAME [OPTIONS]
```

**Arguments:**

- `PROJECT_NAME` - Name of the project (creates directory)

**Options:**

- `-p, --program-name NAME` - Name of initial program (default: derived from project name)
- `-s, --signature SIGNATURE` - Inline signature string (e.g., `"question -> answer"`)
- `--link-dspy-cli PATH` - Add uv path override for local dspy-cli development

**Examples:**

```bash
# Basic project
dspy-cli new my-project

# With custom program name
dspy-cli new my-project -p custom_program

# With inline signature
dspy-cli new my-project -s "post -> tags: list[str]"

# Complex signature
dspy-cli new my-project -p analyzer -s "text, context: list[str] -> summary"

# Link to local dspy-cli for development
dspy-cli new my-project --link-dspy-cli ../dspy-cli
```

**What it creates:**

```
my-project/
├── src/
│   └── my_project/
│       ├── modules/
│       ├── signatures/
│       ├── optimizers/
│       ├── metrics/
│       └── utils/
├── tests/
├── data/
├── logs/
├── dspy.config.yaml
├── pyproject.toml
├── .env
├── .gitignore
├── Dockerfile
├── .dockerignore
└── README.md
```

---

## dspy-cli serve

Start a local HTTP API server that exposes your DSPy modules.

```bash
dspy-cli serve [OPTIONS]
```

**Options:**

- `--port PORT` - Port to run server on (default: 8000)
- `--host HOST` - Host to bind to (default: 0.0.0.0)
- `--logs-dir DIR` - Directory for logs (default: ./logs)
- `-u, --ui` - Enable web UI for interactive testing
- `--python PATH` - Path to Python interpreter (default: auto-detect)
- `--system` - Use system Python instead of project venv

**Examples:**

```bash
# Basic server
dspy-cli serve

# Custom port and host
dspy-cli serve --port 8080 --host 127.0.0.1

# With interactive UI
dspy-cli serve --ui

# Use specific Python interpreter
dspy-cli serve --python /path/to/venv/bin/python

# Use system Python (skip venv detection)
dspy-cli serve --system
```

**Aliases:**

- `dspy-cli s` - Shorthand for `serve`

**What it does:**

1. Validates you're in a DSPy project directory (looks for `dspy.config.yaml`)
2. Detects project virtual environment (if not already activated)
3. Auto-discovers DSPy modules in `src/<package>/modules/`
4. Starts FastAPI server with endpoints for each module
5. Provides interactive API docs at `/docs`

**Endpoints:**

- `GET /` - Health check
- `GET /docs` - Interactive API documentation
- `POST /predict/{module_name}` - Run a specific module
- `GET /programs` - List all discovered programs

---

## dspy-cli deploy

Deploy a DSPy application to the control plane.

```bash
dspy-cli deploy [OPTIONS]
```

**Options:**

- `--control-url URL` - Control plane URL (default: derived from dspy.config.yaml `host`)
- `--api-key KEY` - API key for authentication (or use `DSPY_CONTROL_API_KEY` env var)
- `--api-key-file PATH` - File containing API key
- `--app-id ID` - Override app_id from dspy.config.yaml
- `--code-dir DIR` - Override code_dir from dspy.config.yaml

**Examples:**

```bash
# Deploy to production (uses host from dspy.config.yaml)
dspy-cli deploy

# Deploy to local control plane
dspy-cli deploy --control-url http://localhost:9000

# With API key
dspy-cli deploy --api-key your-key-here

# Using API key file
dspy-cli deploy --api-key-file ~/.dspy/control.key

# Override app_id
dspy-cli deploy --app-id my-custom-id
```

**What it does:**

1. Reads `dspy.config.yaml` configuration
2. Packages your code as a ZIP file (excludes `.git`, `.venv`, `__pycache__`, etc.)
3. Deploys to control plane via HTTP
4. Saves runtime API key to `~/.dspy/keys/{app_id}.key`
5. Returns deployment information (URL, version, programs)

**Output:**

```
Deploying to https://platform.cmpnd.ai...

Deployment successful!

App ID: my-app
Version: v1
Route: /my-app

Programs:
  • qa_predict
    Stable:  https://platform.cmpnd.ai/my-app/predict/qa_predict
    Version: https://platform.cmpnd.ai/my-app/v1/predict/qa_predict

Key: rtk_abc123...

Runtime API key saved to ~/.dspy/keys/
```

**API Key Resolution:**

dspy-cli looks for API keys in this order:

1. `--api-key` flag
2. `--api-key-file` flag
3. `DSPY_CONTROL_API_KEY` environment variable
4. `~/.dspy/control.key` file

---

## dspy-cli generate

Generate new components in an existing DSPy project.

```bash
dspy-cli generate SUBCOMMAND [OPTIONS]
dspy-cli g SUBCOMMAND [OPTIONS]  # shorthand
```

**Aliases:**

- `dspy-cli g` - Shorthand for `generate`

### Subcommands

#### generate scaffold

Generate a complete module (signature + module + test).

```bash
dspy-cli g scaffold PROGRAM_NAME [OPTIONS]
```

**Arguments:**

- `PROGRAM_NAME` - Name of the program/module

**Options:**

- `-m, --module TYPE` - DSPy module type (default: Predict)
  - Available: `Predict`, `ChainOfThought`, `CoT`, `ProgramOfThought`, `PoT`, `ReAct`, `MultiChainComparison`, `Refine`
- `-s, --signature SIGNATURE` - Inline signature string

**Examples:**

```bash
# Basic Predict module
dspy-cli g scaffold qa

# ChainOfThought module
dspy-cli g scaffold reasoning -m CoT

# With inline signature
dspy-cli g scaffold summarizer -m CoT -s "text: str -> summary: str, key_points: list[str]"

# ReAct agent
dspy-cli g scaffold agent -m ReAct -s "task -> steps: list[str], result"

# Program of Thought
dspy-cli g scaffold calculator -m PoT -s "problem -> code, answer"
```

**What it creates:**

1. **Signature**: `src/<package>/signatures/<name>.py`
2. **Module**: `src/<package>/modules/<name>_<type>.py`
3. **Test**: `tests/test_<name>.py`

---

## Environment Variables

dspy-cli respects these environment variables:

- `DSPY_CONTROL_URL` - Default control plane URL for deployments
- `DSPY_CONTROL_API_KEY` - Default API key for deployments
- `DSPY_CLI_PATH` - Path to local dspy-cli for development (used by `new --link-dspy-cli`)
- `OPENAI_API_KEY` - OpenAI API key (for your DSPy modules)
- Other model API keys as configured in `dspy.config.yaml`

## Virtual Environment Detection

dspy-cli automatically detects and uses your project's virtual environment:

1. Checks if already running in a venv (via `VIRTUAL_ENV`)
2. Looks for `.venv/` in current directory
3. Looks for `venv/` in current directory
4. Checks Python version compatibility (requires 3.9+)
5. Warns if dspy-cli is not installed in project venv

To bypass venv detection, use `--system` flag:

```bash
dspy-cli serve --system
```

## Configuration File

The `dspy.config.yaml` file configures your deployment:

```yaml
# Required: App identifier
app_id: my-app

# Required: Module path (package.module:ClassName)
module_path: my_app.modules.main:MyModule

# Required: Source code directory
code_dir: src

# Optional: Production host
host: platform.cmpnd.ai

# Optional: Model configuration
models:
  default: openai:gpt-4o-mini
  
  registry:
    openai:gpt-4o-mini:
      model: openai/gpt-4o-mini
      env: OPENAI_API_KEY
      max_tokens: 16000
      temperature: 1.0
      model_type: responses
```

## Exit Codes

- `0` - Success
- `1` - General error (validation, network, etc.)
- `130` - Interrupted by user (Ctrl+C)

## Getting Help

```bash
# General help
dspy-cli --help

# Command-specific help
dspy-cli new --help
dspy-cli serve --help
dspy-cli deploy --help
dspy-cli generate --help
```
