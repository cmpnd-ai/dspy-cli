"""Dynamic route generation for DSPy programs."""

import base64
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import dspy
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, create_model

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.server.logging import log_inference

logger = logging.getLogger(__name__)


def _convert_dspy_types(inputs: Dict[str, Any], signature) -> Dict[str, Any]:
    """Convert string inputs to DSPy types based on signature.

    For fields with dspy types (Image, Audio, etc.), converts string values
    (URLs or data URIs) to proper dspy objects.

    Args:
        inputs: Dictionary of input values from the request
        signature: DSPy signature with type information

    Returns:
        Dictionary with converted values
    """
    if not signature:
        return inputs

    converted = {}
    for field_name, value in inputs.items():
        if field_name not in signature.input_fields:
            # Pass through unknown fields
            converted[field_name] = value
            continue

        field_info = signature.input_fields[field_name]
        field_type = field_info.annotation if hasattr(field_info, 'annotation') else None

        # Check if field type is a dspy type (from dspy module)
        if field_type and hasattr(field_type, '__module__') and field_type.__module__.startswith('dspy'):
            # Convert string/dict to dspy type
            try:
                if isinstance(value, str) or isinstance(value, dict):
                    converted[field_name] = field_type(value)
                else:
                    # Already the right type or not convertible
                    converted[field_name] = value
            except Exception as e:
                logger.warning(f"Failed to convert {field_name} to {field_type.__name__}: {e}")
                # Pass through unconverted on error
                converted[field_name] = value
        else:
            # Not a dspy type, pass through
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
    # Create img directory if it doesn't exist
    img_dir = logs_dir / "img"
    img_dir.mkdir(exist_ok=True, parents=True)

    # Generate timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Determine file extension and decode data
    if image_data.startswith('data:'):
        # Parse data URI: data:image/png;base64,iVBORw0KG...
        try:
            # Extract mime type and data
            header, data = image_data.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0]

            # Determine extension from mime type
            ext_map = {
                'image/png': 'png',
                'image/jpeg': 'jpg',
                'image/jpg': 'jpg',
                'image/gif': 'gif',
                'image/webp': 'webp',
                'image/svg+xml': 'svg'
            }
            ext = ext_map.get(mime_type, 'png')

            # Decode base64 data
            if 'base64' in header:
                image_bytes = base64.b64decode(data)
            else:
                # Plain data URI (rare)
                image_bytes = data.encode('utf-8')

            # Save to file
            filename = f"{program_name}_{timestamp}_{field_name}.{ext}"
            filepath = img_dir / filename

            with open(filepath, 'wb') as f:
                f.write(image_bytes)

            return f"img/{filename}"

        except Exception as e:
            logger.error(f"Failed to save data URI image: {e}")
            # Return the original data URI truncated for logging
            return f"data:[error saving image: {str(e)[:50]}]"
    else:
        # It's a URL - just return it as-is
        # (We could optionally download and save, but URLs are already compact)
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
    # Handle dspy.Image objects
    if hasattr(data, '__class__') and data.__class__.__name__ == 'Image' and \
       hasattr(data.__class__, '__module__') and data.__class__.__module__.startswith('dspy'):
        # Extract the image URL/data URI from the Image object
        # dspy.Image stores the data in a 'url' attribute
        image_data = getattr(data, 'url', None) or str(data)
        field_name = field_prefix or 'image'
        return _save_image(image_data, logs_dir, program_name, field_name)

    # Handle dictionaries
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

    # Handle lists
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

    # Handle other dspy types (future-proof)
    elif hasattr(data, '__class__') and hasattr(data.__class__, '__module__') and \
         data.__class__.__module__.startswith('dspy'):
        # For other dspy types, try to convert to dict or string
        if hasattr(data, 'toDict'):
            return _serialize_for_logging(data.toDict(), logs_dir, program_name, field_prefix)
        elif hasattr(data, '__dict__'):
            return _serialize_for_logging(vars(data), logs_dir, program_name, field_prefix)
        else:
            return str(data)

    # All other types pass through (str, int, bool, etc.)
    else:
        return data


def create_program_routes(
    app: FastAPI,
    module: DiscoveredModule,
    lm: dspy.LM,
    model_config: Dict,
    config: Dict
):
    """Create API routes for a DSPy program.

    Args:
        app: FastAPI application
        module: Discovered module information
        lm: Language model instance for this program
        model_config: Model configuration for this program
        config: Full configuration dictionary
    """
    program_name = module.name
    model_name = model_config.get("model", "unknown")

    # Instantiate the module once during route creation
    instance = module.instantiate()

    # Create request/response models based on signature if available
    if module.signature:
        try:
            request_model = _create_request_model(module)
            response_model = _create_response_model(module)
        except Exception as e:
            logger.warning(f"Could not create models for {program_name}: {e}")
            request_model = Dict[str, Any]
            response_model = Dict[str, Any]
    else:
        # Fallback to generic dict models
        request_model = Dict[str, Any]
        response_model = Dict[str, Any]

    # Create POST /{program} endpoint
    @app.post(f"/{program_name}", response_model=response_model)
    async def run_program(request: request_model):
        """Execute the DSPy program with given inputs."""
        start_time = time.time()

        try:
            # Convert request to dict if it's a Pydantic model
            if isinstance(request, BaseModel):
                inputs = request.model_dump()
            else:
                inputs = request

            # Convert dspy types (Image, Audio, etc.) from strings to objects
            inputs = _convert_dspy_types(inputs, module.signature)

            # Execute the program with the program-specific LM via context
            logger.info(f"Executing {program_name} with inputs: {inputs}")
            with dspy.context(lm=lm):
                result = instance(**inputs)

            # Convert result to dict
            if isinstance(result, dspy.Prediction):
                output = result.toDict()
            elif hasattr(result, '__dict__'):
                output = vars(result)
            else:
                output = {"result": str(result)}

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Serialize inputs and outputs for logging (extract images to files)
            serialized_inputs = _serialize_for_logging(inputs, app.state.logs_dir, program_name)
            serialized_outputs = _serialize_for_logging(output, app.state.logs_dir, program_name)

            # Log the inference trace
            log_inference(
                logs_dir=app.state.logs_dir,
                program_name=program_name,
                model=model_name,
                inputs=serialized_inputs,
                outputs=serialized_outputs,
                duration_ms=duration_ms
            )

            logger.info(f"Program {program_name} completed successfully. Response: {output}")
            return output

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Serialize inputs for logging (if they exist)
            raw_inputs = inputs if 'inputs' in locals() else {}
            serialized_inputs = _serialize_for_logging(raw_inputs, app.state.logs_dir, program_name)

            # Log the failed inference
            log_inference(
                logs_dir=app.state.logs_dir,
                program_name=program_name,
                model=model_name,
                inputs=serialized_inputs,
                outputs={},
                duration_ms=duration_ms,
                error=str(e)
            )

            logger.error(f"Error executing {program_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


def _create_request_model(module: DiscoveredModule) -> type:
    """Create a Pydantic model for request validation based on signature.

    Args:
        module: Discovered module with signature

    Returns:
        Pydantic model class
    """
    if not module.signature:
        return Dict[str, Any]

    # Get input fields from signature
    fields = {}
    for field_name, field_info in module.signature.input_fields.items():
        # Get the type annotation
        field_type = field_info.annotation if hasattr(field_info, 'annotation') else str

        # For dspy types (Image, Audio, etc.), accept strings in the API
        # They'll be converted to proper dspy objects before execution
        if hasattr(field_type, '__module__') and field_type.__module__.startswith('dspy'):
            field_type = str

        # Check if field is Optional by checking if it's a Union with None
        import typing
        default_value = ...  # Required by default

        # Check if type is Optional (Union with None)
        origin = typing.get_origin(field_type)
        if origin is typing.Union:
            args = typing.get_args(field_type)
            if type(None) in args:
                default_value = None

        # Add to fields dict
        fields[field_name] = (field_type, default_value)

    # Create dynamic Pydantic model
    model_name = f"{module.name}Request"
    return create_model(model_name, **fields)


def _create_response_model(module: DiscoveredModule) -> type:
    """Create a Pydantic model for response based on signature.

    Args:
        module: Discovered module with signature

    Returns:
        Pydantic model class
    """
    if not module.signature:
        return Dict[str, Any]

    # Get output fields from signature
    fields = {}
    for field_name, field_info in module.signature.output_fields.items():
        # Get the type annotation
        field_type = field_info.annotation if hasattr(field_info, 'annotation') else str

        # Add to fields dict
        fields[field_name] = (field_type, ...)

    # Create dynamic Pydantic model
    model_name = f"{module.name}Response"
    return create_model(model_name, **fields)
