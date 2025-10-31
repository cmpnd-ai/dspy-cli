"""Dynamic route generation for DSPy programs."""

import logging
import time
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

            # Log the inference trace
            log_inference(
                logs_dir=app.state.logs_dir,
                program_name=program_name,
                model=model_name,
                inputs=inputs,
                outputs=output,
                duration_ms=duration_ms
            )

            logger.info(f"Program {program_name} completed successfully. Response: {output}")
            return output

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log the failed inference
            log_inference(
                logs_dir=app.state.logs_dir,
                program_name=program_name,
                model=model_name,
                inputs=inputs if 'inputs' in locals() else {},
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

        # Get description
        description = ""
        if field_info.json_schema_extra:
            description = field_info.json_schema_extra.get("desc", "")

        # Check if field is Optional by checking if it's a Union with None
        import typing
        is_optional = False
        default_value = ...  # Required by default

        # Check if type is Optional (Union with None)
        origin = typing.get_origin(field_type)
        if origin is typing.Union:
            args = typing.get_args(field_type)
            if type(None) in args:
                is_optional = True
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

        # Get description
        description = ""
        if field_info.json_schema_extra:
            description = field_info.json_schema_extra.get("desc", "")

        # Add to fields dict
        fields[field_name] = (field_type, ...)

    # Create dynamic Pydantic model
    model_name = f"{module.name}Response"
    return create_model(model_name, **fields)
