"""Dynamic route generation for DSPy programs."""

import logging
from typing import Any, Dict

import dspy
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, create_model

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.server.execution import _convert_dspy_types, execute_pipeline

logger = logging.getLogger(__name__)


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

    # Create request/response models based on forward types
    if module.is_forward_typed:
        try:
            request_model = _create_request_model_from_forward(module)
            response_model = _create_response_model_from_forward(module)
        except Exception as e:
            logger.warning(f"Could not create models from forward types for {program_name}: {e}")
            request_model = Dict[str, Any]
            response_model = Dict[str, Any]
    else:
        # No typed forward method - use generic dict models (no validation)
        logger.warning(f"Module {program_name} does not have typed forward() method - API will have no validation")
        request_model = Dict[str, Any]
        response_model = Dict[str, Any]

    # Create POST /{program} endpoint
    @app.post(f"/{program_name}", response_model=response_model)
    async def run_program(request: request_model):
        """Execute the DSPy program with given inputs."""
        try:
            # Convert request to dict if it's a Pydantic model
            if isinstance(request, BaseModel):
                inputs = request.model_dump()
            else:
                inputs = request

            # Convert dspy types (Image, Audio, etc.) from strings to objects
            inputs = _convert_dspy_types(inputs, module)

            # Instantiate module per call to avoid shared state across concurrent requests
            instance = module.instantiate()

            # Execute via shared pipeline executor
            output = await execute_pipeline(
                module=module,
                instance=instance,
                lm=lm,
                model_name=model_name,
                program_name=program_name,
                inputs=inputs,
                logs_dir=app.state.logs_dir,
            )

            return output

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


def _create_request_model_from_forward(module: DiscoveredModule) -> type:
    """Create a Pydantic model for request validation based on forward() types.

    Args:
        module: Discovered module with forward type information

    Returns:
        Pydantic model class
    """
    if not module.forward_input_fields:
        return Dict[str, Any]

    # Get input fields from forward types
    import typing
    fields = {}
    for field_name, field_info in module.forward_input_fields.items():
        # Get the type annotation from the stored info
        field_type = field_info.get("annotation", str)

        # For dspy types (Image, Audio, etc.), accept strings in the API
        if hasattr(field_type, '__module__') and field_type.__module__.startswith('dspy'):
            field_type = str

        # Check if field is Optional (Union with None)
        default_value = ...  # Required by default
        origin = typing.get_origin(field_type)
        if origin is typing.Union:
            args = typing.get_args(field_type)
            if type(None) in args:
                # It's Optional - make it not required
                default_value = None

        fields[field_name] = (field_type, default_value)

    # Create dynamic Pydantic model
    model_name = f"{module.name}Request"
    return create_model(model_name, **fields)


def _create_response_model_from_forward(module: DiscoveredModule) -> type:
    """Create a Pydantic model for response based on forward() return type.

    Args:
        module: Discovered module with forward type information

    Returns:
        Pydantic model class or Dict[str, Any] for dspy.Prediction
    """
    # If forward_output_fields is None or empty (e.g., dspy.Prediction), use generic dict
    if not module.forward_output_fields:
        return Dict[str, Any]

    # Get output fields from forward return type (TypedDict, dataclass, etc.)
    fields = {}
    for field_name, field_info in module.forward_output_fields.items():
        # Get the type annotation from the stored info
        field_type = field_info.get("annotation", str)

        # Add to fields dict
        fields[field_name] = (field_type, ...)

    # Create dynamic Pydantic model
    model_name = f"{module.name}Response"
    return create_model(model_name, **fields)
