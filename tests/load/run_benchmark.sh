#!/usr/bin/env bash
set -euo pipefail

# Single-scenario benchmark runner.
# For multi-scenario matrix, use run_matrix.sh instead.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
MOCK_PORT=${MOCK_PORT:-9999}
SERVER_PORT=${SERVER_PORT:-8000}
USERS=${USERS:-100}
SPAWN_RATE=${SPAWN_RATE:-10}
DURATION=${DURATION:-60s}
MOCK_DELAY_MS=${MOCK_DELAY_MS:-500}
LABEL=${LABEL:-"$(git -C "$REPO_ROOT" rev-parse --short HEAD)"}

mkdir -p "$RESULTS_DIR"

kill_port() {
    # Kill ALL processes listening on a port, including children
    lsof -ti:"$1" 2>/dev/null | xargs kill -9 2>/dev/null || true
}

cleanup() {
    echo "Cleaning up..."
    kill_port $MOCK_PORT
    kill_port $SERVER_PORT
    sleep 1
}
trap cleanup EXIT

# 0. Ensure ports are free before starting
kill_port $MOCK_PORT
kill_port $SERVER_PORT
sleep 1

# 1. Start mock LLM server
echo "Starting mock LLM server on :$MOCK_PORT (delay=${MOCK_DELAY_MS}ms)..."
MOCK_DELAY_MS=$MOCK_DELAY_MS MOCK_PORT=$MOCK_PORT python "$SCRIPT_DIR/mock_lm_server.py" &
sleep 1

if ! curl -sf http://127.0.0.1:$MOCK_PORT/health > /dev/null; then
    echo "ERROR: Mock LLM server failed to start"
    exit 1
fi
echo "Mock LLM server ready."

# 2. Start dspy-cli server against fixture project
echo "Starting dspy-cli server on :$SERVER_PORT..."
pushd "$SCRIPT_DIR/fixture_project" > /dev/null
dspy-cli serve --port $SERVER_PORT --no-reload --no-save-openapi --system &
popd > /dev/null
sleep 3

# 3. Wait for server health
echo "Waiting for server..."
for i in {1..20}; do
    if curl -sf http://127.0.0.1:$SERVER_PORT/programs > /dev/null; then
        echo "Server ready."
        break
    fi
    if [ $i -eq 20 ]; then
        echo "ERROR: Server failed to start within 20s"
        exit 1
    fi
    sleep 1
done

# 4. Run load test
echo "Running load test (users=$USERS, delay=${MOCK_DELAY_MS}ms, duration=$DURATION)..."
locust -f "$SCRIPT_DIR/locustfile.py" \
    --host http://127.0.0.1:$SERVER_PORT \
    --headless \
    -u $USERS -r $SPAWN_RATE \
    --run-time $DURATION \
    --csv "$RESULTS_DIR/$LABEL" \
    --html "$RESULTS_DIR/$LABEL.html"

echo "Results written to $RESULTS_DIR/$LABEL*.csv"
echo "Done."
