# dspy-cli

[![Documentation](https://img.shields.io/badge/docs-cmpnd--ai.github.io-blue)](https://cmpnd-ai.github.io/dspy-cli-tool/)
[![PyPI](https://img.shields.io/pypi/v/dspy-cli)](https://pypi.org/project/dspy-cli/)

CLI for deploying DSPy programs as HTTP APIs. Auto-generates endpoints, OpenAPI specs, and Docker configs.

Reduces deployment setup from hours to minutes for developers embedding LLM features in applications.

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

- Auto-discovery of modules as HTTP endpoints
- Docker configs and OpenAPI specs generated
- Hot reload development server
- Model switching via config file
- MCP tool support

## Commands

```bash
dspy-cli new <name> [-s "input -> output"]    # Create project
dspy-cli serve [--ui]                          # Start HTTP server
dspy-cli g scaffold <program> [-m CoT]         # Add module to project
```

See [Command Reference](docs/commands/) for complete documentation.

## Documentation

See the full docs at: [https://cmpnd-ai.github.io/dspy-cli-tool/](https://cmpnd-ai.github.io/dspy-cli-tool/)

- [Getting Started](docs/getting-started.md) - Quickstart guide
- [Commands](docs/commands/) - CLI reference
- [Configuration](docs/configuration.md) - Model and environment settings
- [Examples](examples/) - Sample projects

## License

MIT
