"""Metrics aggregation for DSPy programs."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProgramMetrics:
    """Aggregated metrics for a single program."""

    program: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    last_call_ts: Optional[datetime] = None
    avg_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: Optional[float] = None
    lm_call_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "program": self.program,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_call_ts": self.last_call_ts.isoformat() if self.last_call_ts else None,
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            "p95_latency_ms": round(self.p95_latency_ms, 2) if self.p95_latency_ms else None,
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6) if self.total_cost_usd else None,
            "lm_call_breakdown": self.lm_call_breakdown,
        }


def compute_program_metrics(logs_dir: Path, program_name: str) -> ProgramMetrics:
    """Compute metrics for a program by scanning its log file.

    Args:
        logs_dir: Directory containing log files
        program_name: Name of the program

    Returns:
        ProgramMetrics with aggregated data
    """
    log_file = logs_dir / f"{program_name}.log"
    metrics = ProgramMetrics(program=program_name)

    if not log_file.exists():
        return metrics

    durations: List[float] = []
    total_cost = 0.0
    has_cost = False
    lm_breakdown: Dict[str, Dict[str, Any]] = {}

    try:
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                metrics.call_count += 1

                if entry.get("success", True):
                    metrics.success_count += 1
                else:
                    metrics.error_count += 1

                # Timestamp
                ts_str = entry.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        # Normalize to UTC-aware datetime for consistent comparison
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        else:
                            ts = ts.astimezone(timezone.utc)
                        if metrics.last_call_ts is None or ts > metrics.last_call_ts:
                            metrics.last_call_ts = ts
                    except ValueError:
                        pass

                # Latency
                duration = entry.get("duration_ms")
                if isinstance(duration, (int, float)):
                    durations.append(duration)

                # Tokens
                tokens = entry.get("tokens")
                if isinstance(tokens, dict):
                    metrics.total_prompt_tokens += tokens.get("prompt_tokens", 0) or 0
                    metrics.total_completion_tokens += tokens.get("completion_tokens", 0) or 0
                    metrics.total_tokens += tokens.get("total_tokens", 0) or 0

                # Cost
                cost = entry.get("cost_usd")
                if cost is not None:
                    total_cost += cost
                    has_cost = True

                # LM call breakdown (for compound programs)
                lm_calls = entry.get("lm_calls")
                if isinstance(lm_calls, list):
                    for call in lm_calls:
                        model = call.get("model", "unknown")
                        if model not in lm_breakdown:
                            lm_breakdown[model] = {
                                "call_count": 0,
                                "total_prompt_tokens": 0,
                                "total_completion_tokens": 0,
                                "total_cost_usd": 0.0,
                            }
                        lm_breakdown[model]["call_count"] += 1
                        lm_breakdown[model]["total_prompt_tokens"] += call.get("prompt_tokens", 0) or 0
                        lm_breakdown[model]["total_completion_tokens"] += call.get("completion_tokens", 0) or 0
                        if call.get("cost_usd") is not None:
                            lm_breakdown[model]["total_cost_usd"] += call["cost_usd"]

    except Exception as e:
        logger.error(f"Error reading log file {log_file}: {e}")
        return metrics

    # Compute latency stats
    if durations:
        metrics.avg_latency_ms = sum(durations) / len(durations)
        sorted_durations = sorted(durations)
        p95_idx = int(0.95 * (len(sorted_durations) - 1))
        metrics.p95_latency_ms = sorted_durations[p95_idx]

    if has_cost:
        metrics.total_cost_usd = total_cost

    metrics.lm_call_breakdown = lm_breakdown

    return metrics


def _file_signature(path: Path) -> tuple:
    """Get file signature (size, mtime) for cache invalidation."""
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime)
    except FileNotFoundError:
        return (0, 0)


def get_program_metrics_cached(
    logs_dir: Path,
    program_name: str,
    cache: Dict[str, Dict[str, Any]],
) -> ProgramMetrics:
    """Get metrics with file-based cache invalidation.

    Args:
        logs_dir: Directory containing log files
        program_name: Name of the program
        cache: Dictionary to store cached metrics

    Returns:
        ProgramMetrics (from cache if valid, recomputed otherwise)
    """
    log_file = logs_dir / f"{program_name}.log"
    sig = _file_signature(log_file)

    cached = cache.get(program_name)
    if cached and cached.get("sig") == sig:
        return cached["metrics"]

    metrics = compute_program_metrics(logs_dir, program_name)
    cache[program_name] = {"metrics": metrics, "sig": sig}
    return metrics


def get_all_metrics(
    logs_dir: Path,
    program_names: List[str],
    cache: Dict[str, Dict[str, Any]],
    sort_by: str = "name",
    order: str = "desc",
) -> List[ProgramMetrics]:
    """Get metrics for all programs with sorting.

    Args:
        logs_dir: Directory containing log files
        program_names: List of program names
        cache: Metrics cache dictionary
        sort_by: Sort key (name, calls, latency, cost, tokens)
        order: Sort order (asc, desc)

    Returns:
        Sorted list of ProgramMetrics
    """
    metrics_list = [
        get_program_metrics_cached(logs_dir, name, cache)
        for name in program_names
    ]

    reverse = order == "desc"

    if sort_by == "calls":
        metrics_list.sort(key=lambda m: m.call_count, reverse=reverse)
    elif sort_by == "latency":
        metrics_list.sort(key=lambda m: m.avg_latency_ms or 0.0, reverse=reverse)
    elif sort_by == "cost":
        metrics_list.sort(key=lambda m: m.total_cost_usd or 0.0, reverse=reverse)
    elif sort_by == "tokens":
        metrics_list.sort(key=lambda m: m.total_tokens, reverse=reverse)
    elif sort_by == "last_call":
        metrics_list.sort(
            key=lambda m: m.last_call_ts or datetime.min.replace(tzinfo=timezone.utc),
            reverse=reverse,
        )
    else:  # name
        metrics_list.sort(key=lambda m: m.program, reverse=reverse)

    return metrics_list
