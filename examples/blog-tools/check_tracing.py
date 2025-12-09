#!/usr/bin/env python3
"""Quick diagnostic script to check if tracing is working."""

import json
import sys
from pathlib import Path

def main():
    print("🔍 Checking DSPy CLI Tracing Setup\n")

    # Check 1: Modules importable
    print("1️⃣ Checking if tracing modules are installed...")
    try:
        from dspy_cli.server.trace_builder import TraceBuilder
        from dspy_cli.config.loader import get_trace_config
        print("   ✅ TraceBuilder available")
        print("   ✅ get_trace_config available")
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        print("\n   Fix: Run 'pip install -e .' from the dspy-cli directory")
        return False

    # Check 2: Config file
    print("\n2️⃣ Checking dspy.config.yaml...")
    config_path = Path("dspy.config.yaml")
    if not config_path.exists():
        print("   ❌ dspy.config.yaml not found")
        print("   Fix: Make sure you're in a DSPy project directory")
        return False

    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        if "tracing" in config:
            print("   ✅ Tracing section found in config")
            print(f"      enabled: {config['tracing'].get('enabled', 'not set')}")
            print(f"      store_in_logs: {config['tracing'].get('store_in_logs', 'not set')}")
            print(f"      max_trace_depth: {config['tracing'].get('max_trace_depth', 'not set')}")
        else:
            print("   ⚠️  No 'tracing' section in dspy.config.yaml")
            print("\n   Fix: Add this to your dspy.config.yaml:")
            print("""
tracing:
  enabled: true
  store_in_logs: true
  max_trace_depth: 50
            """)
            return False
    except Exception as e:
        print(f"   ❌ Error reading config: {e}")
        return False

    # Check 3: Log files
    print("\n3️⃣ Checking log files...")
    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("   ⚠️  No logs directory (will be created on first request)")
        print("   Make a request to your API to generate logs")
        return True

    log_files = list(logs_dir.glob("*.log"))
    if not log_files:
        print("   ⚠️  No log files found")
        print("   Make a request to your API to generate logs")
        return True

    print(f"   Found {len(log_files)} log file(s)")

    # Check 4: Trace data in logs
    print("\n4️⃣ Checking for trace data in logs...")
    found_traces = False

    for log_file in log_files:
        try:
            with open(log_file) as f:
                lines = f.readlines()
                if not lines:
                    print(f"   ⚠️  {log_file.name}: empty")
                    continue

                last_line = lines[-1].strip()
                if not last_line:
                    print(f"   ⚠️  {log_file.name}: last line empty")
                    continue

                entry = json.loads(last_line)
                has_trace = "trace" in entry

                if has_trace:
                    trace = entry["trace"]
                    span_count = len(trace.get("spans", []))
                    root_count = len(trace.get("root_call_ids", []))

                    print(f"   ✅ {log_file.name}:")
                    print(f"      - {span_count} spans")
                    print(f"      - {root_count} root call(s)")
                    print(f"      - trace_id: {trace.get('trace_id', 'missing')[:8]}...")

                    # Show span hierarchy
                    if span_count > 0:
                        print(f"      - Span hierarchy:")
                        for span in trace.get("spans", []):
                            indent = "  " * span.get("depth", 0)
                            name = span.get("name", "unknown")
                            span_type = span.get("type", "unknown")
                            print(f"        {indent}[{span_type}] {name}")

                    found_traces = True
                else:
                    print(f"   ❌ {log_file.name}: NO 'trace' field in latest entry")
                    print(f"      Keys found: {list(entry.keys())}")

        except json.JSONDecodeError as e:
            print(f"   ❌ {log_file.name}: Invalid JSON - {e}")
        except Exception as e:
            print(f"   ❌ {log_file.name}: Error - {e}")

    if not found_traces:
        print("\n   ⚠️  No traces found in any logs")
        print("\n   Troubleshooting:")
        print("   1. Make sure you've restarted the server after adding tracing config")
        print("   2. Kill any running servers: pkill -f 'dspy-cli serve'")
        print("   3. Start fresh: dspy-cli serve")
        print("   4. Make a new request to generate a fresh log entry")
        return False

    print("\n✅ Tracing is working correctly!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
