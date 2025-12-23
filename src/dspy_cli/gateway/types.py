"""Type definitions for gateways."""

from typing import Any, Dict

PipelineOutput = Dict[str, Any]
"""Output from a DSPy pipeline after normalization via _normalize_output.

This is always a dictionary mapping field names to their values,
regardless of the original return type from the DSPy module.
"""

PipelineInputs = Dict[str, Any]
"""Input kwargs for a DSPy pipeline's forward() method.

Should not contain _-prefixed keys like _meta; those are stripped
before passing to the pipeline.
"""
