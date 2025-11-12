# Deployment

This guide covers deployment of DSPy applications to production environments using containerization and cloud platforms.

## Overview

DSPy applications generated with `dspy-cli new` include production-ready deployment artifacts:

- **Dockerfile** - Container configuration for standardized deployment
- **REST API endpoints** - Auto-generated from DSPy modules
- **OpenAPI specification** - Type-safe integration for clients
- **Environment variable handling** - Secure secrets management

Local development servers created with `dspy-cli serve` use identical endpoints and behavior as production deployments.

## Prerequisites

- Docker (version 20.10 or later)
- Active account on target deployment platform
- API keys for configured LLM providers (OpenAI, Anthropic, etc.)
- Git repository (optional, required for some platforms)

## Deployment to Fly.io

Time to complete: ~3-5 minutes

Fly.io provides global container deployment with minimal configuration.

### 1. Install Fly CLI

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### 2. Authenticate

```bash
flyctl auth login
```

Opens browser for authentication. Free tier available without credit card for starter applications.

### 3. Initialize Application

Navigate to your project directory and run:

```bash
flyctl launch
```

**Expected output:**

```
Scanning source code
Detected a Dockerfile app
? Choose an app name (leave blank to generate one): blog-tools-prod
? Choose a region for deployment: Seattle, Washington (US) (sea)

Creating app in /Users/you/blog-tools
Organization: Personal
Name:         blog-tools-prod
Region:       Seattle, Washington (US)
App Machines: shared-cpu-1x, 1GB RAM

? Do you want to tweak these settings before proceeding? No
```

### 4. Deploy

```bash
flyctl deploy
```

**Expected output:**

```
--> Building image
[+] Building 28.7s
--> Pushing image to fly
--> Creating release
--> Monitoring deployment

Visit your app at: https://blog-tools-prod.fly.dev
```

### 5. Configure Secrets

Set environment variables for API keys:

```bash
flyctl secrets set OPENAI_API_KEY=sk-proj-...
```

**Expected output:**

```
Secrets are staged for the first deployment
Release v2 created
```

For multiple providers:

```bash
flyctl secrets set ANTHROPIC_API_KEY=sk-ant-...
```

Verify configured secrets:

```bash
flyctl secrets list
```

**Expected output:**

```
NAME                    DIGEST                          CREATED AT
OPENAI_API_KEY          a1b2c3d4e5f6...               1m ago
ANTHROPIC_API_KEY       f6e5d4c3b2a1...               30s ago
```

### 6. Verify Deployment

Test the deployed API:

```bash
curl -X POST "https://blog-tools-prod.fly.dev/SummarizerPredict" \
  -H "Content-Type: application/json" \
  -d '{
    "blog_post": "Sample article text for testing deployment.",
    "summary_length": "short",
    "tone": "casual"
  }'
```

**Expected output:**

```json
{
  "summary": "Testing deployment with a sample article."
}
```

Verify OpenAPI specification is accessible:

```bash
curl https://blog-tools-prod.fly.dev/openapi.json
```

### 7. Update Deployment

Deploy changes:

```bash
flyctl deploy
```

Zero-downtime rolling deployment. Previous version remains active until new version is healthy.

### 8. Scale Deployment (Optional)

Add instances in multiple regions:

```bash
flyctl scale count 2 --region sea,iad
```

Configure auto-scaling:

```bash
flyctl autoscale set min=1 max=10
```

## Docker Deployment (Generic)

The generated Dockerfile is compatible with any container platform: Render, Railway, Google Cloud Run, AWS App Runner, DigitalOcean App Platform, Azure Container Instances.

### 1. Build Container Locally

```bash
docker build -t blog-tools:latest .
```

**Expected output:**

```
[+] Building 45.3s
 => [1/5] FROM docker.io/library/python:3.11-slim
 => [2/5] COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
 => [3/5] COPY . .
 => [4/5] RUN uv sync --no-dev
 => [5/5] RUN uv tool install dspy-cli
 => exporting to image
Successfully tagged blog-tools:latest
```

### 2. Test Container Locally

```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-... \
  blog-tools:latest
```

**Expected output:**

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test endpoint in another terminal:

```bash
curl -X POST http://localhost:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{"blog_post": "Test content", "summary_length": "short", "tone": null}'
```

### 3. Push to Container Registry

**Docker Hub:**

```bash
docker tag blog-tools:latest your-username/blog-tools:latest
docker push your-username/blog-tools:latest
```

**AWS ECR:**

```bash
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-west-2.amazonaws.com

docker tag blog-tools:latest <account-id>.dkr.ecr.us-west-2.amazonaws.com/blog-tools:latest
docker push <account-id>.dkr.ecr.us-west-2.amazonaws.com/blog-tools:latest
```

**Google Artifact Registry:**

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev

docker tag blog-tools:latest us-central1-docker.pkg.dev/<project-id>/dspy-apps/blog-tools:latest
docker push us-central1-docker.pkg.dev/<project-id>/dspy-apps/blog-tools:latest
```

### 4. Deploy to Platform

**Render:**

1. Connect GitHub repository in Render dashboard
2. Create new Web Service
3. Render auto-detects Dockerfile
4. Configure environment variables in Environment tab
5. Deploy

**Railway:**

```bash
railway up
railway variables set OPENAI_API_KEY=sk-proj-...
```

Auto-deploys on Git push when repository is connected.

**Google Cloud Run:**

```bash
gcloud run deploy blog-tools \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=sk-proj-...
```

**Expected output:**

```
Building using Dockerfile and deploying container
✓ Deploying... Done.
Service [blog-tools] revision [blog-tools-00001] has been deployed
Service URL: https://blog-tools-xyz.a.run.app
```

**AWS App Runner:**

1. Push image to ECR (see registry instructions above)
2. Create App Runner service in AWS Console
3. Configure ECR image as source
4. Set environment variables in Configuration
5. Deploy service

**DigitalOcean App Platform:**

1. Connect GitHub repository
2. App Platform detects Dockerfile
3. Configure environment variables in Settings
4. Click Deploy

## Environment Configuration

### Development Environment

Use `.env` file for local development:

```bash
# .env - Do not commit to version control
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
```

The `dspy-cli serve` command automatically loads variables from `.env`. File is excluded via `.gitignore`.

### Production Secrets

Configure secrets using platform-specific secret managers:

| Platform | Command | Injection Method |
|----------|---------|------------------|
| **Fly.io** | `flyctl secrets set KEY=value` | Environment variables |
| **Render** | Dashboard → Environment tab | Environment variables |
| **Railway** | `railway variables set KEY=value` | Environment variables |
| **Google Cloud Run** | `--set-env-vars KEY=value` or Secret Manager | Environment variables |
| **AWS** | Systems Manager Parameter Store / Secrets Manager | ECS task definition |
| **DigitalOcean** | App Platform dashboard → Settings | Environment variables |

### Model Configuration by Environment

Configure different models for development and production using `dspy.config.yaml`:

```yaml
models:
  default: openai:gpt-4o-mini
  
  registry:
    # Production model
    openai:gpt-4o-mini:
      model: openai/gpt-4o-mini
      env: OPENAI_API_KEY
      max_tokens: 16000
      temperature: 1.0
      model_type: chat
    
    # Development model
    openai:gpt-4o-nano:
      model: openai/gpt-4o-nano
      env: OPENAI_API_KEY
      max_tokens: 8000
      temperature: 1.0
      model_type: chat
    
    # Local model
    local:qwen:
      model: openai/qwen/qwen3-4b
      api_base: http://127.0.0.1:1234/v1
      api_key: placeholder
      max_tokens: 4096
      temperature: 1.0
      model_type: chat

# Override per module
program_models:
  SummarizerPredict: openai:gpt-4o-nano
  TaggerCoT: openai:gpt-4o-mini
```

Override `default` or `program_models` before deploying, or maintain separate configuration files:

```bash
# Use production config
cp dspy.config.prod.yaml dspy.config.yaml
```

### Secrets Management Best Practices

**Required:**
- Store secrets in platform secret managers
- Use `.env` for local development only
- Add `.env` to `.gitignore`
- Rotate API keys regularly (monthly or quarterly)
- Use separate keys for development, staging, and production

**Prohibited:**
- Committing `.env` files to Git
- Hardcoding keys in source code or configuration files
- Sharing production keys in communication channels
- Using production keys in local development
- Exposing keys in client-side code

## Health Checks and Monitoring

### Health Check Endpoint

Verify service availability using the OpenAPI endpoint:

```bash
curl https://blog-tools-prod.fly.dev/openapi.json
```

Returns OpenAPI specification if service is healthy.

### Log Access

**Fly.io:**

```bash
# Stream live logs
flyctl logs

# View recent logs
flyctl logs --recent

# Access log files in container
flyctl ssh console
cd logs/
tail -f SummarizerPredict.log
```

**Render:**

View logs in dashboard under Logs tab. Export logs via Export Logs button.

**Railway:**

```bash
# View live logs
railway logs

# Follow logs in real-time
railway logs --follow
```

**Google Cloud Run:**

```bash
# View logs in Cloud Console
gcloud logging read "resource.type=cloud_run_revision"

# Stream logs
gcloud logging tail "resource.type=cloud_run_revision"
```

**AWS App Runner:**

View logs in CloudWatch Logs console. Use CloudWatch Insights for structured queries.

### Log Format

Structured JSON logs capture request details:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "program": "SummarizerPredict",
  "model": "openai/gpt-4o-mini",
  "duration_ms": 847.23,
  "inputs": {
    "blog_post": "Article text...",
    "summary_length": "short",
    "tone": null
  },
  "outputs": {
    "summary": "Generated summary."
  },
  "success": true
}
```

### Platform-Specific Health Checks

Configure health checks in platform configuration files:

**Fly.io (fly.toml):**

```toml
[http_service]
  internal_port = 8000
  force_https = true
  auto_start_machines = true
  auto_stop_machines = true
  min_machines_running = 0
  
  [[http_service.checks]]
    grace_period = "10s"
    interval = "30s"
    timeout = "5s"
    method = "GET"
    path = "/openapi.json"
```

**Google Cloud Run:**

```bash
gcloud run deploy blog-tools \
  --timeout=300 \
  --max-instances=10 \
  --cpu=1 \
  --memory=512Mi
```

## Troubleshooting

### Build Errors

**Error: `uv: command not found`**

Update Dockerfile to include `uv` binary:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```

Or regenerate project files:

```bash
dspy-cli new --force
```

**Error: `No module named 'dspy'`**

Verify `pyproject.toml` includes DSPy dependency:

```toml
[project]
dependencies = [
    "dspy>=2.5.0",
]
```

Rebuild container:

```bash
docker build -t blog-tools .
```

**Error: `failed to solve with frontend dockerfile.v0`**

Update Docker to version 20.10 or later.

### Runtime Errors

**Error: `OPENAI_API_KEY not set`**

Configure environment variable on deployment platform:

```bash
# Fly.io
flyctl secrets set OPENAI_API_KEY=sk-proj-...

# Railway
railway variables set OPENAI_API_KEY=sk-proj-...

# Google Cloud Run
gcloud run services update blog-tools --set-env-vars OPENAI_API_KEY=sk-proj-...
```

Verify secret is loaded:

```bash
flyctl ssh console
echo $OPENAI_API_KEY
```

**Error: `Module not found: SummarizerPredict`**

Verify module exists with correct class name:

```bash
ls src/blog_tools/modules/
cat src/blog_tools/modules/summarizer_predict.py | grep "class"
```

Expected: `class SummarizerPredict(dspy.Module):`

**Error: `500 Internal Server Error`**

Check container logs:

```bash
flyctl logs --recent  # Fly.io
railway logs          # Railway
```

Common causes:
- Missing environment variables
- Model API rate limits exceeded
- Invalid signature definition
- Import errors in module code

### Performance Issues

**Slow cold starts (10-20 seconds)**

Platforms may shut down idle containers. Solutions:

- **Fly.io:** Upgrade to dedicated VM tier: `flyctl scale vm dedicated-cpu-1x`
- **Render:** Enable "Always On" in paid tiers
- **Railway:** Paid plans keep services active
- **Pre-warm with cron:** Configure external service (e.g., cron-job.org) to ping `/openapi.json` every 5 minutes

**High latency**

Deploy in regions closer to users:

```bash
# Fly.io: Add regions
flyctl regions add sea iad lhr
flyctl scale count 3

# Google Cloud Run: Deploy to multiple regions
gcloud run deploy blog-tools --region us-central1
gcloud run deploy blog-tools --region europe-west1
gcloud run deploy blog-tools --region asia-northeast1
```

**Timeout errors (504 Gateway Timeout)**

Increase platform timeout limits:

```bash
# Google Cloud Run (maximum 300 seconds)
gcloud run deploy blog-tools --timeout=300

# Fly.io: Edit fly.toml http_service.checks.timeout
```

### Debugging Workflow

1. **Test locally with Docker:**

```bash
docker build -t blog-tools .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-proj-... blog-tools
curl -X POST http://localhost:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{"blog_post": "test", "summary_length": "short", "tone": null}'
```

2. **Verify OpenAPI specification:**

```bash
curl https://blog-tools-prod.fly.dev/openapi.json
```

3. **Check application logs:**

```bash
flyctl logs --recent
```

4. **Verify environment variables:**

```bash
flyctl ssh console
env | grep API_KEY
```

## Related Documentation

- [Configuration](configuration.md) - Model configuration and advanced settings
- [MCP Integration](OPENAPI.md) - Model Context Protocol tool server
- [Getting Started](getting-started.md#continuous-optimization) - Production data optimization
- [Use Cases: AI Features](use-cases/ai-features.md) - Integration patterns

## Platform Documentation

- [Fly.io Documentation](https://fly.io/docs/)
- [Render Documentation](https://render.com/docs)
- [Railway Documentation](https://docs.railway.app/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
