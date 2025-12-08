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

```text
What is your project name? [my-project]: email-subject
Would you like to specify your first program? [Y/n]: Y
What is the name of your first DSPy program? [my_program]: email_subject
Choose a module type:
  1. Predict - Basic prediction module (default)
  2. ChainOfThought (CoT) - Step-by-step reasoning with chain of thought
  3. ProgramOfThought (PoT) - Generates and executes code for reasoning
  4. ReAct - Reasoning and acting with tools
  5. MultiChainComparison - Compare multiple reasoning paths
  6. Refine - Iterative refinement of outputs
Enter number or name [1]: 1
Enter your signature or type '?' for guided input:
  Examples: 'question -> answer', 'post:str -> tags:list[str], category:str'
Signature [question:str -> answer:str]: body, sender, context -> subject, tone, priority
Enter your model (LiteLLM format):
  Examples: 'anthropic/claude-sonnet-4-5', 'openai/gpt-4o', 'ollama/llama2'
Model [openai/gpt-5-mini]: openai/gpt-5-mini
Enter your OpenAI API key:
  (This will be stored in .env as OPENAI_API_KEY)
  Press Enter to skip and set it manually later
OPENAI_API_KEY: your_key_here
```

## 3. Run Locally

```bash
dspy-cli serve
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

See [Deployment Guide](deployment.md) for Fly.io, Docker, AWS, GCP, and more. Production Docker deployments enable authentication by default; set `DSPY_API_KEY` in your environment and use `Authorization: Bearer <key>` when calling your API.

## Development

- **Hot reload**: Changes to `.py` files restart server automatically
- **Switch models**: Edit `dspy.config.yaml` - see [Configuration](configuration.md)
- **Custom port**: `dspy-cli serve --port 3000`

## Next Steps

- **[Deployment Guide](deployment.md)** - Production deployment, scaling, monitoring, troubleshooting
- **[Configuration Reference](configuration.md)** - Model providers, advanced settings, optimization
- **[Command Reference](commands/index.md)** - Complete CLI documentation (`new`, `generate`, `serve`)
- **[Examples](https://github.com/cmpnd-ai/dspy-cli/tree/main/examples)** - Working applications (blog-tools, code-review-agent, multi-module patterns)
- **[Project Structure](commands/new.md)** - Understand generated files and conventions
- **[Module Types](commands/generate.md)** - Predict, ChainOfThought, ReAct, ProgramOfThought
