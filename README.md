# dspy-cli

A command-line interface tool for creating and serving DSPy projects, inspired by Ruby on Rails.

## Installation

```bash
pip install dspy-cli
```

### Installing for Development/Testing

If you're testing or developing dspy-cli itself:

```bash
# Clone or navigate to the dspy-cli repository
cd /path/to/dspy-cli

# Install in editable mode
pip install -e .

# Now the dspy-cli command is available
dspy-cli --help
```

## Quick Start

### Create a new DSPy project

```bash
dspy-cli new my-project
cd my-project
```

### Create a project with a custom program name

```bash
dspy-cli new my-project -p custom_program
```

### Serve your DSPy programs as an API

```bash
dspy-cli serve --port 8000 --host 0.0.0.0
```

## Features

- **Project scaffolding**: Generate a complete DSPy project structure with boilerplate code
- **Convention over configuration**: Organized directory structure for modules, signatures, optimizers, and metrics
- **HTTP API server**: Automatically serve your DSPy programs as REST endpoints
- **Flexible configuration**: YAML-based model configuration with environment variable support
- **Logging**: Request logging to both STDOUT and per-module log files

## Project Structure

When you create a new project, dspy-cli generates the following structure:

```
my-project/
├── pyproject.toml
├── dspy.config.yaml       # Model registry and configuration
├── .env                   # API keys and secrets
├── README.md
├── src/
│   └── dspy_project/      # Importable package
│       ├── __init__.py
│       ├── modules/       # DSPy program implementations
│       ├── signatures/    # Reusable signatures
│       ├── optimizers/    # Optimizer configurations
│       ├── metrics/       # Evaluation metrics
│       └── utils/         # Shared helpers
├── data/
├── logs/
└── tests/
```

## Commands

### `new`

Create a new DSPy project with boilerplate structure.

```bash
dspy-cli new [PROJECT_NAME] [OPTIONS]
```

**Options:**
- `-p, --program-name TEXT`: Name of the initial program (default: converts project name)

### `serve`

Start an HTTP API server that exposes your DSPy programs.

```bash
dspy-cli serve [OPTIONS]
```

**Options:**
- `--port INTEGER`: Port to run the server on (default: 8000)
- `--host TEXT`: Host to bind to (default: 0.0.0.0)

**Endpoints:**
- `GET /programs`: List all discovered programs with their schemas
- `POST /{program}`: Execute a program with JSON payload

## Configuration

### dspy.config.yaml

Configure your language models and routing:

```yaml
models:
  default: openai:gpt-4o-mini
  registry:
    openai:gpt-4o-mini:
      model: openai/gpt-4o-mini
      env: OPENAI_API_KEY
      max_tokens: 16000
      temperature: 1.0
      model_type: chat
    anthropic:sonnet-3.5:
      model: anthropic/claude-3-5-sonnet
      env: ANTHROPIC_API_KEY
      model_type: chat

# Optional: per-program model overrides
program_models:
  MySpecialProgram: anthropic:sonnet-3.5
```

### .env

Store your API keys and secrets:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## License

MIT
