# dspy-cli

## Tired of Prompts Breaking When You Switch Models?

You tweak your prompt until it works perfectly with GPT-4. Then you try Claude or Llama and everything breaks. You're stuck manually tuning prompts, chasing edge cases, and praying nothing breaks in production.

**There's a better way.**

> **Prompt. Test. Ship.**

DSPy optimizes your AI systems automatically—no manual prompt engineering. **dspy-cli gets you started in minutes.**

## From Frustration to Flow

**Before:**
```python
# Brittle prompt strings
prompt = "You are a helpful assistant. Given this text..."
# Manual tweaking for every model
# Breaks when you change providers
# No systematic testing
```

**After:**
```python
# Declarative, optimizable signatures
class QASignature(dspy.Signature):
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()
qa = dspy.Predict(QASignature)
```

**The difference:** Your system adapts automatically. Switch models, run an optimizer, ship with confidence.

## Quick Start

Go from idea to live API in three commands:

```bash
dspy-cli new chatbot        # Full project structure
cd chatbot && uv sync       # Install dependencies  
dspy-cli serve              # Live REST API
```

Your LLM app is running at `http://localhost:8000` with interactive docs at `/docs`.

## Installation

```bash
pipx install dspy-cli
# or: uv tool install dspy-cli
```

## What You Get

### 1. Stop Fighting Boilerplate

```bash
dspy-cli new my-app
```

```
Creating new DSPy project: my-app
  ✓ Project structure
  ✓ Type-safe signatures
  ✓ Test templates
  ✓ Config files
  ✓ Git repository
```

**No more:** "Where does this file go?" or "Where do I put my modules?" or "What configuration do I need?"

### 2. Ship Faster

```bash
dspy-cli serve
```

```
Server starting on http://0.0.0.0:8000

Discovered Programs:
  • MyAppPredict - POST /MyAppPredict

✓ Ready at http://localhost:8000/docs
```

**No more:** Building REST APIs from scratch. Auto-discovery turns your modules into endpoints.

### 3. Iterate Without Friction

Built-in web UI for testing. Edit a module, restart the server, test immediately.

```bash
dspy-cli serve --ui
```

**No more:** Building custom testing interfaces.

## Real-World Examples

See how developers use dspy-cli to solve actual problems:

### Content Pipeline
**Pain:** Manual content generation is slow. Generating headlines, summaries, and tags should be programs that are simple and easy to read.

**Solution:** [blog-tools](../examples/blog-tools/) - Automated headline generator, summarizer, tagger, and tweet extractor. One system, optimized together.

### Code Review Agent
**Pain:** Code review is tedious. You want AI help but building a reliable system takes weeks.

**Solution:** [code-review-agent](../examples/code-review-agent/) - Automated analysis and review, built in days instead of weeks. Uses the GitHub API as a tool.

## Core Workflow

### Create Your Project

```bash
dspy-cli new qa-bot -s "question -> answer"
```

Scaffolds modules, signatures, tests, config—everything you need to start coding.

### Add Your API Key

```bash
cd qa-bot
echo "OPENAI_API_KEY=sk-..." > .env
uv sync
```

### Build Your Logic

Edit `src/qa_bot/modules/qa_bot_predict.py`:

```python
class QaBotPredict(dspy.Module):
    def __init__(self):
        self.prog = dspy.Predict(QaBotSignature)
    
    def forward(self, question: str):
        return self.prog(question=question)
```

### Test Locally

```bash
dspy-cli serve
```

```bash
curl -X POST http://localhost:8000/QaBotPredict \
  -H "Content-Type: application/json" \
  -d '{"question": "What is DSPy?"}'
```

Or open `http://localhost:8000/docs` for interactive testing.

### Add More Programs

```bash
dspy-cli g scaffold summarizer -m CoT -s "text -> summary"
```

Creates signature and module. Instantly available at `/SummarizerCoT` endpoint.

## Why dspy-cli?

### Speed to Production

- **Scaffold in seconds** - From zero to working project instantly
- **Auto-discovery** - Drop in a module, get a REST endpoint
- **Interactive testing** - Built-in web UI for rapid iteration
- **Docker ready** - Production deployment included

### Built for Reliability

- **Type-safe signatures** - Catch errors before runtime
- **Testing built-in** - Test templates for every module
- **Config management** - Environment-based settings with `.env` support

### Focus on What Matters

**Stop spending time on:**
- Project structure
- Boilerplate code
- Server setup
- Deployment config

**Start spending time on:**
- Your AI logic
- Understanding the user problem
- Training data
- Shipping features

## Next Steps

- [Getting Started Guide](getting-started.md) - Detailed walkthrough
- [Commands Reference](commands/) - All commands and options
- [Configuration](configuration.md) - Model settings and customization

```bash
dspy-cli --help     # See all commands
```

---

**Stop tweaking. Start building.** Transform your DSPy ideas into production APIs today.
