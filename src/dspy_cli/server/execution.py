"""Shared pipeline execution logic for HTTP, MCP, and gateways."""

import base64
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import dspy

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.server.logging import log_inference

logger = logging.getLogger(__name__)


def _extract_lm_metrics(lm: dspy.LM, history_start_idx: int) -> Dict[str, Any]:
    """Extract metrics from LM history entries created during a program call.

    Args:
        lm: The language model instance
        history_start_idx: Index in lm.history where this call's entries start

    Returns:
        Dictionary with tokens, cost_usd, and lm_calls breakdown
    """
    if not hasattr(lm, 'history') or not lm.history:
        return {"tokens": None, "cost_usd": None, "lm_calls": None}

    new_entries = lm.history[history_start_idx:]
    if not new_entries:
        return {"tokens": None, "cost_usd": None, "lm_calls": None}

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    has_cost = False
    lm_calls: List[Dict[str, Any]] = []

    for entry in new_entries:
        usage = entry.get("usage", {})
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", 0) or 0
            completion = usage.get("completion_tokens", 0) or 0
            total_prompt_tokens += prompt
            total_completion_tokens += completion

        cost = entry.get("cost")
        if cost is not None:
            total_cost += cost
            has_cost = True

        lm_calls.append({
            "model": entry.get("model", "unknown"),
            "timestamp": entry.get("timestamp"),
            "prompt_tokens": usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            "completion_tokens": usage.get("completion_tokens") if isinstance(usage, dict) else None,
            "cost_usd": cost,
        })

    tokens = {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
    }

    return {
        "tokens": tokens if total_prompt_tokens > 0 or total_completion_tokens > 0 else None,
        "cost_usd": total_cost if has_cost else None,
        "lm_calls": lm_calls if lm_calls else None,
    }


def _convert_dspy_types(inputs: Dict[str, Any], module: DiscoveredModule) -> Dict[str, Any]:
    """Convert string inputs to DSPy types based on forward type annotations.

    For fields with dspy types (Image, Audio, etc.), converts string values
    (URLs or data URIs) to proper dspy objects.

    Args:
        inputs: Dictionary of input values from the request
        module: DiscoveredModule with forward type information

    Returns:
        Dictionary with converted values
    """
    if not module.is_forward_typed or not module.forward_input_fields:
        return inputs

    converted = {}
    for field_name, value in inputs.items():
        if field_name not in module.forward_input_fields:
            converted[field_name] = value
            continue

        field_info = module.forward_input_fields[field_name]
        field_type = field_info.get('annotation')

        if field_type and hasattr(field_type, '__module__') and field_type.__module__.startswith('dspy'):
            try:
                if isinstance(value, str) or isinstance(value, dict):
                    converted[field_name] = field_type(value)
                else:
                    converted[field_name] = value
            except Exception as e:
                logger.warning(f"Failed to convert {field_name} to {field_type.__name__}: {e}")
                converted[field_name] = value
        else:
            converted[field_name] = value

    return converted


def _save_image(image_data: str, logs_dir: Path, program_name: str, field_name: str) -> str:
    """Save an image to disk and return the relative path.

    Args:
        image_data: Image data (data URI or URL)
        logs_dir: Base logs directory
        program_name: Name of the program
        field_name: Name of the input/output field

    Returns:
        Relative path to saved image (e.g., "img/program_timestamp_field.png")
    """
    img_dir = logs_dir / "img"
    img_dir.mkdir(exist_ok=True, parents=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    if image_data.startswith('data:'):
        try:
            header, data = image_data.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0]

            ext_map = {
                'image/png': 'png',
                'image/jpeg': 'jpg',
                'image/jpg': 'jpg',
                'image/gif': 'gif',
                'image/webp': 'webp',
                'image/svg+xml': 'svg'
            }
            ext = ext_map.get(mime_type, 'png')

            if 'base64' in header:
                image_bytes = base64.b64decode(data)
            else:
                image_bytes = data.encode('utf-8')

            filename = f"{program_name}_{timestamp}_{field_name}.{ext}"
            filepath = img_dir / filename

            with open(filepath, 'wb') as f:
                f.write(image_bytes)

            return f"img/{filename}"

        except Exception as e:
            logger.error(f"Failed to save data URI image: {e}")
            return f"data:[error saving image: {str(e)[:50]}]"
    else:
        return image_data


def _serialize_for_logging(data: Any, logs_dir: Path, program_name: str, field_prefix: str = "") -> Any:
    """Recursively serialize data for JSON logging, extracting images to files.

    Args:
        data: Data to serialize (can be dict, list, dspy.Image, etc.)
        logs_dir: Base logs directory
        program_name: Name of the program
        field_prefix: Prefix for field names (for nested structures)

    Returns:
        Serialized data with dspy.Image objects replaced by file paths
    """
    if hasattr(data, '__class__') and data.__class__.__name__ == 'Image' and \
       hasattr(data.__class__, '__module__') and data.__class__.__module__.startswith('dspy'):
        image_data = getattr(data, 'url', None) or str(data)
        field_name = field_prefix or 'image'
        return _save_image(image_data, logs_dir, program_name, field_name)

    elif isinstance(data, dict):
        return {
            key: _serialize_for_logging(
                value,
                logs_dir,
                program_name,
                field_prefix=f"{field_prefix}_{key}" if field_prefix else key
            )
            for key, value in data.items()
        }

    elif isinstance(data, list):
        return [
            _serialize_for_logging(
                item,
                logs_dir,
                program_name,
                field_prefix=f"{field_prefix}_{i}" if field_prefix else f"item_{i}"
            )
            for i, item in enumerate(data)
        ]

    elif hasattr(data, '__class__') and hasattr(data.__class__, '__module__') and \
         data.__class__.__module__.startswith('dspy'):
        if hasattr(data, 'toDict'):
            return _serialize_for_logging(data.toDict(), logs_dir, program_name, field_prefix)
        elif hasattr(data, '__dict__'):
            return _serialize_for_logging(vars(data), logs_dir, program_name, field_prefix)
        else:
            return str(data)

    else:
        return data


def _normalize_output(result: Any, module: DiscoveredModule) -> Dict[str, Any]:
    """Normalize any DSPy result into a dict for HTTP/MCP/gateways.

    Args:
        result: The result from a DSPy module execution
        module: The DiscoveredModule that produced the result

    Returns:
        Dictionary representation of the result
    """
    if isinstance(result, dspy.Prediction):
        return result.toDict()
    elif hasattr(result, '__dict__'):
        return vars(result)
    elif isinstance(result, dict):
        return result
    else:
        if module.is_forward_typed and module.forward_output_fields:
            field_names = list(module.forward_output_fields.keys())
            if len(field_names) == 1:
                return {field_names[0]: result}
        return {"result": result}


async def execute_pipeline(
    *,
    module: DiscoveredModule,
    instance: dspy.Module,
    lm: dspy.LM,
    model_name: str,
    program_name: str,
    inputs: Dict[str, Any],
    logs_dir: Path,
) -> Dict[str, Any]:
    """Run a DSPy module with its own LM copy, log metrics and I/O, and return output dict.

    This is the shared execution logic used by HTTP routes, MCP, and gateways.

    Args:
        module: DiscoveredModule metadata
        instance: Instantiated DSPy module
        lm: Language model instance (will be copied for this request)
        model_name: Model name for logging
        program_name: Program name for logging
        inputs: Input dictionary (already converted via _convert_dspy_types)
        logs_dir: Directory for log files

    Returns:
        Dictionary of output values

    Raises:
        The original exception on failure after logging.
    """
    start_time = time.time()
    request_lm = lm.copy()

    try:
        logger.info(f"Executing {program_name} with inputs: {inputs}")

        with dspy.context(lm=request_lm):
            if hasattr(instance, 'aforward'):
                result = await instance.acall(**inputs)
            else:
                result = instance(**inputs)

        output = _normalize_output(result, module)
        duration_ms = (time.time() - start_time) * 1000
        metrics = _extract_lm_metrics(request_lm, 0)

        serialized_inputs = _serialize_for_logging(inputs, logs_dir, program_name)
        serialized_outputs = _serialize_for_logging(output, logs_dir, program_name)

        log_inference(
            logs_dir=logs_dir,
            program_name=program_name,
            model=model_name,
            inputs=serialized_inputs,
            outputs=serialized_outputs,
            duration_ms=duration_ms,
            tokens=metrics["tokens"],
            cost_usd=metrics["cost_usd"],
            lm_calls=metrics["lm_calls"],
        )

        logger.info(f"Program {program_name} completed successfully.")
        return output

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics = _extract_lm_metrics(request_lm, 0)

        try:
            serialized_inputs = _serialize_for_logging(inputs, logs_dir, program_name)
        except Exception:
            serialized_inputs = {}

        log_inference(
            logs_dir=logs_dir,
            program_name=program_name,
            model=model_name,
            inputs=serialized_inputs,
            outputs={},
            duration_ms=duration_ms,
            error=str(e),
            tokens=metrics["tokens"],
            cost_usd=metrics["cost_usd"],
            lm_calls=metrics["lm_calls"],
        )

        logger.error(f"Error executing {program_name}: {e}", exc_info=True)
        raise


async def execute_pipeline_batch(
    *,
    module: DiscoveredModule,
    instance: dspy.Module,
    lm: dspy.LM,
    model_name: str,
    program_name: str,
    inputs_list: List[Dict[str, Any]],
    logs_dir: Path,
    num_threads: Optional[int] = None,
    max_errors: Optional[int] = None,
) -> List[Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Exception]]]:
    """Run a DSPy module in batch mode using module.batch().

    This processes multiple inputs in parallel using DSPy's built-in
    batch processing with thread pooling.

    Args:
        module: DiscoveredModule metadata
        instance: Instantiated DSPy module
        lm: Language model instance
        model_name: Model name for logging
        program_name: Program name for logging
        inputs_list: List of raw input dictionaries (may contain _meta)
        logs_dir: Directory for log files
        num_threads: Number of threads for batch (None = DSPy default)
        max_errors: Maximum errors before stopping (None = no limit)

    Returns:
        List of tuples: (raw_inputs, output_dict or None, error or None)
    """
    start_time = time.time()
    request_lm = lm.copy()

    prepared_inputs = []
    for raw_inputs in inputs_list:
        pipeline_inputs = {k: v for k, v in raw_inputs.items() if not k.startswith("_")}
        converted = _convert_dspy_types(pipeline_inputs, module)
        prepared_inputs.append((raw_inputs, converted))

    examples = [
        dspy.Example(**converted).with_inputs(*converted.keys())
        for _, converted in prepared_inputs
    ]

    logger.info(
        f"Batch executing {program_name} with {len(examples)} inputs "
        f"(threads={num_threads or 'default'})"
    )

    results: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Exception]]] = []

    try:
        with dspy.context(lm=request_lm):
            batch_kwargs = {
                "return_failed_examples": True,
                "provide_traceback": True,
            }
            if num_threads is not None:
                batch_kwargs["num_threads"] = num_threads
            if max_errors is not None:
                batch_kwargs["max_errors"] = max_errors

            batch_result = instance.batch(examples, **batch_kwargs)

            if isinstance(batch_result, tuple) and len(batch_result) == 3:
                successful, failed_examples, exceptions = batch_result
            else:
                successful = batch_result
                failed_examples = []
                exceptions = []

        duration_ms = (time.time() - start_time) * 1000

        failed_map = {}
        used_indices: set[int] = set()
        for i, (failed_ex, exc) in enumerate(zip(failed_examples, exceptions)):
            for j, (raw_inputs, converted) in enumerate(prepared_inputs):
                if j not in used_indices and _examples_match(failed_ex, converted):
                    failed_map[j] = exc
                    used_indices.add(j)
                    break

        success_idx = 0
        for i, (raw_inputs, converted) in enumerate(prepared_inputs):
            if i in failed_map:
                results.append((raw_inputs, None, failed_map[i]))

                try:
                    serialized_inputs = _serialize_for_logging(converted, logs_dir, program_name)
                except Exception:
                    serialized_inputs = {}

                log_inference(
                    logs_dir=logs_dir,
                    program_name=program_name,
                    model=model_name,
                    inputs=serialized_inputs,
                    outputs={},
                    duration_ms=0,
                    error=str(failed_map[i]),
                    tokens=None,
                    cost_usd=None,
                    lm_calls=None,
                )
            else:
                if success_idx < len(successful):
                    result = successful[success_idx]
                    output = _normalize_output(result, module)
                    results.append((raw_inputs, output, None))

                    try:
                        serialized_inputs = _serialize_for_logging(converted, logs_dir, program_name)
                        serialized_outputs = _serialize_for_logging(output, logs_dir, program_name)
                    except Exception:
                        serialized_inputs = {}
                        serialized_outputs = {}

                    log_inference(
                        logs_dir=logs_dir,
                        program_name=program_name,
                        model=model_name,
                        inputs=serialized_inputs,
                        outputs=serialized_outputs,
                        duration_ms=duration_ms / len(inputs_list),
                        tokens=None,
                        cost_usd=None,
                        lm_calls=None,
                    )
                    success_idx += 1

        logger.info(
            f"Batch {program_name} completed: {len(successful)} succeeded, "
            f"{len(failed_examples)} failed in {duration_ms:.0f}ms"
        )

    except Exception as e:
        logger.error(f"Batch execution error for {program_name}: {e}", exc_info=True)
        for raw_inputs, _ in prepared_inputs:
            results.append((raw_inputs, None, e))

    return results


def _examples_match(example: dspy.Example, inputs: Dict[str, Any]) -> bool:
    """Check if a DSPy Example matches the given inputs dict."""
    try:
        for key, value in inputs.items():
            if getattr(example, key, None) != value:
                return False
        return True
    except Exception:
        return False
