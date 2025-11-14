# Quickstart: Create, Serve, Deploy, Integrate

Deploy a DSPy AI application as a REST API in 5 minutes.

**Time to complete:** 5-10 minutes

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) package manager
- LLM API key (OpenAI, Anthropic, or compatible provider)

## 1. Install CLI

```bash
uv tool install dspy-cli
```

Verify installation:

```bash
dspy-cli --version
```

## 2. Create Project

### Interactive Mode (Recommended)

```bash
dspy-cli new
```

You'll be prompted for:
- **Project name:** `email-subject`
- **First program name:** `email_subject` (default, or customize)
- **Module type:** Choose from Predict, ChainOfThought, ReAct, etc.
- **Signature:** `body, sender, context -> subject, tone, priority`
  - Type `?` for guided field-by-field input
- **Model:** `openai/gpt-4o-mini` (or any LiteLLM-compatible model)
- **API Key:** Enter your key or press Enter to configure later

**Expected output:**
```
Creating new DSPy project: email-subject
  Package name: email_subject
  Initial program: email_subject
  Module type: Predict
  Signature: body, sender, context -> subject, tone, priority
  Model: openai/gpt-4o-mini

✓ Project created successfully!
```

### Non-Interactive Mode

```bash
dspy-cli new email-subject -s "body, sender, context -> subject, tone, priority"
cd email-subject
echo "OPENAI_API_KEY=sk-..." > .env
uv sync
```

## 3. Run Locally

```bash
dspy-cli serve --ui
```

Server starts at `http://localhost:8000` with interactive UI.

## 4. Test Endpoint

```bash
curl -X POST http://localhost:8000/EmailSubjectPredict \
  -H "Content-Type: application/json" \
  -d '{"body": "Team meeting notes...", "sender": "CEO", "context": "Internal"}'
```

Or use interactive UI at `http://localhost:8000`.

## 5. Deploy

See [Deployment Guide](deployment.md) for Fly.io, Docker, AWS, GCP, and Kubernetes instructions.

## 6. Integrate

Integration examples for JavaScript, Python, and other languages: [Examples](../examples/).

## Development

- **Hot reload**: Changes to `.py` files restart server automatically
- **Switch models**: Edit `dspy.config.yaml` - see [Configuration](configuration.md)
- **Custom port**: `dspy-cli serve --port 3000`

## Next Steps

- **[Deployment Guide](deployment.md)** - Production deployment, scaling, monitoring, troubleshooting
- **[Configuration Reference](configuration.md)** - Model providers, advanced settings, optimization
- **[Command Reference](commands/index.md)** - Complete CLI documentation (`new`, `generate`, `serve`, `optimize`)
- **[Examples](../examples/)** - Working applications (blog-tools, code-review-agent, multi-module patterns)
- **[Project Structure](commands/new.md)** - Understand generated files and conventions
- **[Module Types](commands/generate.md)** - Predict, ChainOfThought, ReAct, ProgramOfThought
