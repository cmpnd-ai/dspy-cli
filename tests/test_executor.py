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

    def test_contextvar_propagates_to_executor_thread(self):
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
        cv = contextvars.ContextVar("test_cv", default="UNSET")
        init_executor(max_workers=4)

        results = {}

        def read_cv():
            import time
            time.sleep(0.05)
            return cv.get()

        async def make_request(name: str, value: str):
            cv.set(value)
            results[name] = await run_sync_in_executor(read_cv)

        async def run():
            await asyncio.gather(
                make_request("a", "alpha"),
                make_request("b", "beta"),
                make_request("c", "gamma"),
            )

        asyncio.get_event_loop().run_until_complete(run())
        assert results == {"a": "alpha", "b": "beta", "c": "gamma"}

    def test_dspy_context_lm_propagates(self):
        import dspy

        init_executor(max_workers=2)

        def read_lm():
            return dspy.settings.lm

        async def run():
            sentinel = object()
            with dspy.context(lm=sentinel):
                result = await run_sync_in_executor(read_lm)
            return result, sentinel

        result, sentinel = asyncio.get_event_loop().run_until_complete(run())
        assert result is sentinel

    def test_fallback_without_init(self):
        cv = contextvars.ContextVar("test_cv", default="UNSET")

        def read_cv():
            return cv.get()

        async def run():
            cv.set("fallback-value")
            return await run_sync_in_executor(read_cv)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result == "fallback-value"
