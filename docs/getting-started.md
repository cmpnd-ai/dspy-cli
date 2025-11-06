# Getting Started

## The Problem

Building reliable LLM applications is hard. Prompts break when requirements change. Manual tuning is tedious. Production debugging is a nightmare.

**Get from idea to working DSPy application to API endpoint in 5 minutes.**

## Prerequisites

- Python 3.9+
- uv ([install uv](https://docs.astral.sh/uv/))
- An LLM API key (OpenAI, Anthropic, or local models)

## Installation

```bash
uv install dspy-cli
```

## Simple → Real-world → Production-ready

### 1. Create Your Project

```bash
dspy-cli new qa-bot -s "question -> answer"
cd qa-bot
echo "OPENAI_API_KEY=sk-..." > .env
uv sync
```

**What this solves:** Manual prompt engineering for every task. DSPy generates optimized prompts automatically from your signature.

### 2. Start Building

```bash
dspy-cli serve
```

```
✓ Configuration loaded

Discovered Programs:
  • QaBotPredict
    POST /QaBotPredict

Server starting on http://0.0.0.0:8000
```

**Before:** Writing Flask/FastAPI boilerplate, managing routes, validating inputs.  
**After:** Automatic REST API with input and output validation.

### 3. Test It

```bash
curl -X POST http://localhost:8000/QaBotPredict \
  -H "Content-Type: application/json" \
  -d '{"question": "What is DSPy?"}'
```

Or add the `--ui` flag and open `http://localhost:8000/` for interactive testing.

!!! success "Why This Matters"
    You now have a working LLM application. No prompt templates. No brittle string formatting. Just type-safe inputs and outputs.

### 4. Add Real-World Features

Need chain-of-thought reasoning?

```bash
dspy-cli g scaffold analyzer -m CoT -s "text, context: list[str] -> summary, key_points: list[str]"
```

**What breaks in traditional approaches:**
- Chaining prompts manually = context loss
- Parsing structured outputs = fragile regex
- Managing multi-step workflows = error-prone state
- Engineering concerns are bundles together into one big string prompt that is hard to reason about and debug.

**DSPy prevents this:** Modules compose cleanly. Signatures enforce types. Programs are testable Python.

Restart the server and your new `/AnalyzerCoT` endpoint is live.

## Make It Better: Optimization

Your app works. Now make it **great**.

DSPy supports optimization through its Python API. You can use optimizers like `BootstrapFewShot` to automatically improve your prompts based on training examples:

```python
import dspy
from dspy.teleprompt import BootstrapFewShot

# Define your metric
def accuracy(example, pred, trace=None):
    return example.answer.lower() == pred.answer.lower()

# Optimize
optimizer = BootstrapFewShot(metric=accuracy)
optimized_program = optimizer.compile(
    student=qa_bot,
    trainset=training_examples
)

# Then load your optimized program inside module init!
# TODO: (Isaac) Does this work?
class QaBot(dspy.Module):
    def __init__(self):
        self.load("path/to/optimized_program.<json|pkl>")
```

**Before optimization:** Generic prompts. Inconsistent quality. Trial-and-error tuning.  
**After optimization:** Prompts tailored to your task. Measurable improvements. Data-driven.

See the [DSPy documentation](dspy.ai) for more on optimization strategies.

## Module Types

| Type | Flag | Use Case |
|------|------|----------|
| Predict | default | Simple input → output |
| ChainOfThought | `-m CoT` | Show reasoning steps |
| ReAct | `-m ReAct` | Tool-using agents |
| ProgramOfThought | `-m PoT` | Code generation |

## Project Structure

```
qa-bot/
├── src/qa_bot/
│   ├── modules/         # Your DSPy programs (auto-discovered)
│   ├── signatures/      # Input/output type definitions
│   ├── optimizers/      # Prompt optimization configs
│   ├── metrics/         # Custom evaluation metrics
│   └── utils/           # Helper functions
├── data/                # Example data
├── logs/                # Server logs
├── tests/               # Automatically generated test files
├── dspy.config.yaml     # Model and LLM provider settings
├── .env                 # API keys (never committed)
├── Dockerfile           # Production deployment
└── pyproject.toml       # Dependencies and package config
```

## Development Workflow

### Web UI

```bash
dspy-cli serve --ui
```

Visual testing interface at `http://localhost:8000`.

### Custom Port

```bash
dspy-cli serve --port 3000
```

## Common Patterns

### Multiple Inputs

```bash
dspy-cli g scaffold search -s "query, context: list[str] -> answer, sources: list[str]"
```

### Typed Outputs

```bash
dspy-cli g scaffold classifier -s "text -> category, confidence: float, reasoning"
```

### Complex Types

```bash
# Supports: str, int, float, bool, list[T], dict, Any
dspy-cli g scaffold extractor -s "document -> entities: list[str], metadata: dict"
```

## Next Steps

**See Real Examples:**
- [blog-tools](../examples/blog-tools/) - Content generation pipeline
- [code-review-agent](../examples/code-review-agent/) - Code analysis automation

**Configure Models:**
- [Configuration Guide](configuration.md) - LLM providers, custom models

**Deploy:**
- [Deployment](deployment.md) - Ship to production

## Troubleshooting

**Module not found error:**

This typically happens if you are trying to import a dependency, but you're not using the correct venv.
```bash
cd qa-bot  # Ensure you're in the project directory
uv venv
source .venv/bin/activate
```

To use an external dependency, you need to:
1. Have it in the pyproject.toml file
2. Make sure that you are using the correct venv
The global tool install of dspy-cli won't work with external dependencies.

If you run:
```bash
which dspy-cli
```
The global tool will be at: `~/.local/bin/dspy-cli` (or equivalent on your system)
The local install will be at: `./venv/bin/dspy-cli`. The local install will allow you to use external dependencies.


**API key errors:**
```bash
cat .env  # Check .env file
export OPENAI_API_KEY=sk-...  # Ensure key is set
```

**Port already in use:**
```bash
dspy-cli serve --port 8080
```

**Virtual environment issues:**
```bash
rm -rf .venv && uv sync
source .venv/bin/activate
```

---

**You're ready to build.** Start with a working system, iterate with real data, optimize for production.
