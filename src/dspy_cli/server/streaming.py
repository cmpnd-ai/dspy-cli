"""Streaming infrastructure for real-time DSPy callback events via Server-Sent Events (SSE)."""

import asyncio
import json
import logging
import time
from queue import Queue
from typing import Any, AsyncGenerator

import dspy
from dspy.utils.callback import BaseCallback

logger = logging.getLogger(__name__)


class StreamingCallback(BaseCallback):
    """Custom DSPy callback that queues events for SSE streaming to frontend.

    Enhanced with hierarchical span tracking, token usage aggregation,
    and rich metadata extraction following MLFlow patterns.
    """

    def __init__(self, event_queue: Queue, max_depth: int = 50):
        """Initialize callback with event queue.

        Args:
            event_queue: Thread-safe queue for passing events to SSE generator
            max_depth: Maximum call stack depth to prevent infinite recursion
        """
        self.event_queue = event_queue
        self.call_stack: list[str] = []  # Track parent-child relationships
        self.call_start_times: dict[str, float] = {}  # For duration calculation
        self.max_depth = max_depth
        self.call_id_to_instance: dict[str, Any] = {}  # Store instances for end callbacks
        self.collected_events: list[dict] = []  # Store all events for trace building

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
        # Also store for trace building (independent of queue consumption)
        self.collected_events.append(event)

    def _get_module_attributes(self, instance: Any) -> dict:
        """Extract rich metadata from module instance.

        Args:
            instance: DSPy module instance

        Returns:
            Dictionary with module attributes (signature, model config, etc.)
        """
        attrs = {"class": instance.__class__.__name__}

        # Extract signature information
        if hasattr(instance, "signature"):
            attrs["signature"] = repr(instance.signature)
        elif hasattr(instance, "predict") and hasattr(instance.predict, "signature"):
            attrs["signature"] = repr(instance.predict.signature)

        # Extract LM config if present
        if hasattr(instance, "lm") and instance.lm:
            lm = instance.lm
            attrs["model"] = getattr(lm, "model", None)
            attrs["model_type"] = getattr(lm, "model_type", None)
            # Filter sensitive data from kwargs
            if hasattr(lm, "kwargs"):
                safe_kwargs = {
                    k: v
                    for k, v in lm.kwargs.items()
                    if k not in {"api_key", "api_base", "api_secret", "organization"}
                }
                if safe_kwargs:
                    attrs["lm_config"] = safe_kwargs

        return attrs

    def _clean_inputs(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Clean and flatten input data.

        Removes empty args, flattens nested kwargs, optimizes signature serialization.

        Args:
            inputs: Raw input dictionary

        Returns:
            Cleaned input dictionary
        """
        # Remove empty args arrays
        if "args" in inputs and not inputs["args"]:
            inputs = {k: v for k, v in inputs.items() if k != "args"}

        # Flatten nested kwargs
        if "kwargs" in inputs:
            kwargs = inputs.pop("kwargs")
            inputs = {**inputs, **kwargs}

        # Convert Signature types to string representation (faster than full serialization)
        cleaned = {}
        for k, v in inputs.items():
            if isinstance(v, type) and issubclass(v, dspy.Signature):
                cleaned[k] = repr(v)
            else:
                cleaned[k] = v

        return cleaned

    def _process_outputs(self, outputs: Any) -> dict:
        """Process and normalize output data.

        Extracts token usage from dspy.Prediction objects and normalizes to dict.

        Args:
            outputs: Raw output from module/LM/tool

        Returns:
            Dictionary with 'data' and optional 'token_usage' fields
        """
        result = {"data": None, "token_usage": None}

        # Handle dspy.Prediction objects specially
        if isinstance(outputs, dspy.Prediction):
            # Extract token usage before converting to dict
            if hasattr(outputs, "get_lm_usage"):
                try:
                    usage_by_model = outputs.get_lm_usage()
                    if usage_by_model:
                        token_summary = {
                            "total_input_tokens": 0,
                            "total_output_tokens": 0,
                            "by_model": {},
                        }
                        for model, usage in usage_by_model.items():
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)
                            token_summary["total_input_tokens"] += input_tokens
                            token_summary["total_output_tokens"] += output_tokens
                            token_summary["by_model"][model] = {
                                "input": input_tokens,
                                "output": output_tokens,
                            }
                        result["token_usage"] = token_summary
                except Exception as e:
                    logger.warning(f"Failed to extract token usage: {e}")

            # Convert to dict for serialization
            result["data"] = outputs.toDict()
        else:
            result["data"] = outputs

        return result

    # Module callbacks
    def on_module_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when a DSPy Module starts execution."""
        logger.info(f"[StreamingCallback] on_module_start called: {instance.__class__.__name__}")

        # Check depth limit
        if len(self.call_stack) >= self.max_depth:
            logger.warning(f"Max call depth {self.max_depth} reached, skipping event")
            return

        # Track parent-child relationship
        parent_id = self.call_stack[-1] if self.call_stack else None
        self.call_stack.append(call_id)
        self.call_start_times[call_id] = time.time()
        self.call_id_to_instance[call_id] = instance

        self._emit_event(
            "module_start",
            call_id,
            {
                "parent_call_id": parent_id,
                "depth": len(self.call_stack) - 1,
                "module_name": instance.__class__.__name__,
                "attributes": self._get_module_attributes(instance),
                "inputs": self._clean_inputs(inputs.copy()),
            },
        )

    def on_module_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when a DSPy Module completes execution."""
        logger.info(f"[StreamingCallback] on_module_end called: success={exception is None}")

        # Calculate duration
        start_time = self.call_start_times.pop(call_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        # Process outputs with token extraction
        processed = self._process_outputs(outputs)

        self._emit_event(
            "module_end",
            call_id,
            {
                "duration_ms": duration_ms,
                "outputs": processed["data"],
                "token_usage": processed["token_usage"],
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

        # Pop from call stack
        if call_id in [c for c in self.call_stack]:
            self.call_stack.remove(call_id)
        self.call_id_to_instance.pop(call_id, None)

    # Language Model callbacks
    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when a Language Model call starts."""
        # Extract model name and type
        model_name = getattr(instance, "model", "unknown")
        model_type = getattr(instance, "model_type", None)
        logger.info(f"[StreamingCallback] on_lm_start called: model={model_name}")

        # Track parent and timing
        parent_id = self.call_stack[-1] if self.call_stack else None
        self.call_stack.append(call_id)
        self.call_start_times[call_id] = time.time()

        # Extract messages or prompt
        messages = inputs.get("messages", inputs.get("prompt", ""))

        # Filter sensitive kwargs
        safe_kwargs = {}
        if hasattr(instance, "kwargs"):
            safe_kwargs = {
                k: v
                for k, v in instance.kwargs.items()
                if k not in {"api_key", "api_base", "api_secret", "organization"}
            }

        self._emit_event(
            "lm_start",
            call_id,
            {
                "parent_call_id": parent_id,
                "depth": len(self.call_stack) - 1,
                "model": model_name,
                "model_type": model_type,
                "messages": messages,
                "lm_config": safe_kwargs if safe_kwargs else None,
            },
        )

    def on_lm_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when a Language Model call completes."""
        logger.info(f"[StreamingCallback] on_lm_end called: success={exception is None}")

        # Calculate duration
        start_time = self.call_start_times.pop(call_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        # Try to extract response text and token usage
        response_text = None
        token_usage = None

        if outputs and isinstance(outputs, dict):
            # Handle common response formats
            if "choices" in outputs and len(outputs["choices"]) > 0:
                response_text = outputs["choices"][0].get("message", {}).get("content")
            elif "response" in outputs:
                response_text = outputs["response"]

            # Extract detailed token usage if available
            if "usage" in outputs:
                usage = outputs["usage"]
                token_usage = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }

        self._emit_event(
            "lm_end",
            call_id,
            {
                "duration_ms": duration_ms,
                "outputs": response_text or str(outputs) if outputs else None,
                "token_usage": token_usage,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

        # Pop from call stack
        if call_id in self.call_stack:
            self.call_stack.remove(call_id)

    # Tool callbacks
    def on_tool_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when a Tool is invoked."""
        tool_name = getattr(instance, "name", instance.__class__.__name__)

        # Skip DSPy's internal "finish" tool
        if tool_name == "finish":
            return

        logger.info(f"[StreamingCallback] on_tool_start called: tool={tool_name}")

        # Track parent and timing
        parent_id = self.call_stack[-1] if self.call_stack else None
        self.call_stack.append(call_id)
        self.call_start_times[call_id] = time.time()

        # Extract tool metadata
        tool_desc = getattr(instance, "desc", None)
        tool_args_schema = getattr(instance, "args", None)

        self._emit_event(
            "tool_start",
            call_id,
            {
                "parent_call_id": parent_id,
                "depth": len(self.call_stack) - 1,
                "tool_name": tool_name,
                "description": tool_desc,
                "args_schema": tool_args_schema,
                "inputs": self._clean_inputs(inputs.copy()),
            },
        )

    def on_tool_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when a Tool completes."""
        logger.info(f"[StreamingCallback] on_tool_end called: success={exception is None}")

        # Calculate duration
        start_time = self.call_start_times.pop(call_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        self._emit_event(
            "tool_end",
            call_id,
            {
                "duration_ms": duration_ms,
                "outputs": outputs,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

        # Pop from call stack
        if call_id in self.call_stack:
            self.call_stack.remove(call_id)

    # Adapter callbacks
    def on_adapter_format_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when an Adapter's format() method starts."""
        logger.info(f"[StreamingCallback] on_adapter_format_start called: {instance.__class__.__name__}")

        parent_id = self.call_stack[-1] if self.call_stack else None
        self.call_stack.append(call_id)
        self.call_start_times[call_id] = time.time()

        self._emit_event(
            "adapter_format_start",
            call_id,
            {
                "parent_call_id": parent_id,
                "depth": len(self.call_stack) - 1,
                "adapter_type": instance.__class__.__name__,
            },
        )

    def on_adapter_format_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when an Adapter's format() method completes."""
        logger.info(f"[StreamingCallback] on_adapter_format_end called: success={exception is None}")

        start_time = self.call_start_times.pop(call_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        self._emit_event(
            "adapter_format_end",
            call_id,
            {
                "duration_ms": duration_ms,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

        if call_id in self.call_stack:
            self.call_stack.remove(call_id)

    def on_adapter_parse_start(self, call_id: str, instance: Any, inputs: dict[str, Any]):
        """Called when an Adapter's parse() method starts."""
        logger.info(f"[StreamingCallback] on_adapter_parse_start called: {instance.__class__.__name__}")

        parent_id = self.call_stack[-1] if self.call_stack else None
        self.call_stack.append(call_id)
        self.call_start_times[call_id] = time.time()

        self._emit_event(
            "adapter_parse_start",
            call_id,
            {
                "parent_call_id": parent_id,
                "depth": len(self.call_stack) - 1,
                "adapter_type": instance.__class__.__name__,
            },
        )

    def on_adapter_parse_end(self, call_id: str, outputs: Any | None, exception: Exception | None = None):
        """Called when an Adapter's parse() method completes.

        The outputs contain the structured data extracted from the LLM response,
        matching the signature's output fields (e.g., tags: list[str], sentiment: bool).
        """
        logger.info(f"[StreamingCallback] on_adapter_parse_end called: success={exception is None}")

        start_time = self.call_start_times.pop(call_id, None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else None

        # Process outputs - convert to serializable format
        parsed_outputs = None
        if outputs is not None:
            if isinstance(outputs, dict):
                parsed_outputs = outputs
            elif hasattr(outputs, 'toDict'):
                parsed_outputs = outputs.toDict()
            elif hasattr(outputs, '__dict__'):
                parsed_outputs = vars(outputs)
            else:
                parsed_outputs = str(outputs)

        self._emit_event(
            "adapter_parse_end",
            call_id,
            {
                "duration_ms": duration_ms,
                "outputs": parsed_outputs,
                "success": exception is None,
                "error": str(exception) if exception else None,
            },
        )

        if call_id in self.call_stack:
            self.call_stack.remove(call_id)


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
