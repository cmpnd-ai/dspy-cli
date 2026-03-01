---
name: fly-e2e-test
description: Deploy and test dspy-cli on Fly.io using local changes via temp git branch. Full integration testing with guaranteed cleanup. (project)
allowed-tools:
  - Bash
---

# Fly.io E2E Integration Test Skill

Deploy a fresh dspy-cli project to Fly.io using your local code changes, run full integration tests (health, auth, LLM execution), and **guarantee cleanup** regardless of success or failure.

## ⚠️ CRITICAL RULES

1. **NEVER commit directly to main** - Always create a side branch first, even for small changes
2. **ALWAYS clean up** - Destroy Fly apps and delete temp branches, even if tests fail
3. **Use temp branches** - Name them `e2e-test/{timestamp}-{random}` for easy identification

## Prerequisites

1. **fly CLI**: Installed and authenticated (`fly auth whoami`)
2. **OPENAI_API_KEY**: In environment or `.env` file
3. **Git**: Clean working directory (stash uncommitted changes first)
4. **Git push access**: Ability to push to origin

## Quick Start

Run each phase in a tmux session to enable output capture and cleanup tracking.

### Phase 1: Setup Environment

```bash
# Create tmux session
tmux new-session -d -s e2e-fly -c /Users/isaac/projects/dspy-cli

# Set variables
tmux send-keys -t e2e-fly 'export DSPY_CLI_DIR="/Users/isaac/projects/dspy-cli"' C-m
tmux send-keys -t e2e-fly 'export TIMESTAMP=$(date +%s)' C-m
tmux send-keys -t e2e-fly 'export RANDOM_SUFFIX=$(head -c 4 /dev/urandom | xxd -p)' C-m
tmux send-keys -t e2e-fly 'export FLY_APP_NAME="dspy-e2e-${RANDOM_SUFFIX}"' C-m
tmux send-keys -t e2e-fly 'export TEMP_BRANCH="e2e-test/${TIMESTAMP}-${RANDOM_SUFFIX}"' C-m

# Source .env for OPENAI_API_KEY
tmux send-keys -t e2e-fly 'set -a && source .env && set +a' C-m

# Verify setup
tmux send-keys -t e2e-fly 'echo "App: $FLY_APP_NAME Branch: $TEMP_BRANCH"' C-m
```

### Phase 2: Pre-flight Checks

```bash
# Verify fly CLI
tmux send-keys -t e2e-fly 'fly version && fly auth whoami' C-m

# Check for uncommitted changes (stash if needed)
tmux send-keys -t e2e-fly 'git status --porcelain' C-m

# Clean up any orphaned e2e resources
tmux send-keys -t e2e-fly 'fly apps list 2>/dev/null | grep "dspy-e2e" || echo "No orphaned apps"' C-m
```

### Phase 3: Create and Push Temp Branch

```bash
tmux send-keys -t e2e-fly 'git checkout -b "$TEMP_BRANCH"' C-m
tmux send-keys -t e2e-fly 'git push -u origin "$TEMP_BRANCH"' C-m
```

### Phase 4: Create Test Project

```bash
# Create temp directory
tmux send-keys -t e2e-fly 'export TEST_DIR=$(mktemp -d) && echo "TEST_DIR=$TEST_DIR"' C-m

# Create project (will prompt for API key confirmation - send Y)
tmux send-keys -t e2e-fly 'uv run --directory "$DSPY_CLI_DIR" dspy-cli new fly-e2e-test --program-name qa_module --signature "question:str -> answer:str" --module-type Predict --model openai/gpt-4o-mini' C-m

# When prompted "Proceed with this API key? [Y/n]:", send:
tmux send-keys -t e2e-fly 'Y' C-m

# Move project to temp dir (dspy-cli creates in current dir)
tmux send-keys -t e2e-fly 'mv "$DSPY_CLI_DIR/fly-e2e-test" "$TEST_DIR/" && cd "$TEST_DIR/fly-e2e-test"' C-m
```

### Phase 5: Modify for Git-Based dspy-cli

```bash
# Update pyproject.toml to install dspy-cli from temp branch
tmux send-keys -t e2e-fly 'sed -i.bak "s|\"dspy-cli\"|\"dspy-cli @ git+https://github.com/cmpnd-ai/dspy-cli.git@$TEMP_BRANCH\"|" pyproject.toml' C-m

# IMPORTANT: Update Dockerfile to include git (required for git-based deps)
# NOTE: This is an example dockerfile. There may be specific changes in a newer version of dspy-cli. Check the current Dockerfile and add the Git install line
tmux send-keys -t e2e-fly 'cat > Dockerfile << '"'"'EOF'"'"'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV XDG_CACHE_HOME=/tmp/.cache

# Install git for fetching dspy-cli from git URL
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY . .
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "dspy-cli", "serve", "--host", "0.0.0.0", "--port", "8000", "--auth", "--no-reload"]
EOF' C-m
```

### Phase 6: Create fly.toml and Deploy

```bash
# Create fly.toml
tmux send-keys -t e2e-fly 'cat > fly.toml << EOF
app = '"'"'$FLY_APP_NAME'"'"'
primary_region = '"'"'ewr'"'"'

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ['"'"'app'"'"']

[[vm]]
  memory = '"'"'512mb'"'"'
  cpu_kind = '"'"'shared'"'"'
  cpus = 1
EOF' C-m

# Create app
tmux send-keys -t e2e-fly 'fly apps create "$FLY_APP_NAME" --org personal' C-m

# Generate a random API key for testing
tmux send-keys -t e2e-fly 'export DSPY_API_KEY_VALUE="test-e2e-$(head -c 8 /dev/urandom | xxd -p)"' C-m

# Set secrets using fly secrets (required env vars for your app)
# Add any additional env vars your project needs here
tmux send-keys -t e2e-fly 'fly secrets set OPENAI_API_KEY="$OPENAI_API_KEY" DSPY_API_KEY="$DSPY_API_KEY_VALUE" --app "$FLY_APP_NAME"' C-m

# Deploy (takes ~2-3 minutes)
tmux send-keys -t e2e-fly 'fly deploy --app "$FLY_APP_NAME" --wait-timeout 300' C-m
```

### Phase 7: Run Integration Tests

```bash
tmux send-keys -t e2e-fly 'export FLY_APP_URL="https://$FLY_APP_NAME.fly.dev"' C-m

# Test 1: Health Check
tmux send-keys -t e2e-fly 'echo "=== Test 1: Health Check ===" && curl -s "$FLY_APP_URL/health"' C-m
# Expected: {"status":"ok"}

# Test 2: Auth Redirect (unauthenticated)
tmux send-keys -t e2e-fly 'echo "=== Test 2: Auth Redirect ===" && curl -s -o /dev/null -w "HTTP: %{http_code}\n" "$FLY_APP_URL/programs"' C-m
# Expected: HTTP: 303

# Test 3: Auth Success (authenticated)
tmux send-keys -t e2e-fly 'echo "=== Test 3: Auth Success ===" && curl -s -H "Authorization: Bearer $DSPY_API_KEY_VALUE" "$FLY_APP_URL/programs"' C-m
# Expected: {"programs":[{"name":"QaModulePredict",...}]}

# Test 4: LLM Module Execution
tmux send-keys -t e2e-fly 'echo "=== Test 4: LLM Execution ===" && curl -s -X POST -H "Authorization: Bearer $DSPY_API_KEY_VALUE" -H "Content-Type: application/json" -d '"'"'{"question": "What is 2+2?"}'"'"' "$FLY_APP_URL/QaModulePredict"' C-m
# Expected: {"answer":"4"} (or similar)
```

### Phase 8: Guaranteed Cleanup

**ALWAYS run cleanup, even if tests fail:**

```bash
# Destroy Fly app
tmux send-keys -t e2e-fly 'fly apps destroy "$FLY_APP_NAME" --yes' C-m

# Delete remote branch
tmux send-keys -t e2e-fly 'git -C "$DSPY_CLI_DIR" push origin --delete "$TEMP_BRANCH"' C-m

# Return to main and delete local branch
tmux send-keys -t e2e-fly 'git -C "$DSPY_CLI_DIR" checkout main' C-m
tmux send-keys -t e2e-fly 'git -C "$DSPY_CLI_DIR" branch -D "$TEMP_BRANCH"' C-m

# Remove temp directory
tmux send-keys -t e2e-fly 'rm -rf "$TEST_DIR"' C-m

# Kill tmux session
tmux kill-session -t e2e-fly
```

## Verification Checklist

| Test | Expected Result |
|------|-----------------|
| Health Check | `{"status":"ok"}` |
| Auth Redirect (no auth) | HTTP 303 |
| Auth Success (Bearer token) | JSON with `QaModulePredict` |
| LLM Execution | JSON with `"answer"` field |

## Cleanup Verification

After running cleanup, verify:

```bash
# No orphaned Fly apps
fly apps list | grep "dspy-e2e" || echo "Clean"

# No orphaned branches
git branch -r | grep "e2e-test/" || echo "Clean"
```

## Troubleshooting

### Deploy fails with "Git executable not found"
The Dockerfile must include git installation. Ensure the Dockerfile has:
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
`dspy-cli new` creates projects relative to the current working directory, not where it's run from. Move the project after creation:
```bash
mv "$DSPY_CLI_DIR/fly-e2e-test" "$TEST_DIR/"
```

### Cleanup fails
If any cleanup step fails, run them individually:
```bash
fly apps destroy "dspy-e2e-XXXX" --yes
git push origin --delete "e2e-test/XXXX"
git checkout main
git branch -D "e2e-test/XXXX"
```

### App crashes due to missing environment variables
Use `fly secrets` to set any required env vars. Check the app logs to see which vars are missing:
```bash
# View logs to find missing env vars
fly logs --app "$FLY_APP_NAME" --no-tail

# Set additional secrets as needed
fly secrets set VAR_NAME="value" ANOTHER_VAR="value" --app "$FLY_APP_NAME"

# List current secrets
fly secrets list --app "$FLY_APP_NAME"
```

Common env vars that might be needed:
- `OPENAI_API_KEY` - Required for OpenAI models
- `DSPY_API_KEY` - Required when `--auth` is enabled
- Project-specific vars (check your gateway's `setup()` method)

## Multi-Layer Cleanup Protection

1. **Unique naming**: `dspy-e2e-{random}` prevents conflicts
2. **Pre-test orphan cleanup**: Removes stale resources before starting
3. **tmux session**: Enables output capture and manual recovery
4. **Explicit cleanup phase**: Always runs after tests
5. **Verification commands**: Confirm cleanup succeeded
