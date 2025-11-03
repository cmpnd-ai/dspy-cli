# dspy-cli

A command-line interface tool for creating and serving DSPy projects, inspired by Ruby on Rails.

## Installation

```bash
uv add dspy-cli
```

### Installing for Development/Testing

If you're testing or developing dspy-cli itself:

```bash
# Clone or navigate to the dspy-cli repository
cd /path/to/dspy-cli

# Sync dependencies
uv sync --extra dev

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

### Create a project with a custom signature

```bash
dspy-cli new blog-tagger -s "post -> tags: list[str]"
```

### Serve your DSPy programs as an API

```bash
dspy-cli serve --port 8000 --host 0.0.0.0
```

## Features

- **Project scaffolding**: Generate a complete DSPy project structure with boilerplate code
- **Code generation**: Quickly scaffold new DSPy programs with signatures and modules using Rails-style generators
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
- `-s, --signature TEXT`: Inline signature string (e.g., `"question -> answer"` or `"post -> tags: list[str]"`)

**Examples:**

```bash
# Basic project
dspy-cli new my-project

# With custom program name
dspy-cli new my-project -p custom_program

# With custom signature
dspy-cli new blog-tagger -s "post -> tags: list[str]"

# With both program name and signature
dspy-cli new analyzer -p text_analyzer -s "text, context: list[str] -> summary, sentiment: bool"
```

### `generate` (alias: `g`)

Generate new components in an existing DSPy project.

```bash
dspy-cli generate scaffold PROGRAM_NAME [OPTIONS]
dspy-cli g scaffold PROGRAM_NAME [OPTIONS]
```

**Options:**
- `-m, --module TEXT`: DSPy module type to use (default: Predict)
  - Available: `Predict`, `ChainOfThought` (or `CoT`), `ProgramOfThought` (or `PoT`), `ReAct`, `MultiChainComparison`, `Refine`
- `-s, --signature TEXT`: Inline signature string (e.g., `"question -> answer"`)

**Examples:**

```bash
# Basic scaffold with default Predict module
dspy-cli g scaffold categorizer

# Scaffold with ChainOfThought
dspy-cli g scaffold categorizer -m CoT

# Scaffold with custom signature
dspy-cli g scaffold qa -m CoT -s "question -> answer"

# Complex signature with types
dspy-cli g scaffold search -s "query, context: list[str] -> answer, confidence: float"
```

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
    anthropic:sonnet-4-5:
      model: anthropic/claude-sonnet-4-5
      env: ANTHROPIC_API_KEY
      model_type: chat

# Optional: per-program model overrides
program_models:
  MySpecialProgram: anthropic:sonnet-4-5
```

### .env

Store your API keys and secrets:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## License

MIT
