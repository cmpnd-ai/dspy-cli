"""Streaming infrastructure for real-time DSPy callback events via Server-Sent Events (SSE)."""

import asyncio
import json
import logging
import time
from queue import Queue
from typing import Any, AsyncGenerator

from dspy.utils.callback import BaseCallback

logger = logging.getLogger(__name__)


class StreamingCallback(BaseCallback):
    """Custom DSPy callback that queues events for SSE streaming to frontend."""

    def __init__(self, event_queue: Queue):
        """Initialize callback with event queue.

        Args:
            event_queue: Thread-safe queue for passing events to SSE generator
        """
        self.event_queue = event_queue

    def _emit_event(self, event_type: str, call_id: str, data: dict):
        """Helper to queue events with metadata.

        Args:
            event_type: Type of event (e.g., 'lm_start', 'tool_end')
            call_id: Unique identifier for the call
            data: Event-specific data to include
        """
        event = {
            "type": event_type,
            "call_id": call_id,
            "timestamp": time.time(),
            **data,
        }
        logger.info(f"[StreamingCallback] Emitting event: {event_type} (queue size: {self.event_queue.qsize()})")
        self.event_queue.put(event)

    # Module callbacks
    def on_module_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when a DSPy Module starts execution."""
        logger.info(f"[StreamingCallback] on_module_start called: {instance.__class__.__name__}")
        self._emit_event(
            "module_start",
            call_id,
            {
                "module_name": instance.__class__.__name__,
                "inputs": inputs,
            },
        )

    def on_module_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when a DSPy Module completes execution."""
        logger.info(f"[StreamingCallback] on_module_end called: success={exception is None}")
        self._emit_event(
            "module_end",
            call_id,
            {
                "outputs": str(outputs) if outputs is not None else None,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

    # Language Model callbacks
    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when a Language Model call starts."""
        # Extract model name
        model_name = getattr(instance, "model", "unknown")
        logger.info(f"[StreamingCallback] on_lm_start called: model={model_name}")

        # Extract messages or prompt
        messages = inputs.get("messages", inputs.get("prompt", ""))

        self._emit_event(
            "lm_start",
            call_id,
            {
                "model": model_name,
                "messages": messages,
            },
        )

    def on_lm_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when a Language Model call completes."""
        logger.info(f"[StreamingCallback] on_lm_end called: success={exception is None}")

        # Try to extract response text and token count if available
        response_text = None
        token_count = None

        if outputs and isinstance(outputs, dict):
            # Handle common response formats
            if "choices" in outputs and len(outputs["choices"]) > 0:
                response_text = outputs["choices"][0].get("message", {}).get("content")
            elif "response" in outputs:
                response_text = outputs["response"]

            # Extract token usage if available
            if "usage" in outputs:
                token_count = outputs["usage"].get("total_tokens")

        self._emit_event(
            "lm_end",
            call_id,
            {
                "outputs": response_text or str(outputs) if outputs else None,
                "token_count": token_count,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

    # Tool callbacks
    def on_tool_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when a Tool is invoked."""
        tool_name = getattr(instance, "name", instance.__class__.__name__)
        logger.info(f"[StreamingCallback] on_tool_start called: tool={tool_name}")

        self._emit_event(
            "tool_start",
            call_id,
            {
                "tool_name": tool_name,
                "args": inputs,
            },
        )

    def on_tool_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when a Tool completes."""
        logger.info(f"[StreamingCallback] on_tool_end called: success={exception is None}")
        self._emit_event(
            "tool_end",
            call_id,
            {
                "outputs": outputs,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

    # Adapter callbacks
    def on_adapter_format_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when an Adapter's format() method starts."""
        logger.info(f"[StreamingCallback] on_adapter_format_start called: {instance.__class__.__name__}")
        self._emit_event(
            "adapter_format_start",
            call_id,
            {
                "adapter_type": instance.__class__.__name__,
            },
        )

    def on_adapter_format_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when an Adapter's format() method completes."""
        logger.info(f"[StreamingCallback] on_adapter_format_end called: success={exception is None}")
        self._emit_event(
            "adapter_format_end",
            call_id,
            {
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

    def on_adapter_parse_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when an Adapter's parse() method starts."""
        logger.info(f"[StreamingCallback] on_adapter_parse_start called: {instance.__class__.__name__}")
        self._emit_event(
            "adapter_parse_start",
            call_id,
            {
                "adapter_type": instance.__class__.__name__,
            },
        )

    def on_adapter_parse_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when an Adapter's parse() method completes."""
        logger.info(f"[StreamingCallback] on_adapter_parse_end called: success={exception is None}")
        self._emit_event(
            "adapter_parse_end",
            call_id,
            {
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )


async def event_stream_generator(event_queue: Queue, execution_task: asyncio.Task) -> AsyncGenerator[str, None]:
    """Async generator that yields Server-Sent Events.

    Args:
        event_queue: Queue containing events from StreamingCallback
        execution_task: Asyncio task running the DSPy module execution

    Yields:
        SSE-formatted strings: "data: {json}\\n\\n"
    """
    try:
        # Send initial connection event to verify streaming works
        logger.info("[SSE] Starting event stream")
        yield f"data: {json.dumps({'type': 'stream_start', 'timestamp': time.time()})}\n\n"

        event_count = 0
        while not execution_task.done():
            # Check for queued events
            if not event_queue.empty():
                event = event_queue.get()
                event_count += 1
                logger.info(f"[SSE] Streaming event #{event_count}: {event['type']}")
                # Yield the event - this should flush immediately
                yield f"data: {json.dumps(event)}\n\n"
                # Small delay to allow the event to be sent before checking for more
                await asyncio.sleep(0.01)
            else:
                # Send a comment line as keepalive to prevent buffering
                yield ": keepalive\n\n"
                # Prevent tight loop, yield control
                await asyncio.sleep(0.5)

        # Task completed - drain remaining events with a small delay to ensure all callbacks have fired
        await asyncio.sleep(0.1)

        logger.info(f"[SSE] Task completed, draining queue (size: {event_queue.qsize()})")
        while not event_queue.empty():
            event = event_queue.get()
            event_count += 1
            logger.info(f"[SSE] Streaming queued event #{event_count}: {event['type']}")
            yield f"data: {json.dumps(event)}\n\n"

        # Get the result or exception
        try:
            result = await execution_task
            logger.info(f"[SSE] Streaming final result (sent {event_count} events)")
            yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"
        except Exception as e:
            logger.error(f"[SSE] Execution error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    except asyncio.CancelledError:
        # Client disconnected
        logger.info("[SSE] Client disconnected")
        yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
