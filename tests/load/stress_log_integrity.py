#!/usr/bin/env python3
"""
Stress test: Log writer integrity.

Fires concurrent requests at the server, then parses every line of the
JSONL log files to verify:
  1. Every line is valid JSON
  2. Total log lines == total HTTP requests
  3. Per-program counts match
  4. Every log entry has required fields

Usage:
    python stress_log_integrity.py [--host HOST] [--port PORT] [--requests N] [--workers W] [--logs-dir DIR]
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REQUIRED_LOG_FIELDS = {"timestamp", "program", "model", "duration_ms", "inputs", "outputs", "success"}


def fire_request(host: str, port: int, program: str, idx: int) -> dict:
    """Send one request and return a result dict."""
    url = f"http://{host}:{port}/{program}"
    payload = json.dumps({"question": f"stress test {program} #{idx}"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"program": program, "status": resp.status, "ok": True}
    except urllib.error.HTTPError as e:
        return {"program": program, "status": e.code, "ok": False, "error": str(e)}
    except Exception as e:
        return {"program": program, "status": 0, "ok": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Log writer integrity stress test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--requests", type=int, default=200, help="Total requests to fire")
    parser.add_argument("--workers", type=int, default=30, help="Concurrent workers")
    parser.add_argument("--logs-dir", default=None, help="Path to logs directory")
    args = parser.parse_args()

    if args.logs_dir:
        logs_dir = Path(args.logs_dir)
    else:
        logs_dir = Path(__file__).parent / "fixture_project" / "logs"

    programs = ["SimplePredict", "AsyncPredict"]
    total = args.requests
    failures = []
    http_results = {"SimplePredict": {"success": 0, "error": 0}, "AsyncPredict": {"success": 0, "error": 0}}

    # Clear existing logs
    for prog in programs:
        log_file = logs_dir / f"{prog}.log"
        if log_file.exists():
            log_file.unlink()

    # Fire concurrent requests
    print(f"Firing {total} requests ({args.workers} concurrent workers)...")
    start = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = []
        for i in range(total):
            prog = programs[i % len(programs)]
            futures.append(pool.submit(fire_request, args.host, args.port, prog, i))

        for f in as_completed(futures):
            result = f.result()
            if result["ok"]:
                http_results[result["program"]]["success"] += 1
            else:
                http_results[result["program"]]["error"] += 1

    elapsed = time.time() - start
    total_success = sum(r["success"] for r in http_results.values())
    total_error = sum(r["error"] for r in http_results.values())
    print(f"Completed in {elapsed:.1f}s: {total_success} success, {total_error} error")

    # Wait briefly for the log writer to flush
    time.sleep(2)

    # Validate logs
    print("\nValidating JSONL logs...")
    log_counts = {}
    total_log_lines = 0
    parse_errors = 0
    field_errors = 0

    for prog in programs:
        log_file = logs_dir / f"{prog}.log"
        if not log_file.exists():
            if http_results[prog]["success"] + http_results[prog]["error"] > 0:
                failures.append(f"FAIL: Log file missing for {prog} (expected entries)")
            continue

        count = 0
        with open(log_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                count += 1

                # Check 1: Valid JSON
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    parse_errors += 1
                    failures.append(f"FAIL: {prog}.log line {line_num}: invalid JSON: {e}")
                    continue

                # Check 2: Required fields
                missing = REQUIRED_LOG_FIELDS - set(entry.keys())
                if missing:
                    field_errors += 1
                    failures.append(f"FAIL: {prog}.log line {line_num}: missing fields: {missing}")

                # Check 3: Program name matches file
                if entry.get("program") != prog:
                    failures.append(
                        f"FAIL: {prog}.log line {line_num}: program={entry.get('program')}, expected {prog}"
                    )

        log_counts[prog] = count
        total_log_lines += count

    # Check 4: Counts match
    expected_total = total_success + total_error  # Both success and error get logged
    if total_log_lines != expected_total:
        failures.append(
            f"FAIL: Total log lines ({total_log_lines}) != total requests ({expected_total})"
        )

    for prog in programs:
        expected = http_results[prog]["success"] + http_results[prog]["error"]
        actual = log_counts.get(prog, 0)
        if actual != expected:
            failures.append(
                f"FAIL: {prog} log lines ({actual}) != requests ({expected})"
            )

    # Report
    print(f"  Total log lines: {total_log_lines}")
    print(f"  Parse errors:    {parse_errors}")
    print(f"  Field errors:    {field_errors}")
    for prog in programs:
        print(f"  {prog}: {log_counts.get(prog, 0)} lines (expected {http_results[prog]['success'] + http_results[prog]['error']})")

    if failures:
        print(f"\n{'='*60}")
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    else:
        print(f"\nPASSED — {total_log_lines} log lines, all valid, counts match")
        sys.exit(0)


if __name__ == "__main__":
    main()
