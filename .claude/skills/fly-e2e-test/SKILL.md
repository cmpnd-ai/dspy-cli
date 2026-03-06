---
name: fly-e2e-test
description: Deploy and test dspy-cli on Fly.io using local changes via temp git branch. Full integration testing with guaranteed cleanup. (project)
allowed-tools:
  - Bash
---

# Fly.io E2E Integration Test Skill

Deploy a fresh dspy-cli project to Fly.io using your local code changes, run full integration tests (health, auth, LLM execution), and **guarantee cleanup** regardless of success or failure.

## CRITICAL RULES

1. **NEVER commit directly to main** - Always create a side branch first, even for small changes
2. **ALWAYS clean up** - Destroy Fly apps and delete temp branches, even if tests fail
3. **Use temp branches** - Name them `e2e-test/{timestamp}-{random}` for easy identification
4. **Run cleanup in a trap** - Use bash trap or always-run-cleanup pattern

## Prerequisites

1. **fly CLI**: Installed and authenticated (`fly auth whoami`)
2. **OPENAI_API_KEY**: In environment or `.env` file
3. **Git**: Clean working directory (stash uncommitted changes first)
4. **Git push access**: Ability to push to origin

## Quick Start

All commands run directly in the shell (no tmux required). Use environment variables to pass state between steps.

### Phase 1: Setup Environment

```bash
export DSPY_CLI_DIR="/Users/isaac/projects/dspy-cli"
export TIMESTAMP=$(date +%s)
export RANDOM_SUFFIX=$(head -c 4 /dev/urandom | xxd -p)
export FLY_APP_NAME="dspy-e2e-${RANDOM_SUFFIX}"
export TEMP_BRANCH="e2e-test/${TIMESTAMP}-${RANDOM_SUFFIX}"
export DSPY_API_KEY_VALUE="test-e2e-$(head -c 8 /dev/urandom | xxd -p)"

# Source .env for OPENAI_API_KEY
set -a && source "$DSPY_CLI_DIR/.env" && set +a

# Verify setup
echo "App: $FLY_APP_NAME Branch: $TEMP_BRANCH"
```

### Phase 2: Pre-flight Checks

```bash
fly version && fly auth whoami
git -C "$DSPY_CLI_DIR" status --porcelain

# Clean up any orphaned e2e resources
fly apps list 2>/dev/null | grep "dspy-e2e" || echo "No orphaned apps"
```

### Phase 3: Create and Push Temp Branch

```bash
git -C "$DSPY_CLI_DIR" checkout -b "$TEMP_BRANCH"
git -C "$DSPY_CLI_DIR" push -u origin "$TEMP_BRANCH"
```

### Phase 4: Create Test Project

```bash
export TEST_DIR=$(mktemp -d) && echo "TEST_DIR=$TEST_DIR"

# Pipe "Y" to accept the API key confirmation prompt
echo "Y" | uv run --directory "$DSPY_CLI_DIR" dspy-cli new fly-e2e-test \
  --program-name qa_module \
  --signature "question:str -> answer:str" \
  --module-type Predict \
  --model openai/gpt-4o-mini

# Move project to temp dir (dspy-cli new creates in current dir)
mv "$DSPY_CLI_DIR/fly-e2e-test" "$TEST_DIR/"
cd "$TEST_DIR/fly-e2e-test"
```

### Phase 5: Modify for Git-Based dspy-cli

```bash
cd "$TEST_DIR/fly-e2e-test"

# Update pyproject.toml to install dspy-cli from temp branch (use double quotes for variable expansion)
sed -i.bak "s|\"dspy-cli\"|\"dspy-cli @ git+https://github.com/cmpnd-ai/dspy-cli.git@$TEMP_BRANCH\"|" pyproject.toml

# Update Dockerfile: add git (required for git-based deps)
# NOTE: Check the current Dockerfile.template for the latest CMD format and update accordingly
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV XDG_CACHE_HOME=/tmp/.cache

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY . .
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "dspy-cli", "serve", "--host", "0.0.0.0", "--port", "8000", "--auth", "--no-reload"]
EOF
```

### Phase 6: Create fly.toml and Deploy

```bash
cd "$TEST_DIR/fly-e2e-test"

cat > fly.toml << EOF
app = '$FLY_APP_NAME'
primary_region = 'ewr'

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ['app']

[deploy]
  ha = false

[checks]
  [checks.health]
    port = 8000
    type = "http"
    interval = "10s"
    timeout = "5s"
    grace_period = "30s"
    method = "GET"
    path = "/health/live"

[[vm]]
  memory = '512mb'
  cpu_kind = 'shared'
  cpus = 1
EOF

# Create app and set secrets
fly apps create "$FLY_APP_NAME" --org personal
fly secrets set OPENAI_API_KEY="$OPENAI_API_KEY" DSPY_API_KEY="$DSPY_API_KEY_VALUE" --app "$FLY_APP_NAME"

# Deploy (takes ~2-3 minutes)
fly deploy --app "$FLY_APP_NAME" --wait-timeout 300
```

### Phase 7: Run Integration Tests

```bash
export FLY_APP_URL="https://$FLY_APP_NAME.fly.dev"

# Wait for app to be ready (poll /health/ready)
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FLY_APP_URL/health/ready")
  if [ "$STATUS" = "200" ]; then echo "App ready after ${i}s"; break; fi
  sleep 1
done

# Test 1: Health endpoints (no auth required)
echo "=== Test 1: Liveness ===" && curl -s "$FLY_APP_URL/health/live"
echo "=== Test 2: Readiness ===" && curl -s "$FLY_APP_URL/health/ready"
echo "=== Test 3: Legacy health ===" && curl -s "$FLY_APP_URL/health"

# Test 4: Auth redirect (unauthenticated)
echo "=== Test 4: Auth Redirect ===" && curl -s -o /dev/null -w "HTTP: %{http_code}\n" "$FLY_APP_URL/programs"

# Test 5: Auth success (authenticated)
echo "=== Test 5: Auth Success ===" && curl -s -H "Authorization: Bearer $DSPY_API_KEY_VALUE" "$FLY_APP_URL/programs"

# Test 6: LLM Module Execution
echo "=== Test 6: LLM Execution ===" && curl -s -X POST \
  -H "Authorization: Bearer $DSPY_API_KEY_VALUE" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is 2+2? Reply with just the number."}' \
  "$FLY_APP_URL/QaModulePredict"
```

### Phase 8: SSH Inspection (optional)

With `ha = false`, there's only one machine so SSH always targets it.
Shell redirects like `2>/dev/null` don't work in `-C` commands -- wrap in `sh -c`:

```bash
# Inspect the machine filesystem
fly ssh console --app "$FLY_APP_NAME" -C "sh -c 'find /root -name \"*.log\" 2>/dev/null'"

# Check inference logs
fly ssh console --app "$FLY_APP_NAME" -C "cat /logs/QaModulePredict.log"
```

### Phase 9: Guaranteed Cleanup

**ALWAYS run cleanup, even if tests fail:**

```bash
# Destroy Fly app
fly apps destroy "$FLY_APP_NAME" --yes

# Delete remote branch
git -C "$DSPY_CLI_DIR" push origin --delete "$TEMP_BRANCH"

# Return to main and delete local branch
git -C "$DSPY_CLI_DIR" checkout main
git -C "$DSPY_CLI_DIR" branch -D "$TEMP_BRANCH"

# Remove temp directory
rm -rf "$TEST_DIR"
```

## Verification Checklist

| Test | Expected Result |
|------|-----------------|
| `/health/live` (no auth) | `{"status":"alive"}` |
| `/health/ready` (no auth) | `{"status":"ready","programs":1}` |
| `/health` (no auth) | `{"status":"ok"}` |
| Auth Redirect (no auth) | HTTP 303 |
| Auth Success (Bearer token) | JSON with `QaModulePredict` |
| LLM Execution | JSON with `"answer"` field |

## Cleanup Verification

```bash
fly apps list | grep "dspy-e2e" || echo "No orphaned apps"
git branch -r | grep "e2e-test/" || echo "No orphaned branches"
```

## Troubleshooting

### Deploy fails with "Git executable not found"
The Dockerfile must include git installation:
```dockerfile
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
```

### pyproject.toml sed command doesn't expand variables
Use double quotes for the sed command, not single quotes:
```bash
sed -i.bak "s|...|...@$TEMP_BRANCH\"|" pyproject.toml  # Correct
sed -i.bak 's|...|...|' pyproject.toml  # Won't expand $TEMP_BRANCH
```

### Project created in wrong directory
`dspy-cli new` creates projects relative to the current working directory. Move the project after creation:
```bash
mv "$DSPY_CLI_DIR/fly-e2e-test" "$TEST_DIR/"
```

### Shell redirects fail in fly ssh -C
Wrap the remote command in `sh -c`:
```bash
fly ssh console --app "$FLY_APP_NAME" -C "sh -c 'find / -name \"*dspy*\" 2>/dev/null'"
```

### Cleanup fails
Run each step individually:
```bash
fly apps destroy "dspy-e2e-XXXX" --yes
git push origin --delete "e2e-test/XXXX"
git checkout main
git branch -D "e2e-test/XXXX"
```

### App crashes due to missing environment variables
```bash
fly logs --app "$FLY_APP_NAME" --no-tail
fly secrets set VAR_NAME="value" --app "$FLY_APP_NAME"
fly secrets list --app "$FLY_APP_NAME"
```

Common env vars:
- `OPENAI_API_KEY` - Required for OpenAI models
- `DSPY_API_KEY` - Required when `--auth` is enabled

### Per-machine cache fragmentation (multi-machine deployments)
The `ha = false` setting in fly.toml keeps E2E tests on a single machine,
avoiding this issue. For production deployments with multiple machines, the
LM response cache (`.dspy_cache`) is local to each VM, so requests hitting
different machines may miss the cache.
