"""Tests for the bounded executor and context propagation."""

import asyncio
import contextvars

import pytest

from dspy_cli.server.executor import (
    init_executor,
    run_sync_in_executor,
    shutdown_executor,
)


@pytest.fixture(autouse=True)
def _clean_executor():
    """Ensure each test gets a fresh executor."""
    yield
    shutdown_executor()


class TestContextPropagation:
    """Verify that contextvars set in the async caller are visible in executor threads.

    This is critical because dspy.context() stores per-request LM overrides in a
    ContextVar. If the executor doesn't propagate context, sync modules silently
    use the global LM instead of the per-request copy.
    """

    def test_contextvar_propagates_to_executor_thread(self):
        """A ContextVar set before run_sync_in_executor must be visible inside the thread."""
        cv = contextvars.ContextVar("test_cv", default="UNSET")
        init_executor(max_workers=2)

        def read_cv():
            return cv.get()

        async def run():
            cv.set("per-request-value")
            return await run_sync_in_executor(read_cv)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result == "per-request-value"

    def test_concurrent_requests_see_own_context(self):
        """Two concurrent tasks with different context values must each see their own."""
        cv = contextvars.ContextVar("test_cv", default="UNSET")
        init_executor(max_workers=4)

        results = {}

        def read_cv():
            import time
            time.sleep(0.05)  # Force overlap
            return cv.get()

        async def make_request(name: str, value: str):
            cv.set(value)
            result = await run_sync_in_executor(read_cv)
            results[name] = result

        async def run():
            await asyncio.gather(
                make_request("request_a", "model-alpha"),
                make_request("request_b", "model-beta"),
                make_request("request_c", "model-gamma"),
            )

        asyncio.get_event_loop().run_until_complete(run())
        assert results == {
            "request_a": "model-alpha",
            "request_b": "model-beta",
            "request_c": "model-gamma",
        }

    def test_dspy_context_lm_propagates(self):
        """dspy.context(lm=...) override must be visible inside executor thread."""
        import dspy

        init_executor(max_workers=2)

        def read_lm_in_thread():
            return dspy.settings.lm

        async def run():
            sentinel = object()
            with dspy.context(lm=sentinel):
                result = await run_sync_in_executor(read_lm_in_thread)
            return result, sentinel

        result, sentinel = asyncio.get_event_loop().run_until_complete(run())
        assert result is sentinel

    def test_fallback_without_executor(self):
        """Without init_executor, run_sync_in_executor should still propagate context."""
        cv = contextvars.ContextVar("test_cv", default="UNSET")
        # Don't call init_executor — executor is None

        def read_cv():
            return cv.get()

        async def run():
            cv.set("fallback-value")
            return await run_sync_in_executor(read_cv)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result == "fallback-value"
