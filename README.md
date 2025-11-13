# dspy-cli

Deploy DSPy programs as HTTP APIs with standard containerization, routing, and OpenAPI specifications. Setup time: 3-5 minutes.

**For:** Developers embedding AI features in existing applications (Chrome extensions, Notion automations, web apps) who need HTTP endpoints without manual infrastructure work.

**Problem:** Prototype DSPy modules work locally but require Docker configs, API boilerplate, and route management to deploy. This creates friction between development and production.

**Solution:** Convention-based project structure with auto-discovery. Define signatures, implement modules, deploy. Infrastructure handled automatically.

## Quick Start

```bash
# Install
uv tool install dspy-cli

# Create project
dspy-cli new blog-tagger -s "post -> tags: list[str]"
cd blog-tagger

# Serve locally
dspy-cli serve
```

Test the endpoint:

```bash
curl -X POST http://localhost:8000/BlogTaggerPredict \
  -H "Content-Type: application/json" \
  -d '{"post": "How to build Chrome extensions with AI..."}'
```

Response:

```json
{
  "tags": ["chrome-extensions", "ai", "development", "javascript"]
}
```

## Features

- **Auto-discovery** - Modules in `src/*/modules/` automatically exposed as HTTP endpoints
- **Standard containers** - Docker image generation with FastAPI server included
- **OpenAPI specs** - Auto-generated from DSPy signatures for integration with tools and clients
- **Hot reload** - Edit modules without restarting the development server
- **Model configuration** - Switch LLMs via config file without code changes
- **MCP tool integration** - Served programs work as MCP tools for AI assistants
- **Convention-based structure** - Organized directories for modules, signatures, optimizers, metrics

## Project Structure

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

### Create Project

```bash
dspy-cli new PROJECT_NAME [OPTIONS]
```

Options:
- `-s, --signature TEXT` - Inline signature (e.g., `"question -> answer"`)
- `-p, --program-name TEXT` - Initial program name

### Generate Components

```bash
dspy-cli generate scaffold PROGRAM_NAME [OPTIONS]
```

Options:
- `-m, --module TEXT` - Module type (`Predict`, `ChainOfThought`, `ReAct`)
- `-s, --signature TEXT` - Inline signature (e.g. "question -> answer")

### Serve Locally

```bash
dspy-cli serve [--port PORT] [--host HOST]
```

Auto-generated endpoints:
- `GET /programs` - List all programs with schemas
- `POST /{program}` - Execute program with JSON payload

### Deploy

```bash
flyctl launch
flyctl secrets set OPENAI_API_KEY=your-key-here
flyctl deploy
```

See [Deployment Guide](docs/deployment.md) for detailed instructions and other platforms.

## Configuration

### Model Settings

`dspy.config.yaml`:

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

# Per-program overrides
program_models:
  MySpecialProgram: anthropic:sonnet-4-5
```

### Environment Variables

`.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

See [Configuration Guide](docs/configuration.md) for complete settings reference.

## Integration Examples

### Chrome Extension

```javascript
async function summarizePage(content) {
  const response = await fetch('https://your-app.fly.dev/summarizer', {
    method: 'POST',
    body: JSON.stringify({ content }),
    headers: { 'Content-Type': 'application/json' }
  });
  return response.json();
}
```

### Python Client

```python
import requests

def tag_content(page_content):
    response = requests.post(
        'https://your-app.fly.dev/BlogTaggerPredict',
        json={'post': page_content}
    )
    return response.json()['tags']
```

### JavaScript/TypeScript

```javascript
fetch('https://your-app.fly.dev/analyzer', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ 
    text: document.body.innerText,
    context: ['documentation', 'technical'] 
  })
})
.then(res => res.json())
.then(data => console.log(data.summary, data.sentiment));
```

## Development Installation

For contributing or testing dspy-cli itself:

```bash
cd /path/to/dspy-cli
uv sync --extra dev
dspy-cli --help
```

Run tests:

```bash
cd dspy-cli
uv run pytest
```

## Next Steps

- [Architecture Overview](docs/architecture.md) - Project structure and design decisions
- [CLI Reference](docs/cli-reference.md) - Complete command documentation
- [Configuration Guide](docs/configuration.md) - Model settings and environment variables
- [Deployment Guide](docs/deployment.md) - Production deployment workflows
- [MCP Integration](docs/mcp-integration.md) - Using with AI assistants

## License

MIT
