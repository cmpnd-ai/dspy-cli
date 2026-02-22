"""Bounded thread pool executor for sync DSPy module execution."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_executor: Optional[ThreadPoolExecutor] = None

# Match Python's default ThreadPoolExecutor size (same as asyncio.to_thread).
# Users can override via --sync-workers or server.sync_worker_threads config.
DEFAULT_SYNC_WORKERS = min(32, (os.cpu_count() or 1) + 4)


def get_executor() -> Optional[ThreadPoolExecutor]:
    """Return the current executor, or None if not initialized."""
    return _executor


def init_executor(max_workers: Optional[int] = None) -> ThreadPoolExecutor:
    """Create and store a bounded ThreadPoolExecutor.

    Args:
        max_workers: Maximum number of worker threads.
                     Defaults to DEFAULT_SYNC_WORKERS.

    Returns:
        The initialized ThreadPoolExecutor.
    """
    global _executor
    if _executor is not None:
        logger.warning("Executor already initialized, shutting down previous instance")
        _executor.shutdown(wait=False)

    workers = max_workers or DEFAULT_SYNC_WORKERS
    _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dspy-sync")
    logger.info(f"Initialized sync executor with {workers} worker threads")
    return _executor


def shutdown_executor() -> None:
    """Shut down the executor, waiting for pending work to complete."""
    global _executor
    if _executor is not None:
        logger.info("Shutting down sync executor")
        _executor.shutdown(wait=True)
        _executor = None


async def run_sync_in_executor(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a sync callable in the bounded executor.

    Falls back to asyncio.to_thread() if no executor has been initialized
    (e.g., during testing).

    Args:
        fn: Synchronous callable to execute.
        *args: Positional arguments for fn.
        **kwargs: Keyword arguments for fn.

    Returns:
        The return value of fn(*args, **kwargs).
    """
    loop = asyncio.get_running_loop()
    executor = _executor

    if kwargs:
        # ThreadPoolExecutor.submit doesn't support kwargs directly,
        # so we wrap in a lambda.
        call = lambda: fn(*args, **kwargs)  # noqa: E731
    else:
        call = lambda: fn(*args)  # noqa: E731

    if executor is not None:
        return await loop.run_in_executor(executor, call)
    else:
        # Fallback: use default executor (same as asyncio.to_thread)
        return await loop.run_in_executor(None, call)
