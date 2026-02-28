"""Logging utilities for the API server."""

import json
import logging
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_log_queue: queue.Queue = queue.Queue()
_writer_thread: Optional[threading.Thread] = None
_shutdown_event = threading.Event()
_SENTINEL = object()


def start_log_writer() -> None:
    """Start the background log writer thread."""
    global _writer_thread

    if _writer_thread is not None and _writer_thread.is_alive():
        return

    _shutdown_event.clear()
    _writer_thread = threading.Thread(target=_log_writer_loop, name="log-writer", daemon=True)
    _writer_thread.start()


def stop_log_writer(timeout: float = 5.0) -> None:
    """Stop the background log writer, flushing pending entries."""
    global _writer_thread

    if _writer_thread is None or not _writer_thread.is_alive():
        return

    _shutdown_event.set()
    _log_queue.put(_SENTINEL)
    _writer_thread.join(timeout=timeout)
    _writer_thread = None


def _log_writer_loop() -> None:
    """Drain the queue and batch-write entries to per-program log files."""
    while True:
        entries: list = []

        try:
            item = _log_queue.get(timeout=1.0)
        except queue.Empty:
            if _shutdown_event.is_set():
                break
            continue

        if item is _SENTINEL:
            _drain_remaining(entries)
            _flush_entries(entries)
            break

        entries.append(item)

        # Batch up to 49 more without blocking
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


def _drain_remaining(entries: list) -> None:
    """Drain any remaining items from the queue."""
    while not _log_queue.empty():
        try:
            item = _log_queue.get_nowait()
            if item is not _SENTINEL:
                entries.append(item)
        except queue.Empty:
            break


def _flush_entries(entries: list) -> None:
    """Write a batch of log entries grouped by program to their files."""
    if not entries:
        return

    grouped: Dict[tuple, List[str]] = {}
    for logs_dir, program_name, log_entry in entries:
        key = (str(logs_dir), program_name)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(json.dumps(log_entry))

    for (logs_dir_str, program_name), lines in grouped.items():
        log_dir = Path(logs_dir_str)
        log_file = log_dir / f"{program_name}.log"
        try:
            log_dir.mkdir(exist_ok=True, parents=True)
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
    """Enqueue an inference log entry for the background writer.

    Never blocks the calling thread or event loop.
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
