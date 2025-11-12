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

```bash
dspy-cli new email-subject -s "body, sender, context -> subject, tone, priority"
cd email-subject
```

**Expected output:**
```
✓ Created project structure
✓ Generated signature: EmailSubjectSignature
✓ Scaffolded module: EmailSubjectPredict
```

Configure environment:

```bash
echo "OPENAI_API_KEY=sk-..." > .env
uv sync
```

## 3. Run Locally

```bash
dspy-cli serve --ui --reload
```

**Expected output:**
```
✓ Configuration loaded

Discovered Programs:
  • EmailSubjectPredict
    POST /EmailSubjectPredict

Server running at http://0.0.0.0:8000
Interactive UI at http://localhost:8000
```

## 4. Verify Endpoints

Test with curl:

```bash
curl -X POST http://localhost:8000/EmailSubjectPredict \
  -H "Content-Type: application/json" \
  -d '{
    "body": "Team, Q4 results are in. Revenue up 23%, NPS at 72.",
    "sender": "Sarah (CEO)",
    "context": "Company all-hands"
  }'
```

**Expected response:**
```json
{
  "subject": "Q4 Results: +23% Revenue, 72 NPS",
  "tone": "professional",
  "priority": "high"
}
```

View interactive UI at http://localhost:8000 to test without curl.

## 5. Deploy to Production

### Option A: Fly.io (Recommended)

Install Fly CLI:

```bash
curl -L https://fly.io/install.sh | sh
flyctl auth login
```

Deploy:

```bash
flyctl launch --name email-subject
flyctl secrets set OPENAI_API_KEY=sk-...
flyctl deploy
```

**Expected output:**
```
==> Monitoring deployment
✓ Instance created
✓ Health checks passing

Visit your deployment at https://email-subject.fly.dev
```

### Option B: Docker

```bash
docker build -t email-subject .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... email-subject
```

Deploy to AWS ECS, Google Cloud Run, Azure Container Instances, or Kubernetes.

## 6. Verify Production Deployment

Test deployed endpoint:

```bash
curl -X POST https://email-subject.fly.dev/EmailSubjectPredict \
  -H "Content-Type: application/json" \
  -d '{
    "body": "Team, Q4 results are in. Revenue up 23%, NPS at 72.",
    "sender": "Sarah (CEO)",
    "context": "Company all-hands"
  }'
```

Retrieve OpenAPI schema:

```bash
curl https://email-subject.fly.dev/openapi.json
```

## 7. Integrate with Applications

### JavaScript/TypeScript

```typescript
interface EmailSubjectRequest {
  body: string;
  sender: string;
  context: string;
}

interface EmailSubjectResponse {
  subject: string;
  tone: string;
  priority: string;
}

async function generateEmailSubject(
  req: EmailSubjectRequest
): Promise<EmailSubjectResponse> {
  const response = await fetch(
    'https://email-subject.fly.dev/EmailSubjectPredict',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    }
  );
  
  return await response.json();
}

// Usage
const result = await generateEmailSubject({
  body: "Team meeting notes...",
  sender: "manager@company.com",
  context: "Internal communication"
});

console.log(result.subject); // "Weekly Team Sync: Key Decisions"
```

### Python

```python
import requests

def generate_email_subject(body: str, sender: str, context: str) -> dict:
    response = requests.post(
        'https://email-subject.fly.dev/EmailSubjectPredict',
        json={
            'body': body,
            'sender': sender,
            'context': context
        }
    )
    return response.json()

# Usage
result = generate_email_subject(
    body="Team meeting notes...",
    sender="manager@company.com",
    context="Internal communication"
)

print(result['subject'])  # "Weekly Team Sync: Key Decisions"
```

### cURL

```bash
curl -X POST https://email-subject.fly.dev/EmailSubjectPredict \
  -H "Content-Type: application/json" \
  -d '{
    "body": "Team meeting notes...",
    "sender": "manager@company.com",
    "context": "Internal communication"
  }'
```

## Module Types

Select appropriate module type for your use case:

| Type | Flag | Use Case |
|------|------|----------|
| **Predict** | (default) | Classification, extraction, simple generation |
| **ChainOfThought** | `-m CoT` | Tasks requiring reasoning steps |
| **ReAct** | `-m ReAct` | Tool-using agents with external actions |
| **ProgramOfThought** | `-m PoT` | Code generation, calculations, structured logic |

Example with Chain-of-Thought:

```bash
dspy-cli new document-analyzer -m CoT -s "document, criteria -> verdict: bool, reasoning, confidence: float"
```

## Project Structure

```
email-subject/
├── src/email_subject/
│   ├── modules/         # DSPy programs (auto-discovered as endpoints)
│   ├── signatures/      # Input/output schemas
│   ├── optimizers/      # Optimization configurations
│   ├── metrics/         # Evaluation metrics
│   └── utils/           # Helper functions
├── data/                # Training/test datasets
├── logs/                # Request logs
├── tests/               # Test scaffolds
├── dspy.config.yaml     # Model configuration
├── .env                 # API keys (gitignored)
├── Dockerfile           # Container configuration
└── pyproject.toml       # Dependencies
```

## Development Workflow

### Hot Reload

```bash
dspy-cli serve --ui --reload
```

Changes to `src/email_subject/modules/*.py` reload automatically (< 1s).

### Switch Models

Edit `dspy.config.yaml` to change providers without code changes:

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
```

```yaml
# Anthropic
lm:
  provider: anthropic
  model: claude-3-sonnet-20240229
  max_tokens: 1000
  temperature: 0.7
```

Restart server to apply configuration changes.

### Custom Port

```bash
dspy-cli serve --port 3000
```

## Next Steps

- **[Deployment Guide](deployment.md)** - Production configuration, scaling, monitoring
- **[Configuration Reference](configuration.md)** - Model providers, advanced settings
- **[Command Reference](commands/index.md)** - Complete CLI documentation
- **[Examples](../examples/)** - Working applications (blog-tools, code-review-agent)

## Troubleshooting

### Module Not Found

Activate project virtual environment:

```bash
cd email-subject
uv sync
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate     # Windows
```

Add external dependencies to `pyproject.toml`:

```bash
uv add requests pandas
uv sync
```

### API Key Errors

Verify `.env` file exists:

```bash
cat .env  # Should show OPENAI_API_KEY=sk-...
```

Export to current shell:

```bash
export OPENAI_API_KEY=sk-...  # Unix/macOS
# or
set OPENAI_API_KEY=sk-...     # Windows
```

### Port In Use

Use different port:

```bash
dspy-cli serve --port 8080
```

Identify process using port 8000:

```bash
lsof -ti:8000  # Unix/macOS
netstat -ano | findstr :8000  # Windows
```

### Deployment Failures

Check Fly.io logs:

```bash
flyctl logs
```

Verify secrets configured:

```bash
flyctl secrets list  # Should show OPENAI_API_KEY
```

Validate Docker build:

```bash
docker build -t email-subject . --progress=plain
```

For additional issues, see [Deployment Troubleshooting](deployment.md#troubleshooting).
