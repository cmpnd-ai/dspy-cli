#!/usr/bin/env python3
"""
Stress test: Backpressure behavior.

Sends a burst of concurrent requests that exceeds the server's
max_concurrent_per_program limit. Validates:
  1. Requests that fit in the semaphore succeed (200)
  2. Excess requests queue and eventually succeed OR get 429 after timeout
  3. No other error codes appear (no crashes, no 502s)
  4. Server recovers — health check passes after the burst

The server should be configured with a low max_concurrent_per_program
(e.g., 3) and the mock LLM with a moderate delay (e.g., 1000ms) so the
semaphore actually fills up.

Usage:
    python stress_backpressure.py [--host HOST] [--port PORT] [--burst N] [--workers W]
"""
import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed


def fire_request(host: str, port: int, idx: int) -> dict:
    """Send one request and return a result dict."""
    url = f"http://{host}:{port}/SimplePredict"
    payload = json.dumps({"question": f"backpressure #{idx}"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return {"status": resp.status, "duration": time.time() - start, "body": body}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = None
        return {"status": e.code, "duration": time.time() - start, "body": body}
    except Exception as e:
        return {"status": 0, "duration": time.time() - start, "error": str(e)}


def check_health(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/programs"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Backpressure stress test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--burst", type=int, default=50, help="Number of simultaneous requests")
    parser.add_argument("--workers", type=int, default=50, help="Thread pool size (should match burst)")
    args = parser.parse_args()

    failures = []

    if not check_health(args.host, args.port):
        print("FAIL: Server not healthy before test")
        sys.exit(1)

    # Fire a single burst — all at once
    print(f"Firing burst of {args.burst} simultaneous requests...")
    start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(fire_request, args.host, args.port, i)
            for i in range(args.burst)
        ]
        for f in as_completed(futures):
            results.append(f.result())

    elapsed = time.time() - start

    # Categorize results
    ok_200 = [r for r in results if r["status"] == 200]
    rejected_429 = [r for r in results if r["status"] == 429]
    connection_errors = [r for r in results if r["status"] == 0]
    other_errors = [r for r in results if r["status"] not in (200, 429, 0)]

    print(f"Completed in {elapsed:.1f}s")
    print(f"  200 OK:           {len(ok_200)}")
    print(f"  429 Too Many:     {len(rejected_429)}")
    print(f"  Connection errors: {len(connection_errors)}")
    print(f"  Other errors:     {len(other_errors)}")

    if ok_200:
        durations = [r["duration"] for r in ok_200]
        print(f"  200 latency:      min={min(durations):.2f}s  max={max(durations):.2f}s  avg={sum(durations)/len(durations):.2f}s")

    if rejected_429:
        durations = [r["duration"] for r in rejected_429]
        print(f"  429 latency:      min={min(durations):.2f}s  max={max(durations):.2f}s  avg={sum(durations)/len(durations):.2f}s")

    # Check 1: Some requests succeeded
    if len(ok_200) == 0:
        failures.append("FAIL: Zero successes — server may be completely broken")

    # Check 2: No connection errors
    if connection_errors:
        failures.append(f"FAIL: {len(connection_errors)} connection errors — server may have crashed")

    # Check 3: No unexpected error codes (502, 503, etc.)
    if other_errors:
        codes = [r["status"] for r in other_errors]
        failures.append(f"FAIL: Unexpected status codes: {codes}")

    # Check 4: 429 responses should NOT be instant (the old sem.locked() bug)
    # They should take ~30s (the queue timeout) or not appear at all
    # (if the burst fits within semaphore + queue time).
    # If 429s appear in under 1 second, the semaphore is rejecting eagerly.
    instant_429s = [r for r in rejected_429 if r["duration"] < 1.0]
    if instant_429s:
        failures.append(
            f"FAIL: {len(instant_429s)} requests got instant 429 (<1s) — "
            f"semaphore may be rejecting without queuing"
        )

    # Check 5: All responses (200 and 429) have well-formed JSON bodies
    malformed = [r for r in results if r["status"] in (200, 429) and r.get("body") is None]
    if malformed:
        failures.append(f"FAIL: {len(malformed)} responses had no JSON body")

    # Check 6: Server recovers
    time.sleep(1)
    if not check_health(args.host, args.port):
        failures.append("FAIL: Server not healthy after burst")

    # Report
    if failures:
        print(f"\n{'='*60}")
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    else:
        print(f"\nPASSED — {len(ok_200)} served, {len(rejected_429)} queued/rejected cleanly, server recovered")
        sys.exit(0)


if __name__ == "__main__":
    main()
