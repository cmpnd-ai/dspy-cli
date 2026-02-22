"""Logging utilities for the API server."""

import json
import logging
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Background writer state
_log_queue: queue.Queue = queue.Queue()
_writer_thread: Optional[threading.Thread] = None
_shutdown_event = threading.Event()

_SENTINEL = None  # Signals the writer thread to stop


def start_log_writer() -> None:
    """Start the background log writer thread.

    Safe to call multiple times — restarts the writer if already stopped.
    """
    global _writer_thread, _shutdown_event

    if _writer_thread is not None and _writer_thread.is_alive():
        return

    _shutdown_event.clear()
    _writer_thread = threading.Thread(
        target=_log_writer_loop,
        name="log-writer",
        daemon=True,
    )
    _writer_thread.start()
    logger.info("Background log writer started")


def stop_log_writer(timeout: float = 5.0) -> None:
    """Stop the background log writer, flushing pending entries.

    Args:
        timeout: Maximum seconds to wait for the writer to drain.
    """
    global _writer_thread

    if _writer_thread is None or not _writer_thread.is_alive():
        return

    _shutdown_event.set()
    _log_queue.put(_SENTINEL)
    _writer_thread.join(timeout=timeout)
    _writer_thread = None
    logger.info("Background log writer stopped")


def _log_writer_loop() -> None:
    """Drain the log queue and write entries to per-program files.

    Runs in a dedicated thread. Batches up to 50 entries per flush
    for efficiency under high concurrency.
    """
    while True:
        entries: List[tuple] = []

        # Block for the first entry
        try:
            item = _log_queue.get(timeout=1.0)
        except queue.Empty:
            if _shutdown_event.is_set():
                break
            continue

        if item is _SENTINEL:
            # Drain any remaining entries before exiting
            while not _log_queue.empty():
                try:
                    remaining = _log_queue.get_nowait()
                    if remaining is not _SENTINEL:
                        entries.append(remaining)
                except queue.Empty:
                    break
            _flush_entries(entries)
            break

        entries.append(item)

        # Batch: grab up to 49 more without blocking
        for _ in range(49):
            try:
                item = _log_queue.get_nowait()
                if item is _SENTINEL:
                    _flush_entries(entries)
                    return
                entries.append(item)
            except queue.Empty:
                break

        _flush_entries(entries)


def _flush_entries(entries: List[tuple]) -> None:
    """Write a batch of log entries grouped by program to their files.

    Args:
        entries: List of (logs_dir, program_name, log_entry_dict) tuples.
    """
    if not entries:
        return

    # Group by (logs_dir, program_name) to minimize file opens
    grouped: Dict[tuple, List[str]] = {}
    for logs_dir, program_name, log_entry in entries:
        key = (str(logs_dir), program_name)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(json.dumps(log_entry))

    for (logs_dir_str, program_name), lines in grouped.items():
        logs_dir = Path(logs_dir_str)
        log_file = logs_dir / f"{program_name}.log"
        try:
            logs_dir.mkdir(exist_ok=True, parents=True)
            with open(log_file, "a") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            logger.error(f"Failed to write inference log for {program_name}: {e}")


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

    This enqueues the entry for the background writer thread, so it
    never blocks the calling thread or event loop.

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

    _log_queue.put((logs_dir, program_name, log_entry))


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
