"""Dynamic route generation for DSPy programs."""

import logging
from typing import Any, Dict

import dspy
from fastapi import FastAPI, HTTPException
from pydantic import create_model

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.discovery.gateway_finder import get_gateway_for_module
from dspy_cli.gateway import APIGateway
from dspy_cli.server.execution import _convert_dspy_types, execute_pipeline

logger = logging.getLogger(__name__)


def create_program_routes(
    app: FastAPI,
    module: DiscoveredModule,
    lm: dspy.LM,
    model_config: Dict,
    config: Dict,
    gateway: APIGateway | None = None,
):
    """Create API routes for a DSPy program.

    Args:
        app: FastAPI application
        module: Discovered module information
        lm: Language model instance for this program
        model_config: Model configuration for this program
        config: Full configuration dictionary
        gateway: Optional APIGateway instance (if None, will be discovered)
    """
    program_name = module.name
    model_name = model_config.get("model", "unknown")

    if gateway is None:
        gateway = get_gateway_for_module(module)
        if not isinstance(gateway, APIGateway):
            logger.warning(f"Module {program_name} has non-API gateway, skipping route creation")
            return

    request_model = gateway.request_model
    response_model = gateway.response_model

    if request_model is None:
        if module.is_forward_typed:
            try:
                request_model = _create_request_model_from_forward(module)
            except Exception as e:
                logger.warning(f"Could not create request model from forward types for {program_name}: {e}")
                request_model = Dict[str, Any]
        else:
            logger.warning(f"Module {program_name} does not have typed forward() method - API will have no validation")
            request_model = Dict[str, Any]

    if response_model is None:
        if module.is_forward_typed:
            try:
                response_model = _create_response_model_from_forward(module)
            except Exception as e:
                logger.warning(f"Could not create response model from forward types for {program_name}: {e}")
                response_model = Dict[str, Any]
        else:
            response_model = Dict[str, Any]

    route_path = gateway.path if gateway.path else f"/{program_name}"

    async def run_program(request: request_model):
        """Execute the DSPy program with given inputs."""
        try:
            pipeline_inputs = gateway.to_pipeline_inputs(request)

            pipeline_inputs = _convert_dspy_types(pipeline_inputs, module)

            instance = module.instantiate()

            output = await execute_pipeline(
                module=module,
                instance=instance,
                lm=lm,
                model_name=model_name,
                program_name=program_name,
                inputs=pipeline_inputs,
                logs_dir=app.state.logs_dir,
            )

            return gateway.from_pipeline_output(output)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Initialize gateway lifecycle
    gateway.setup()
    
    # Register shutdown hook with FastAPI
    if not hasattr(app.state, "_gateway_shutdowns"):
        app.state._gateway_shutdowns = []
    app.state._gateway_shutdowns.append(gateway.shutdown)

    gateway.configure_route(
        app=app,
        route_path=route_path,
        endpoint=run_program,
        response_model=response_model,
    )

    if not gateway.requires_auth:
        if not hasattr(app.state, "public_paths"):
            app.state.public_paths = set()
        app.state.public_paths.add(route_path)


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
