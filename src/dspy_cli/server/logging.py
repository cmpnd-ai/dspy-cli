"""Logging utilities for the API server."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def log_inference(
    logs_dir: Path,
    program_name: str,
    model: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    duration_ms: float,
    error: Optional[str] = None,
    tokens: Optional[Dict[str, int]] = None,
    cost_usd: Optional[float] = None,
    lm_calls: Optional[List[Dict[str, Any]]] = None,
):
    """Log a DSPy inference trace to a per-program log file.

    This creates a structured log entry suitable for use as training data,
    capturing the full inference trace including inputs, outputs, and metadata.

    Args:
        logs_dir: Directory to write log files
        program_name: Name of the DSPy program
        model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5')
        inputs: Input fields passed to the program
        outputs: Output fields from the program
        duration_ms: Execution duration in milliseconds
        error: Optional error message if inference failed
        tokens: Optional token counts {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        cost_usd: Optional total cost in USD for this inference
        lm_calls: Optional list of LM calls made during inference (for compound programs)
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "program": program_name,
        "model": model,
        "duration_ms": round(duration_ms, 2),
        "inputs": inputs,
        "outputs": outputs,
    }

    if error:
        log_entry["error"] = error
        log_entry["success"] = False
    else:
        log_entry["success"] = True

    if tokens:
        log_entry["tokens"] = tokens

    if cost_usd is not None:
        log_entry["cost_usd"] = round(cost_usd, 8)

    if lm_calls:
        log_entry["lm_calls"] = lm_calls

    log_file = logs_dir / f"{program_name}.log"

    try:
        logs_dir.mkdir(exist_ok=True, parents=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write inference log: {e}")


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
