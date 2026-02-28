#!/usr/bin/env bash
set -euo pipefail

# Matrix benchmark: runs multiple delay x user-count scenarios.
#
# Each scenario boots fresh servers to avoid cross-contamination.
# Results go to tests/load/results/<label>_<delay>ms_<users>u_stats.csv
#
# Usage:
#   bash tests/load/run_matrix.sh                  # full matrix
#   LABEL=baseline bash tests/load/run_matrix.sh   # with custom label
#   DURATION=30s bash tests/load/run_matrix.sh      # shorter runs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
MOCK_PORT=${MOCK_PORT:-9999}
SERVER_PORT=${SERVER_PORT:-8000}
DURATION=${DURATION:-60s}
SPAWN_RATE=${SPAWN_RATE:-10}
BASE_LABEL=${LABEL:-"$(git -C "$REPO_ROOT" rev-parse --short HEAD)"}

# Matrix dimensions
DELAYS=(0 50 200 500 2000)
USERS_LIST=(50 100 200)
# 2000ms delay at 200 users = 400 threads needed, skip to keep runs reasonable
SKIP_2000_200=true

mkdir -p "$RESULTS_DIR"

kill_port() {
    lsof -ti:"$1" 2>/dev/null | xargs kill -9 2>/dev/null || true
}

SUMMARY_FILE="$RESULTS_DIR/${BASE_LABEL}_matrix_summary.csv"
echo "delay_ms,users,rps,p50_ms,p95_ms,p99_ms,max_ms,failure_pct,total_requests" > "$SUMMARY_FILE"

run_scenario() {
    local delay=$1
    local users=$2
    local label="${BASE_LABEL}_${delay}ms_${users}u"

    echo ""
    echo "================================================================"
    echo "  Scenario: delay=${delay}ms, users=${users}"
    echo "================================================================"

    # Ensure ports are free
    kill_port $MOCK_PORT
    kill_port $SERVER_PORT
    sleep 1

    # Start mock LLM server
    MOCK_DELAY_MS=$delay MOCK_PORT=$MOCK_PORT python "$SCRIPT_DIR/mock_lm_server.py" &
    sleep 1

    if ! curl -sf http://127.0.0.1:$MOCK_PORT/health > /dev/null; then
        echo "ERROR: Mock server failed to start for delay=${delay}ms"
        kill_port $MOCK_PORT
        return 1
    fi

    # Start dspy-cli server
    pushd "$SCRIPT_DIR/fixture_project" > /dev/null
    dspy-cli serve --port $SERVER_PORT --no-reload --no-save-openapi --system &
    popd > /dev/null
    sleep 3

    # Wait for server
    local ready=false
    for i in {1..20}; do
        if curl -sf http://127.0.0.1:$SERVER_PORT/programs > /dev/null; then
            ready=true
            break
        fi
        sleep 1
    done

    if [ "$ready" = false ]; then
        echo "ERROR: Server failed to start for scenario delay=${delay}ms users=${users}"
        kill_port $MOCK_PORT
        kill_port $SERVER_PORT
        sleep 1
        return 1
    fi

    # Run locust
    locust -f "$SCRIPT_DIR/locustfile.py" \
        --host http://127.0.0.1:$SERVER_PORT \
        --headless \
        -u $users -r $SPAWN_RATE \
        --run-time $DURATION \
        --csv "$RESULTS_DIR/$label" \
        --html "$RESULTS_DIR/$label.html" \
        2>&1 || true

    # Extract summary from CSV
    if [ -f "$RESULTS_DIR/${label}_stats.csv" ]; then
        local agg_line
        agg_line=$(grep "Aggregated" "$RESULTS_DIR/${label}_stats.csv" || echo "")
        if [ -n "$agg_line" ]; then
            local rps p50 p95 p99 max_rt req_count fail_count fail_pct
            rps=$(echo "$agg_line" | awk -F',' '{print $10}')
            p50=$(echo "$agg_line" | awk -F',' '{print $12}')
            p95=$(echo "$agg_line" | awk -F',' '{print $17}')
            p99=$(echo "$agg_line" | awk -F',' '{print $19}')
            max_rt=$(echo "$agg_line" | awk -F',' '{print $8}')
            req_count=$(echo "$agg_line" | awk -F',' '{print $3}')
            fail_count=$(echo "$agg_line" | awk -F',' '{print $4}')
            if [ "$req_count" -gt 0 ] 2>/dev/null; then
                fail_pct=$(python3 -c "print(f'{$fail_count/$req_count*100:.2f}')")
            else
                fail_pct="0.00"
            fi
            echo "$delay,$users,$rps,$p50,$p95,$p99,$max_rt,$fail_pct,$req_count" >> "$SUMMARY_FILE"
            echo "  -> RPS: $rps | P50: ${p50}ms | P95: ${p95}ms | P99: ${p99}ms | Failures: ${fail_pct}%"
        fi
    fi

    # Teardown — kill by port, not PID
    kill_port $SERVER_PORT
    kill_port $MOCK_PORT
    sleep 1
}

# Ensure clean state before starting
kill_port $MOCK_PORT
kill_port $SERVER_PORT
sleep 1

echo "Running benchmark matrix (${#DELAYS[@]} delays x ${#USERS_LIST[@]} user counts)"
echo "Duration per scenario: $DURATION"
echo "Results directory: $RESULTS_DIR"
echo "Label: $BASE_LABEL"

for delay in "${DELAYS[@]}"; do
    for users in "${USERS_LIST[@]}"; do
        # Skip 2000ms/200u scenario if configured
        if [ "$SKIP_2000_200" = true ] && [ "$delay" -eq 2000 ] && [ "$users" -eq 200 ]; then
            echo ""
            echo "  Skipping delay=2000ms users=200 (would need 400 threads)"
            continue
        fi
        run_scenario "$delay" "$users"
    done
done

echo ""
echo "================================================================"
echo "  Matrix complete. Summary:"
echo "================================================================"
echo ""
column -t -s',' "$SUMMARY_FILE" 2>/dev/null || cat "$SUMMARY_FILE"
echo ""
echo "Full summary: $SUMMARY_FILE"
echo "Individual results: $RESULTS_DIR/${BASE_LABEL}_*_stats.csv"
