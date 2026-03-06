#!/usr/bin/env bash
set -euo pipefail

# Stress test harness.
# Runs log integrity, error storm, and backpressure tests sequentially,
# each with its own server configuration. Reports pass/fail summary.
#
# Usage:
#     bash tests/load/run_stress_tests.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE_DIR="$SCRIPT_DIR/fixture_project"
CONFIG_FILE="$FIXTURE_DIR/dspy.config.yaml"
CONFIG_BACKUP="$CONFIG_FILE.bak"
MOCK_PORT=${MOCK_PORT:-9999}
SERVER_PORT=${SERVER_PORT:-8000}

# Test-specific settings
LOG_INTEGRITY_REQUESTS=${LOG_INTEGRITY_REQUESTS:-200}
LOG_INTEGRITY_WORKERS=${LOG_INTEGRITY_WORKERS:-30}
ERROR_STORM_REQUESTS=${ERROR_STORM_REQUESTS:-200}
ERROR_STORM_WORKERS=${ERROR_STORM_WORKERS:-30}
BACKPRESSURE_BURST=${BACKPRESSURE_BURST:-50}

# Track results (bash 3.2 compatible — no associative arrays)
RESULT_LOG_INTEGRITY="SKIP"
RESULT_ERROR_STORM="SKIP"
RESULT_BACKPRESSURE="SKIP"

kill_port() {
    lsof -ti:"$1" 2>/dev/null | xargs kill -9 2>/dev/null || true
}

cleanup() {
    echo ""
    echo "Cleaning up..."
    kill_port $MOCK_PORT
    kill_port $SERVER_PORT
    # Restore original config if backup exists
    if [ -f "$CONFIG_BACKUP" ]; then
        mv "$CONFIG_BACKUP" "$CONFIG_FILE"
    fi
    sleep 1
}
trap cleanup EXIT

wait_for_server() {
    local port=$1
    local url=$2
    local name=$3
    local max_wait=${4:-20}
    for i in $(seq 1 $max_wait); do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo "  $name ready."
            return 0
        fi
        sleep 1
    done
    echo "  ERROR: $name failed to start within ${max_wait}s"
    return 1
}

start_mock_server() {
    local delay_ms=${1:-50}
    local error_rate=${2:-0.0}
    echo "  Starting mock LLM (delay=${delay_ms}ms, error_rate=${error_rate})..."
    MOCK_DELAY_MS=$delay_ms MOCK_ERROR_RATE=$error_rate MOCK_PORT=$MOCK_PORT \
        python "$SCRIPT_DIR/mock_lm_server.py" > /dev/null 2>&1 &
    disown
    wait_for_server $MOCK_PORT "http://127.0.0.1:$MOCK_PORT/health" "Mock LLM"
}

start_dspy_server() {
    echo "  Starting dspy-cli server..."
    pushd "$FIXTURE_DIR" > /dev/null
    dspy-cli serve --port $SERVER_PORT --no-reload --no-save-openapi --system > /dev/null 2>&1 &
    disown
    popd > /dev/null
    wait_for_server $SERVER_PORT "http://127.0.0.1:$SERVER_PORT/programs" "dspy-cli server" 30
}

stop_servers() {
    kill_port $MOCK_PORT
    kill_port $SERVER_PORT
    sleep 1
}

write_config() {
    # Write a config with optional server section overrides
    local max_concurrent=${1:-""}
    cat > "$CONFIG_FILE" <<YAML
app_id: load-test-app
models:
  default: model-alpha
  registry:
    model-alpha:
      model: openai/mock-alpha
      api_base: http://127.0.0.1:${MOCK_PORT}/v1
      api_key: mock-key
      model_type: chat
      max_tokens: 100
      temperature: 1.0
      cache: false
    model-beta:
      model: openai/mock-beta
      api_base: http://127.0.0.1:${MOCK_PORT}/v1
      api_key: mock-key
      model_type: chat
      max_tokens: 100
      temperature: 1.0
      cache: false

program_models:
  SimplePredict: model-alpha
  AsyncPredict: model-beta
YAML

    if [ -n "$max_concurrent" ]; then
        cat >> "$CONFIG_FILE" <<YAML

server:
  max_concurrent_per_program: ${max_concurrent}
YAML
    fi
}

# ============================================================
# Save original config
# ============================================================
cp "$CONFIG_FILE" "$CONFIG_BACKUP"

# ============================================================
# Test 1: Log Integrity
# Normal config, no errors, verify JSONL logs
# ============================================================
echo ""
echo "============================================================"
echo "  TEST: Log Integrity"
echo "============================================================"

write_config
start_mock_server 50 0.0
start_dspy_server

if python "$SCRIPT_DIR/stress_log_integrity.py" \
    --port $SERVER_PORT \
    --requests $LOG_INTEGRITY_REQUESTS \
    --workers $LOG_INTEGRITY_WORKERS \
    --logs-dir "$FIXTURE_DIR/logs"; then
    RESULT_LOG_INTEGRITY="PASS"
    echo "  => Log Integrity: PASS"
else
    RESULT_LOG_INTEGRITY="FAIL"
    echo "  => Log Integrity: FAIL"
fi

stop_servers

# ============================================================
# Test 2: Error Storm
# Mock LLM returns 30% errors
# ============================================================
echo ""
echo "============================================================"
echo "  TEST: Error Storm"
echo "============================================================"

write_config
start_mock_server 50 0.9
start_dspy_server

if python "$SCRIPT_DIR/stress_error_storm.py" \
    --port $SERVER_PORT \
    --requests $ERROR_STORM_REQUESTS \
    --workers $ERROR_STORM_WORKERS; then
    RESULT_ERROR_STORM="PASS"
    echo "  => Error Storm: PASS"
else
    RESULT_ERROR_STORM="FAIL"
    echo "  => Error Storm: FAIL"
fi

stop_servers

# ============================================================
# Test 3: Backpressure
# Low semaphore (3), moderate LLM delay (1000ms), burst of 50
# ============================================================
echo ""
echo "============================================================"
echo "  TEST: Backpressure"
echo "============================================================"

write_config 3
start_mock_server 1000 0.0
start_dspy_server

if python "$SCRIPT_DIR/stress_backpressure.py" \
    --port $SERVER_PORT \
    --burst $BACKPRESSURE_BURST \
    --workers $BACKPRESSURE_BURST; then
    RESULT_BACKPRESSURE="PASS"
    echo "  => Backpressure: PASS"
else
    RESULT_BACKPRESSURE="FAIL"
    echo "  => Backpressure: FAIL"
fi

stop_servers

# ============================================================
# Summary
# ============================================================
echo ""
echo "========================================"
echo "  SUMMARY"
echo "========================================"

PASSED=0
FAILED=0

for result_var in RESULT_LOG_INTEGRITY RESULT_ERROR_STORM RESULT_BACKPRESSURE; do
    eval "result=\$$result_var"
    case $result_var in
        RESULT_LOG_INTEGRITY) name="Log Integrity" ;;
        RESULT_ERROR_STORM)   name="Error Storm" ;;
        RESULT_BACKPRESSURE)  name="Backpressure" ;;
    esac
    if [ "$result" = "PASS" ]; then
        echo "  PASS  $name"
        PASSED=$((PASSED + 1))
    else
        echo "  FAIL  $name"
        FAILED=$((FAILED + 1))
    fi
done

TOTAL=$((PASSED + FAILED))
echo ""
echo "  $PASSED/$TOTAL passed"

if [ "$FAILED" -gt 0 ]; then
    echo "  $FAILED FAILED"
    exit 1
else
    echo "  All tests passed!"
    exit 0
fi
