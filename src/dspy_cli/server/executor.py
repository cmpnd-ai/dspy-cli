"""Bounded thread pool executor for sync DSPy module execution.

Sync forward() calls are dispatched here so they don't block the async
event loop. Context variables (including dspy.context overrides) are
propagated into the worker thread automatically.
"""

import asyncio
import contextvars
import functools
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_executor: Optional[ThreadPoolExecutor] = None

DEFAULT_SYNC_WORKERS = min(32, (os.cpu_count() or 1) + 4)


def init_executor(max_workers: Optional[int] = None) -> ThreadPoolExecutor:
    """Create the process-wide bounded executor."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)

    workers = max_workers or DEFAULT_SYNC_WORKERS
    _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dspy-sync")
    logger.info(f"Initialized sync executor with {workers} worker threads")
    return _executor


def shutdown_executor() -> None:
    """Shut down the executor, waiting for pending work."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


async def run_sync_in_executor(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a sync callable in the bounded executor with context propagation.

    Falls back to the default executor if init_executor() hasn't been called.
    """
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, fn, *args, **kwargs)
    return await loop.run_in_executor(_executor, func_call)
