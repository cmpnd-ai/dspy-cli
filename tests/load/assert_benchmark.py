"""
Compares two locust CSV result files and fails if performance has regressed.
Usage: python tests/load/assert_benchmark.py results/baseline_stats.csv results/current_stats.csv
"""
import csv
import sys


def load_stats(path):
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Name"] == "Aggregated":
                return {
                    "rps": float(row["Requests/s"]),
                    "p95": float(row["95%"]),
                    "failures": float(row["Failure Count"]) / max(float(row["Request Count"]), 1),
                }
    raise ValueError(f"No 'Aggregated' row found in {path}")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <baseline_stats.csv> <current_stats.csv>")
        sys.exit(2)

    baseline = load_stats(sys.argv[1])
    current = load_stats(sys.argv[2])

    rps_change = (current["rps"] - baseline["rps"]) / baseline["rps"]
    p95_change = (current["p95"] - baseline["p95"]) / baseline["p95"]

    print(f"RPS:      {baseline['rps']:.1f} -> {current['rps']:.1f}  ({rps_change:+.1%})")
    print(f"P95 (ms): {baseline['p95']:.0f} -> {current['p95']:.0f}  ({p95_change:+.1%})")
    print(f"Failures: {baseline['failures']:.1%} -> {current['failures']:.1%}")

    errors = []
    if rps_change < -0.10:
        errors.append(f"RPS dropped {rps_change:.1%} (threshold: -10%)")
    if p95_change > 0.20:
        errors.append(f"P95 increased {p95_change:.1%} (threshold: +20%)")
    if current["failures"] > 0.01:
        errors.append(f"Failure rate {current['failures']:.1%} > 1%")

    if errors:
        print("\nREGRESSION DETECTED:")
        for e in errors:
            print(f"  x {e}")
        sys.exit(1)

    print("\nAll performance gates passed.")


if __name__ == "__main__":
    main()
