# dspy-cli

**Scaffold and serve DSPy applications with ease.**

dspy-cli is a command-line tool for scaffolding and serving [DSPy](https://github.com/stanfordnlp/dspy) applications. It provides convention-based project structure and local development servers.

---

## Quick Start

```bash
# Install with uv (recommended)
uv tool install dspy-cli

# Or with pipx
pipx install dspy-cli

# Create a new DSPy project
dspy-cli new my-project
cd my-project

# Add your API keys to .env
# OPENAI_API_KEY=sk-...

# Install dependencies
uv sync

# Start local development server
dspy-cli serve
```

## Features

- **Project Scaffolding** - Generate complete DSPy projects with best-practice structure
- **Local Development** - Test your DSPy modules locally with hot reload
- **Component Generation** - Add new modules, signatures, and optimizers to existing projects
- **Type-Safe** - Full type hints and signature validation

## Installation

### uv (Recommended)

```bash
uv tool install dspy-cli
```

### pipx

```bash
pipx install dspy-cli
```

### pip

```bash
pip install dspy-cli
```

### Verify Installation

```bash
dspy-cli --version
```

## Your First Project

### 1. Create a new project

```bash
dspy-cli new qa-bot
cd qa-bot
```

This creates a complete project structure:

```
qa-bot/
├── src/
│   └── qa_bot/
│       ├── modules/        # DSPy modules (programs)
│       ├── signatures/     # Input/output signatures
│       ├── optimizers/     # Optimization pipelines
│       └── metrics/        # Evaluation metrics
├── tests/
├── data/
├── dspy.config.yaml        # Configuration
├── pyproject.toml
└── .env                    # API keys (add yours here)
```

### 2. Add your API keys

Edit `.env`:

```bash
OPENAI_API_KEY=sk-...
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Start the development server

```bash
dspy-cli serve
```

This starts a FastAPI server at `http://localhost:8000` with:
- Auto-discovery of DSPy modules
- Interactive API documentation at `/docs`
- Hot reload on code changes

### 5. Test your module

```bash
curl -X POST "http://localhost:8000/predict/qa_bot_predict" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is DSPy?"}'
```

### 6. Generate additional components

```bash
# Add a new ChainOfThought module
dspy-cli g scaffold analyzer -m CoT -s "text -> summary, sentiment"

# Add a ReAct module
dspy-cli g scaffold agent -m ReAct -s "task -> result"
```

## Project Configuration

Edit `dspy.config.yaml` to configure your project:

```yaml
# App identifier (used for routing)
app_id: qa-bot

# Python module path to your DSPy module
module_path: qa_bot.modules.qa_bot_predict:QaBotPredict

# Directory containing your source code
code_dir: src

# Deployment host (production)
host: platform.cmpnd.ai

# Model configuration
models:
  default: openai:gpt-4o-mini
  
  registry:
    openai:gpt-4o-mini:
      model: openai/gpt-4o-mini
      env: OPENAI_API_KEY
      max_tokens: 16000
```

## Development Workflow

### Local Development

```bash
# Start server with UI
dspy-cli serve --ui

# Custom port and host
dspy-cli serve --port 8080 --host 127.0.0.1

# Use specific Python interpreter
dspy-cli serve --python /path/to/venv/bin/python
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src/qa_bot
```

### Deployment

```bash
# Deploy to default (production)
dspy-cli deploy

# Deploy to local control plane
dspy-cli deploy --control-url http://localhost:9000

# Deploy with custom API key
dspy-cli deploy --api-key your-key-here
```

## Project Structure Conventions

dspy-cli follows convention-over-configuration:

- **`src/<package>/modules/`** - DSPy modules (auto-discovered by server)
- **`src/<package>/signatures/`** - Signature definitions
- **`src/<package>/optimizers/`** - Optimization pipelines
- **`src/<package>/metrics/`** - Evaluation metrics
- **`dspy.config.yaml`** - Deployment configuration
- **`.env`** - API keys and secrets (never commit!)

## Examples

### Simple Question Answering

```python
# src/qa_bot/modules/qa_predict.py
import dspy
from qa_bot.signatures.qa import QaSignature

class QaPredict(dspy.Module):
    def __init__(self):
        self.predictor = dspy.Predict(QaSignature)
    
    def forward(self, payload: dict):
        return self.predictor(**payload)
```

```python
# src/qa_bot/signatures/qa.py
import dspy

class QaSignature(dspy.Signature):
    question: str = dspy.InputField(desc="Question to answer")
    answer: str = dspy.OutputField(desc="Answer to the question")
```

### Chain of Thought Reasoning

Generate with:

```bash
dspy-cli g scaffold reasoning -m CoT -s "context: list[str], question -> reasoning, answer"
```

### Multi-Step Agent

Generate with:

```bash
dspy-cli g scaffold agent -m ReAct -s "task, available_tools: list[str] -> steps: list[str], result"
```

## Command Reference

See [CLI Reference](cli-reference.md) for detailed command documentation.

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/cmpnd-ai/optimization-platform/issues)
- **Contributing**: [Contributing Guide](contributing.md)
- **DSPy Documentation**: [dspy.ai](https://dspy.ai)

## Next Steps

- [Explore all CLI commands](cli-reference.md)
- [Learn how to contribute](contributing.md)
- [Read the DSPy documentation](https://dspy.ai)
