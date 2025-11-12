# dspy-cli

## Overview

dspy-cli is a deployment framework for LLM-backed application features. It generates standardized project structure and HTTP interfaces for DSPy modules, reducing setup time from hours to minutes.

## The Problem

Embedding LLM-backed features into applications requires:

- Containerizing the runtime environment
- Exposing a stable HTTP interface
- Wiring API keys and secrets
- Implementing health checks and logging
- Configuring routing and auto-discovery
- Setting up local development and testing infrastructure

This overhead blocks small-to-medium AI features from shipping. A DSPy module that takes 30 minutes to write can require 4+ hours of infrastructure work before it's usable in a browser extension, Notion plugin, or web application.

## What dspy-cli Provides

**Project Scaffolding**
- Standardized directory structure with modules, signatures, and configurations
- Auto-generated DSPy signatures from type specifications
- Docker configurations for local development and production deployment

**HTTP Interface**
- FastAPI-based REST endpoints with automatic module discovery
- OpenAPI documentation and interactive testing UI
- Request/response validation via Pydantic models

**Development Workflow**
- Hot-reload server for rapid iteration
- Built-in testing UI with form-based request construction
- Type-safe module signatures with validation

**Deployment Infrastructure**
- Production-ready Docker containers
- Environment variable management
- Inference API key authentication
- Integration with any platform that can use a Dockerfile: Fly.io, Render, AWS, and other container platforms

## What Are AI Features?

In this context, "AI features" refers to application-embedded functionality backed by LLMs. These are exposed as HTTP endpoints and called by client applications—browser extensions, Notion workspaces, email clients, web servers.

This differs from:
- **Agentic Applications** where the LLM controls the conversation flow
- **Batch pipelines** that process large datasets asynchronously

Examples include text summarization APIs for browser extensions, classification endpoints for content management systems, and generation services for productivity tools.

## Architecture

dspy-cli applications follow a standard structure:

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

**Request Flow:**
1. HTTP request → FastAPI endpoint
2. Request body validated against Pydantic signature
3. DSPy module executes with validated inputs
4. Response serialized and returned

**Module Discovery:**
Modules in `src/*/modules/` are automatically registered as endpoints at `/{ModuleName}`. No manual routing configuration required.

## Quick Start

```bash
# Install
uv tool install dspy-cli

# Create project
dspy-cli new my-feature -s "text -> summary"
cd my-feature && uv sync

# Configure
echo "OPENAI_API_KEY=sk-..." > .env

# Serve locally
dspy-cli serve --ui
```

Access the API at `http://localhost:8000/{ModuleName}` and testing UI at `http://localhost:8000/`.

See the [Getting Started Guide](getting-started.md) for detailed walkthrough.

## Use Cases

**Browser Extensions**
HTTP endpoints for summarization, extraction, or classification that extensions call on user-triggered events.

**Content Management Integration**
Embedded generation or tagging services for platforms like Notion, Confluence, or custom CMSs.

**Application Microservices**
Standalone intelligence services that web or mobile applications consume via REST APIs.

## Next Steps

- [Getting Started Guide](getting-started.md) - Complete setup and first deployment
- [Commands Reference](commands/) - CLI command documentation
- [Configuration](configuration.md) - Model settings and environment variables
- [Examples](https://github.com/cmpnd-ai/dspy-cli-tool/tree/main/examples) - Sample projects and patterns

```bash
dspy-cli --help     # View all commands
```
