# Deployment

Deploy DSPy applications to production using containerization and cloud platforms.

## Overview

Applications include production-ready artifacts:

- **Dockerfile** - Container configuration for standardized deployment
- **REST API endpoints** - Auto-generated from DSPy modules  
- **OpenAPI specification** - Type-safe integration for clients
- **Environment variable handling** - Secure secrets management

## Prerequisites

- Docker 20.10+
- Account on target deployment platform
- API keys for LLM providers (OpenAI, Anthropic, etc.)

## Deployment to Fly.io

Time: ~3-5 minutes

```bash
# Install and authenticate
brew install flyctl
flyctl auth login

# Launch and configure
flyctl launch
flyctl secrets set OPENAI_API_KEY=sk-proj-... DSPY_API_KEY=your-api-key
flyctl deploy
```

App available at `https://your-app.fly.dev`

Verify:

```bash
curl -X POST "https://your-app.fly.dev/SummarizerPredict" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{"blog_post": "Test"}'
```

## Docker Deployment

Compatible with any platform that can serve arbitrary dockerfiles.

### Build and Test

```bash
docker build -t my-app:latest .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e DSPY_API_KEY=your-api-key \
  my-app:latest
```

> The generated Dockerfile runs `dspy-cli serve --auth` by default, so `DSPY_API_KEY` is required.

### Push to Registry

**Docker Hub:**

```bash
docker tag my-app:latest username/my-app:latest
docker push username/my-app:latest
```

**AWS ECR:**

```bash
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-west-2.amazonaws.com
docker tag my-app:latest <account>.dkr.ecr.us-west-2.amazonaws.com/my-app:latest
docker push <account>.dkr.ecr.us-west-2.amazonaws.com/my-app:latest
```

**Google Artifact Registry:**

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
docker tag my-app:latest us-central1-docker.pkg.dev/<project>/dspy/my-app:latest
docker push us-central1-docker.pkg.dev/<project>/dspy/my-app:latest
```

### Deploy to Platform

**Render:** Connect GitHub repository, create Web Service, Render auto-detects Dockerfile, configure environment variables, deploy.

**Google Cloud Run:**

```bash
gcloud run deploy my-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=sk-proj-...,DSPY_API_KEY=your-api-key
```

## Environment Variables

See [Configuration Reference](configuration.md) for detailed environment configuration.

### Development

Use `.env` file (auto-loaded by `dspy-cli serve`, excluded via `.gitignore`):

```bash
# .env - Do not commit
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
DSPY_API_KEY=your-api-key  # Optional: required when running with --auth
```

### Production Secrets

Configure via platform secret managers:

| Platform | Command |
|----------|---------|
| **Fly.io** | `flyctl secrets set KEY=value` |
| **Google Cloud Run** | `--set-env-vars KEY=value` or Secret Manager |
| **AWS** | Systems Manager Parameter Store / Secrets Manager |

When you first create a project, if you do not have a `DSPY_API_KEY`, one will be generated and you can see it in the logs.

It is recommended to change this key immediately after deployment to a secure value via your secret manager.

### Secrets Best Practices

**Required:**

- Store secrets in platform secret managers
- Use `.env` for local development only
- Rotate API keys regularly
- Use separate keys per environment

**Prohibited:**

- Committing `.env` to Git
- Hardcoding keys in source code
- Sharing production keys
- Using production keys in development

## Health Checks

Verify service availability:

```bash
curl https://my-app.fly.dev/health
```

When authentication is enabled, use `/health` (always open) or include `Authorization: Bearer <DSPY_API_KEY>` for other endpoints.

## Logs

**Fly.io:**

```bash
flyctl logs                # Stream logs
flyctl logs --recent       # Recent logs
```

**Google Cloud Run:**

```bash
gcloud logging read "resource.type=cloud_run_revision"
gcloud logging tail "resource.type=cloud_run_revision"
```

**Render:** Dashboard → Logs tab

**AWS App Runner:** CloudWatch Logs console

Structured JSON log format:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "program": "SummarizerPredict",
  "model": "openai/gpt-4o-mini",
  "duration_ms": 847.23,
  "inputs": {...},
  "outputs": {...},
  "success": true
}
```

## Troubleshooting

### Build Errors

**Error: `uv: command not found`**

Update Dockerfile:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```

Or regenerate: `dspy-cli new --force`

**Error: `No module named 'dspy'`**

Verify `pyproject.toml` includes `dspy`, rebuild container.

**Error: `failed to solve with frontend dockerfile.v0`**

Update Docker to 20.10+.

### Runtime Errors

**Error: `OPENAI_API_KEY not set`**

Configure environment variable:

```bash
flyctl secrets set OPENAI_API_KEY=sk-proj-...           # Fly.io
gcloud run services update my-app --set-env-vars OPENAI_API_KEY=sk-...  # Cloud Run
```

**Error: `Module not found: SummarizerPredict`**

Verify module exists with correct class name in `src/<package>/modules/`.

This can also happen when an external dependency is not added to the `pyproject.toml` file.

**Error: `500 Internal Server Error`**

Check logs for:

- Missing environment variables
- Model API rate limits
- Invalid signature definition
- Import errors

### Performance

**Slow cold starts:** Upgrade to dedicated tier, enable "Always On", or pre-warm with cron (ping `/openapi.json` every 5 minutes).

**High latency:** Deploy in multiple regions:
```bash
# Fly.io
flyctl regions add sea iad lhr
flyctl scale count 3
```

**Timeout errors:** Increase platform timeout limits (`--timeout=300` for Cloud Run).

### Debugging

1. Test locally: `docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... my-app`
2. Verify OpenAPI: `curl https://my-app.fly.dev/openapi.json`
3. Check logs: `flyctl logs --recent`
4. Verify env vars: `flyctl ssh console` → `env | grep API_KEY`

## Frontend Integration (CORS)

When your frontend runs on a different origin than the API (e.g., `app.example.com` calling `api.example.com`), configure CORS:

**Environment variable:**

```bash
# Allow all origins (development)
DSPY_CORS_ORIGINS="*" dspy-cli serve

# Allow specific origins (production)
DSPY_CORS_ORIGINS="https://app.example.com,https://admin.example.com" dspy-cli serve
```

**Config file (`dspy.config.yaml`):**

```yaml
server:
  cors_origins:
    - "https://app.example.com"
    - "https://admin.example.com"
```

> **Note**: Wildcard (`*`) disables credential support. For cookie-based auth across origins, specify explicit origins. API clients using Bearer tokens work with any CORS mode.

## Related Documentation

- [Configuration](configuration.md) - Model configuration and advanced settings
- [OpenAPI Generation](OPENAPI.md) - OpenAPI spec and MCP integration
- [Getting Started](getting-started.md) - Production data optimization
- [Use Cases: AI Features](use-cases/ai-features.md) - Integration patterns

## Platform Documentation

- [Fly.io](https://fly.io/docs/)
- [Google Cloud Run](https://cloud.google.com/run/docs)
- [AWS App Runner](https://docs.aws.amazon.com/apprunner/)
