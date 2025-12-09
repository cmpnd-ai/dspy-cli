"""Utility for aggregating callback events into hierarchical execution traces.

This module provides the TraceBuilder class that collects flat callback events
and builds a structured, hierarchical trace suitable for logging and visualization.
"""

import uuid
from typing import Any


class TraceBuilder:
    """Builds hierarchical execution traces from flat callback events.

    Aggregates events from StreamingCallback into a structured trace with:
    - Hierarchical span relationships (parent-child)
    - Timing information per span
    - Token usage aggregation
    - Root call identification
    """

    def __init__(self):
        """Initialize trace builder."""
        self.trace_id = str(uuid.uuid4())
        self.spans: dict[str, dict[str, Any]] = {}  # call_id -> span data
        self.root_call_ids: list[str] = []  # Top-level calls (no parent)
        self.events: list[dict[str, Any]] = []  # Raw events for debugging

    def add_event(self, event: dict[str, Any]):
        """Process and add a callback event to the trace.

        Args:
            event: Event dictionary from StreamingCallback
        """
        self.events.append(event)
        event_type = event.get("type")
        call_id = event.get("call_id")

        if not call_id:
            return

        # Handle start events
        if event_type in {
            "module_start",
            "lm_start",
            "tool_start",
            "adapter_format_start",
            "adapter_parse_start",
        }:
            self._handle_start_event(event)

        # Handle end events
        elif event_type in {
            "module_end",
            "lm_end",
            "tool_end",
            "adapter_format_end",
            "adapter_parse_end",
        }:
            self._handle_end_event(event)

    def _handle_start_event(self, event: dict[str, Any]):
        """Process a start event and create span entry.

        Args:
            event: Start event dictionary
        """
        call_id = event["call_id"]
        parent_id = event.get("parent_call_id")
        event_type = event["type"]

        # Determine span type from event type
        if event_type == "module_start":
            span_type = "module"
            name = event.get("module_name", "UnknownModule")
        elif event_type == "lm_start":
            span_type = "lm"
            name = f"LM({event.get('model', 'unknown')})"
        elif event_type == "tool_start":
            span_type = "tool"
            name = f"Tool({event.get('tool_name', 'unknown')})"
        elif "adapter" in event_type:
            span_type = "adapter"
            operation = "format" if "format" in event_type else "parse"
            name = f"Adapter.{operation}({event.get('adapter_type', 'unknown')})"
        else:
            span_type = "unknown"
            name = "Unknown"

        # Create span entry
        span = {
            "call_id": call_id,
            "parent_call_id": parent_id,
            "type": span_type,
            "name": name,
            "depth": event.get("depth", 0),
            "start_time": event.get("timestamp"),
            "end_time": None,
            "duration_ms": None,
            "inputs": event.get("inputs"),
            "outputs": None,
            "token_usage": None,
            "success": None,
            "error": None,
            "children": [],
            "attributes": event.get("attributes", {}),
        }

        # Add additional metadata based on span type
        if span_type == "lm":
            span["model"] = event.get("model")
            span["model_type"] = event.get("model_type")
            span["lm_config"] = event.get("lm_config")
            span["messages"] = event.get("messages")
        elif span_type == "tool":
            span["description"] = event.get("description")
            span["args_schema"] = event.get("args_schema")

        self.spans[call_id] = span

        # Track root-level calls
        if parent_id is None:
            self.root_call_ids.append(call_id)
        else:
            # Add to parent's children list
            if parent_id in self.spans:
                self.spans[parent_id]["children"].append(call_id)

    def _handle_end_event(self, event: dict[str, Any]):
        """Process an end event and update span.

        Args:
            event: End event dictionary
        """
        call_id = event["call_id"]

        if call_id not in self.spans:
            # Create a minimal span if start event was missed
            self.spans[call_id] = {
                "call_id": call_id,
                "type": "unknown",
                "name": "Unknown",
            }

        span = self.spans[call_id]
        span["end_time"] = event.get("timestamp")
        span["duration_ms"] = event.get("duration_ms")
        span["outputs"] = event.get("outputs")
        span["success"] = event.get("success")
        span["error"] = event.get("error")

        # Update token usage if present
        if event.get("token_usage"):
            span["token_usage"] = event["token_usage"]

    def build(self) -> dict[str, Any]:
        """Build and return the complete hierarchical trace.

        Returns:
            Dictionary containing trace_id, root spans, and aggregated metrics
        """
        # Calculate aggregate token usage across all spans
        total_tokens = self._aggregate_token_usage()

        # Build hierarchical structure
        root_spans = [self.spans[call_id] for call_id in self.root_call_ids if call_id in self.spans]

        return {
            "trace_id": self.trace_id,
            "root_call_ids": self.root_call_ids,
            "spans": list(self.spans.values()),
            "token_usage": total_tokens,
            "span_count": len(self.spans),
        }

    def _aggregate_token_usage(self) -> dict[str, Any]:
        """Aggregate token usage across all spans.

        Returns:
            Dictionary with total and per-model token counts
        """
        total = {"total_input_tokens": 0, "total_output_tokens": 0, "by_model": {}}

        for span in self.spans.values():
            token_usage = span.get("token_usage")
            if not token_usage:
                continue

            # Handle module-level aggregated usage
            if "by_model" in token_usage:
                total["total_input_tokens"] += token_usage.get("total_input_tokens", 0)
                total["total_output_tokens"] += token_usage.get("total_output_tokens", 0)

                for model, usage in token_usage["by_model"].items():
                    if model not in total["by_model"]:
                        total["by_model"][model] = {"input": 0, "output": 0}
                    total["by_model"][model]["input"] += usage.get("input", 0)
                    total["by_model"][model]["output"] += usage.get("output", 0)

            # Handle individual LM call usage
            elif "input_tokens" in token_usage:
                model = span.get("model", "unknown")
                total["total_input_tokens"] += token_usage.get("input_tokens", 0)
                total["total_output_tokens"] += token_usage.get("output_tokens", 0)

                if model not in total["by_model"]:
                    total["by_model"][model] = {"input": 0, "output": 0}
                total["by_model"][model]["input"] += token_usage.get("input_tokens", 0)
                total["by_model"][model]["output"] += token_usage.get("output_tokens", 0)

        return total if total["total_input_tokens"] > 0 or total["total_output_tokens"] > 0 else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize trace to dictionary for JSON logging.

        Returns:
            Complete trace as dictionary
        """
        return self.build()
