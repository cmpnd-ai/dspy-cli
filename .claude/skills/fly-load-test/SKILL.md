---
name: fly-load-test
description: Load test dspy-cli on Fly.io with synthetic delay module (zero LLM cost). Finds per-machine concurrency ceiling, tests autoscaling, produces sizing guide. (project)
allowed-tools:
  - Bash
---

# Fly.io Load Test Skill

Deploy dspy-cli with a **SleepModule** (zero LLM cost) to Fly.io, use `hey` to find the per-machine concurrency ceiling, test multi-machine autoscaling, and produce a production sizing guide.

## CRITICAL RULES

1. **NEVER commit directly to main** - Always create a side branch
2. **ALWAYS clean up** - Destroy Fly apps and delete temp branches, even if tests fail
3. **No real LLM calls** - The SleepModule simulates latency with `time.sleep()`
4. **Record all results** - Print `hey` output and memory stats for every phase

## Prerequisites

1. **fly CLI**: Installed and authenticated (`fly auth whoami`)
2. **hey**: Load testing tool (`brew install hey`)
3. **Git**: Clean working directory (stash uncommitted changes first)
4. **Git push access**: Ability to push to origin

## Quick Start

### Phase 1: Setup Environment

```bash
export DSPY_CLI_DIR="/Users/isaac/projects/dspy-cli"
export TIMESTAMP=$(date +%s)
export RANDOM_SUFFIX=$(head -c 4 /dev/urandom | xxd -p)
export FLY_APP_NAME="dspy-load-${RANDOM_SUFFIX}"
export TEMP_BRANCH="load-test/${TIMESTAMP}-${RANDOM_SUFFIX}"
export DSPY_API_KEY_VALUE="load-test-$(head -c 8 /dev/urandom | xxd -p)"

echo "App: $FLY_APP_NAME Branch: $TEMP_BRANCH"
```

### Phase 2: Pre-flight Checks

```bash
fly version && fly auth whoami
which hey || echo "INSTALL hey: brew install hey"
git -C "$DSPY_CLI_DIR" status --porcelain

# Clean up any orphaned load test resources
fly apps list 2>/dev/null | grep "dspy-load" || echo "No orphaned apps"
```

### Phase 3: Create and Push Temp Branch

```bash
git -C "$DSPY_CLI_DIR" checkout -b "$TEMP_BRANCH"
git -C "$DSPY_CLI_DIR" push -u origin "$TEMP_BRANCH"
```

### Phase 4: Create Test Project with SleepModule

```bash
export TEST_DIR=$(mktemp -d) && echo "TEST_DIR=$TEST_DIR"

# Create project (pipe "Y" to accept the API key prompt)
echo "Y" | uv run --directory "$DSPY_CLI_DIR" dspy-cli new load-test-app \
  --program-name sleep_module \
  --signature "delay_seconds:float -> result:str" \
  --module-type Predict \
  --model openai/gpt-4o-mini

mv "$DSPY_CLI_DIR/load-test-app" "$TEST_DIR/"
cd "$TEST_DIR/load-test-app"
```

Now replace the generated module with SleepModule (which never calls an LM):

```bash
cd "$TEST_DIR/load-test-app"

# Find the generated module file and replace it
MODULE_FILE=$(find src/*/modules/ -name "*.py" ! -name "__init__.py" | head -1)
echo "Replacing module: $MODULE_FILE"

cat > "$MODULE_FILE" << 'PYEOF'
import time
import dspy


class SleepModule(dspy.Module):
    """Synthetic delay module for load testing. Never calls an LLM."""

    def forward(self, delay_seconds: float = 1.0) -> str:
        time.sleep(delay_seconds)
        return f"slept {delay_seconds}s"
PYEOF
```

### Phase 5: Modify for Git-Based dspy-cli

```bash
cd "$TEST_DIR/load-test-app"

# Install dspy-cli from temp branch
sed -i.bak "s|\"dspy-cli\"|\"dspy-cli @ git+https://github.com/cmpnd-ai/dspy-cli.git@$TEMP_BRANCH\"|" pyproject.toml

# Custom Dockerfile with git support
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

CMD ["uv", "run", "dspy-cli", "serve", "--host", "0.0.0.0", "--port", "8000", "--auth", "--no-reload", "--sync-workers", "64"]
EOF
```

**IMPORTANT**: The `--sync-workers` value in the CMD changes per phase:
- Phase A: `--sync-workers 64`
- Phase B: `--sync-workers 128`
- Phase C: `--sync-workers 256`

To change it between phases, edit the Dockerfile CMD and redeploy:
```bash
sed -i.bak 's/--sync-workers [0-9]*/--sync-workers 128/' Dockerfile
fly deploy --app "$FLY_APP_NAME" --wait-timeout 300
```

### Phase 6: Create fly.toml and Deploy

```bash
cd "$TEST_DIR/load-test-app"

cat > fly.toml << EOF
app = '$FLY_APP_NAME'
primary_region = 'ewr'

[build]

[deploy]
  ha = false

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = 'stop'
  auto_start_machines = true
  min_machines_running = 1
  processes = ['app']

  [http_service.concurrency]
    type = 'requests'
    soft_limit = 100
    hard_limit = 128

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
  memory = '1gb'
  cpu_kind = 'shared'
  cpus = 2
EOF

fly apps create "$FLY_APP_NAME" --org personal

# Dummy OpenAI key -- SleepModule never calls an LM, but dspy.LM() init needs it
fly secrets set OPENAI_API_KEY="sk-dummy-not-used" DSPY_API_KEY="$DSPY_API_KEY_VALUE" --app "$FLY_APP_NAME"

fly deploy --app "$FLY_APP_NAME" --wait-timeout 300
```

### Phase 7: Wait for Ready

```bash
export FLY_APP_URL="https://$FLY_APP_NAME.fly.dev"

for i in $(seq 1 60); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FLY_APP_URL/health/ready")
  if [ "$STATUS" = "200" ]; then echo "App ready after ${i}s"; break; fi
  echo "Waiting... ($STATUS)"
  sleep 2
done

# Confirm SleepModule is discovered
curl -s -H "Authorization: Bearer $DSPY_API_KEY_VALUE" "$FLY_APP_URL/programs"
```

### Phase 8: Single-Machine Load Tests

Run `hey` sweeps at increasing concurrency. Each run sends 200 requests with a 1s sleep delay. Theoretical max throughput = `min(concurrency, sync_workers)` rps.

**Phase A: --sync-workers 64**

```bash
export URL="$FLY_APP_URL/SleepModule"
export AUTH="Authorization: Bearer $DSPY_API_KEY_VALUE"
export BODY='{"delay_seconds": 1.0}'

echo "=== Phase A: 64 workers, c=10 ==="
hey -n 200 -c 10 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase A: 64 workers, c=32 ==="
hey -n 200 -c 32 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase A: 64 workers, c=64 ==="
hey -n 200 -c 64 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase A: 64 workers, c=100 ==="
hey -n 200 -c 100 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase A: 64 workers, c=128 ==="
hey -n 200 -c 128 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

# Check memory after heavy load
fly ssh console --app "$FLY_APP_NAME" -C "cat /proc/meminfo | head -5"
```

**Phase B: --sync-workers 128** (redeploy first)

```bash
cd "$TEST_DIR/load-test-app"
sed -i.bak 's/--sync-workers [0-9]*/--sync-workers 128/' Dockerfile
fly deploy --app "$FLY_APP_NAME" --wait-timeout 300

# Wait for ready
for i in $(seq 1 60); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FLY_APP_URL/health/ready")
  if [ "$STATUS" = "200" ]; then echo "Ready after ${i}s"; break; fi
  sleep 2
done

echo "=== Phase B: 128 workers, c=64 ==="
hey -n 200 -c 64 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase B: 128 workers, c=128 ==="
hey -n 200 -c 128 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase B: 128 workers, c=200 ==="
hey -n 300 -c 200 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase B: 128 workers, c=256 ==="
hey -n 300 -c 256 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

fly ssh console --app "$FLY_APP_NAME" -C "cat /proc/meminfo | head -5"
```

**Phase C: --sync-workers 256** (redeploy, only if Phase B didn't OOM)

```bash
cd "$TEST_DIR/load-test-app"
sed -i.bak 's/--sync-workers [0-9]*/--sync-workers 256/' Dockerfile
fly deploy --app "$FLY_APP_NAME" --wait-timeout 300

for i in $(seq 1 60); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FLY_APP_URL/health/ready")
  if [ "$STATUS" = "200" ]; then echo "Ready after ${i}s"; break; fi
  sleep 2
done

echo "=== Phase C: 256 workers, c=128 ==="
hey -n 200 -c 128 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase C: 256 workers, c=256 ==="
hey -n 300 -c 256 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Phase C: 256 workers, c=300 ==="
hey -n 300 -c 300 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

fly ssh console --app "$FLY_APP_NAME" -C "cat /proc/meminfo | head -5"
```

### Phase 9: Multi-Machine Autoscaling Test

Use the best `--sync-workers` from Phases A-C. Remove `ha = false` and scale to 3 machines:

```bash
cd "$TEST_DIR/load-test-app"

# Update fly.toml: remove ha = false
sed -i.bak '/ha = false/d' fly.toml

# Set concurrency limits based on findings (adjust these!)
# soft_limit = ~80% of sync_workers, hard_limit = sync_workers
# Example for 128 workers:
sed -i.bak 's/soft_limit = [0-9]*/soft_limit = 100/' fly.toml
sed -i.bak 's/hard_limit = [0-9]*/hard_limit = 128/' fly.toml

fly deploy --app "$FLY_APP_NAME" --wait-timeout 300

# Scale to 3 machines
fly scale count 3 --app "$FLY_APP_NAME"

# Wait for all machines to be ready
sleep 30
fly machines list --app "$FLY_APP_NAME"

for i in $(seq 1 60); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FLY_APP_URL/health/ready")
  if [ "$STATUS" = "200" ]; then echo "Ready after ${i}s"; break; fi
  sleep 2
done
```

Now blast at concurrency levels that should trigger multi-machine distribution:

```bash
# Should spread across machines (3 x 128 = 384 slots)
echo "=== Autoscale: c=100 (fits in 1 machine) ==="
hey -n 300 -c 100 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Autoscale: c=200 (needs 2 machines) ==="
hey -n 400 -c 200 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

echo "=== Autoscale: c=300 (needs 3 machines) ==="
hey -n 600 -c 300 -t 30 -m POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

# Check machine status (which ones are started/stopped)
fly machines list --app "$FLY_APP_NAME"
```

**Test auto-stop/auto-start:**

```bash
# Wait for idle machines to stop (~5 min)
echo "Waiting 5 minutes for auto-stop..."
sleep 300
fly machines list --app "$FLY_APP_NAME"

# Hit the endpoint -- should auto-start a machine
echo "=== Cold start test ==="
time curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" -d "$BODY" "$URL"

# Check: how long did the cold start take?
fly machines list --app "$FLY_APP_NAME"
```

### Phase 10: Guaranteed Cleanup

**ALWAYS run cleanup, even if tests fail:**

```bash
fly apps destroy "$FLY_APP_NAME" --yes

git -C "$DSPY_CLI_DIR" push origin --delete "$TEMP_BRANCH"
git -C "$DSPY_CLI_DIR" checkout main
git -C "$DSPY_CLI_DIR" branch -D "$TEMP_BRANCH"

rm -rf "$TEST_DIR"
```

## Interpreting Results

### hey Output Key Metrics

```
Summary:
  Total:        X.XXX secs        ← wall clock time
  Requests/sec: XX.XX             ← throughput (target: min(concurrency, sync_workers))

Latency distribution:
  50% in X.XXX secs               ← should be ~1s (the sleep duration) when not queuing
  95% in X.XXX secs               ← spikes here = queuing
  99% in X.XXX secs               ← worst case

Status code distribution:
  [200] XXX responses              ← success
  [503] XXX responses              ← server overloaded (hit hard_limit or OOM)
```

### What Good Looks Like

| Concurrency | Expected RPS (128 workers) | Expected p50 | Sign of trouble |
|-------------|---------------------------|-------------|-----------------|
| c <= workers | ~c rps | ~1.0s | - |
| c = workers | ~workers rps | ~1.0s | Perfect saturation |
| c = 1.5x workers | ~workers rps | ~1.5s | Queuing (expected) |
| c = 2x workers | ~workers rps | ~2.0s | Deep queue |
| Any | < expected | > 3s | OOM, CPU thrash, or errors |

### Memory Check

```bash
fly ssh console --app "$FLY_APP_NAME" -C "cat /proc/meminfo | head -5"
```

If `MemAvailable` drops below ~100MB under load, you've found the memory wall. Reduce `--sync-workers` or increase VM memory.

## Production Sizing Guide

*Fill in after running tests. Template:*

| Target Concurrent | VM | `--sync-workers` | `soft_limit` | `hard_limit` | Machines |
|-------------------|-----|-----------------|-------------|-------------|----------|
| 50 | shared-cpu-2x 1gb | ? | ? | ? | 1 |
| 100 | shared-cpu-2x 1gb | ? | ? | ? | 1 |
| 200 | shared-cpu-2x 1gb | ? | ? | ? | 2 |
| 500 | shared-cpu-2x 1gb | ? | ? | ? | 4-5 |

**Rules:**
- `hard_limit = sync_workers` (the thread pool ceiling; no more concurrent work is possible)
- `soft_limit = ~80% of sync_workers` (gives fly ~seconds to wake another machine)
- Machines = `ceil(target_concurrent / hard_limit)`

## Cleanup Verification

```bash
fly apps list | grep "dspy-load" || echo "No orphaned apps"
git branch -r | grep "load-test/" || echo "No orphaned branches"
```

## Troubleshooting

### SleepModule not discovered
Check that the module file is in `src/<pkg>/modules/` and the class inherits from `dspy.Module`. Verify with:
```bash
fly ssh console --app "$FLY_APP_NAME" -C "sh -c 'find /src -name \"*.py\" | head -20'"
```

### "No module named dspy" during build
The `uv sync --no-dev` in Dockerfile should install dspy via the dspy-cli dependency. Check `pyproject.toml` has the git URL correctly.

### OOM kills during load test
Reduce `--sync-workers`, or increase VM memory. Check:
```bash
fly logs --app "$FLY_APP_NAME" --no-tail | grep -i "oom\|kill\|memory"
```

### hey: "socket: too many open files"
On macOS, increase ulimit before running hey:
```bash
ulimit -n 10240
```

### Autoscaling doesn't trigger
Verify concurrency limits in fly.toml match what's deployed:
```bash
fly config show --app "$FLY_APP_NAME" | grep -A5 concurrency
```
Fly only wakes stopped machines when `soft_limit` is exceeded. If all machines are already running, no new ones start (fly doesn't create machines, only starts/stops existing ones).

### Machines don't auto-stop
`auto_stop_machines = 'stop'` only stops machines with zero connections. If hey keeps connections alive, wait for them to close. Default idle timeout is ~5 minutes.
