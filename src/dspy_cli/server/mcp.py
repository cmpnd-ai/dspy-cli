"""MCP (Model Context Protocol) integration for DSPy programs."""

import logging
from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel

from dspy_cli.config import get_model_config, get_program_model
from dspy_cli.server.execution import _convert_dspy_types, execute_pipeline
from dspy_cli.server.routes import (
    _create_request_model_from_forward,
    _create_response_model_from_forward,
)

logger = logging.getLogger(__name__)

try:
    from fastmcp import FastMCP
except ImportError:
    logger.warning("fastmcp not installed. MCP support will not be available.")
    FastMCP = None

MCP_DEFAULT_PATH = "/mcp"


def _is_pydantic_model(obj) -> bool:
    """Check if an object is a Pydantic BaseModel class."""
    try:
        return isinstance(obj, type) and issubclass(obj, BaseModel)
    except Exception:
        return False


def create_mcp_server(app: FastAPI) -> "FastMCP":
    """Create an MCP server from the FastAPI app with DSPy program tools.

    Args:
        app: FastAPI application with discovered DSPy modules

    Returns:
        FastMCP server instance with registered tools and resources
    """
    if FastMCP is None:
        raise ImportError("fastmcp is required for MCP support. Install with: pip install fastmcp>=2.0.0")

    mcp_server = FastMCP(name="dspy-cli", version="0.1.0")

    # Register tools: one per discovered DSPy program
    modules = getattr(app.state, "modules", [])
    for module in modules:
        _register_program_tool(mcp_server, app, module)

    # Register resources for program metadata
    _register_resources(mcp_server, app)

    return mcp_server


def _register_program_tool(mcp_server: "FastMCP", app: FastAPI, module):
    """Register a single DSPy program as an MCP tool.

    Args:
        mcp_server: FastMCP server instance
        app: FastAPI application
        module: DiscoveredModule instance
    """
    program_name = module.name

    # Get the program-specific LM from app state
    lm = app.state.program_lms[program_name]
    model_alias = get_program_model(app.state.config, program_name)
    model_config = get_model_config(app.state.config, model_alias)
    model_name = model_config.get("model", "unknown")

    # Create request/response models from forward() types if available
    try:
        RequestModel = _create_request_model_from_forward(module)
        ResponseModel = _create_response_model_from_forward(module)
        has_types = True
    except Exception:
        RequestModel = None
        ResponseModel = None
        has_types = False

    # Create tool execution logic
    async def execute_program(**kwargs) -> Dict[str, Any]:
        """Execute the DSPy program with given parameters."""
        # Validate with request model if available
        if has_types and _is_pydantic_model(RequestModel):
            validated = RequestModel(**kwargs)
            inputs = validated.model_dump()
        else:
            inputs = kwargs

        # Convert dspy types (Image, Audio, etc.)
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

        # Validate response if model available
        if has_types and _is_pydantic_model(ResponseModel):
            validated_output = ResponseModel(**output)
            return validated_output.model_dump()

        return output

    # Register tool with explicit fields if typed, else generic params
    if has_types and _is_pydantic_model(RequestModel):
        # Create a wrapper function with explicit parameters from RequestModel
        import inspect
        from pydantic.fields import PydanticUndefined
        
        # Build keyword-only function parameters from Pydantic model fields
        params = []
        annotations = {}
        
        for field_name, field_info in RequestModel.model_fields.items():
            annotation = field_info.annotation
            
            if field_info.is_required():
                # Required parameter - no default
                params.append(inspect.Parameter(
                    field_name, 
                    inspect.Parameter.KEYWORD_ONLY, 
                    annotation=annotation
                ))
            else:
                # Optional parameter - use actual default or None
                if field_info.default is not PydanticUndefined:
                    default = field_info.default
                elif field_info.default_factory is not None:
                    # Can't represent factory in signature, use None
                    default = None
                else:
                    default = None
                    
                params.append(inspect.Parameter(
                    field_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                    annotation=annotation
                ))
            
            annotations[field_name] = annotation
        
        # Add return annotation
        if _is_pydantic_model(ResponseModel):
            annotations['return'] = ResponseModel
        else:
            annotations['return'] = Dict[str, Any]
        
        # Create signature
        sig = inspect.Signature(params)
        
        # Create wrapper function with proper signature
        async def tool_function(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return await execute_program(**bound.arguments)
        
        tool_function.__signature__ = sig
        tool_function.__annotations__ = annotations
        
        # Register the tool
        mcp_server.tool(name=program_name, description=f"Execute DSPy program: {program_name}")(tool_function)
    else:
        # Fallback to generic params dict
        @mcp_server.tool(name=program_name, description=f"Execute DSPy program: {program_name}")
        async def tool_function(params: Dict[str, Any]) -> Dict[str, Any]:
            return await execute_program(**params)


def _register_resources(mcp_server: "FastMCP", app: FastAPI):
    """Register MCP resources for program metadata.

    Args:
        mcp_server: FastMCP server instance
        app: FastAPI application
    """

    # Resource: List all programs
    @mcp_server.resource("dspy://programs")
    def list_programs() -> Dict[str, Any]:
        """List all available DSPy programs."""
        modules = getattr(app.state, "modules", [])
        programs = []
        for module in modules:
            model_alias = get_program_model(app.state.config, module.name)
            programs.append(
                {
                    "name": module.name,
                    "model": model_alias,
                    "endpoint": f"/{module.name}",
                    "typed": bool(module.is_forward_typed),
                }
            )
        return {"programs": programs}

    # Resource: Individual program schemas
    modules = getattr(app.state, "modules", [])
    for module in modules:

        def make_schema_resource(mod):
            @mcp_server.resource(f"dspy://programs/{mod.name}/schema")
            def program_schema() -> Dict[str, Any]:
                """Get schema for a specific DSPy program."""
                try:
                    RequestModel = _create_request_model_from_forward(mod)
                    ResponseModel = _create_response_model_from_forward(mod)

                    if RequestModel != Dict[str, Any]:
                        req_schema = RequestModel.model_json_schema()
                    else:
                        req_schema = {"type": "object", "additionalProperties": True}

                    if ResponseModel != Dict[str, Any]:
                        res_schema = ResponseModel.model_json_schema()
                    else:
                        res_schema = {"type": "object", "additionalProperties": True}

                except Exception:
                    req_schema = {"type": "object", "additionalProperties": True}
                    res_schema = {"type": "object", "additionalProperties": True}

                return {
                    "name": mod.name,
                    "request_schema": req_schema,
                    "response_schema": res_schema,
                }

            return program_schema

        make_schema_resource(module)


def mount_mcp_http(app: FastAPI, mcp_server: "FastMCP", path: str = "/mcp"):
    """Mount MCP server at a path in the FastAPI app.

    Args:
        app: FastAPI application
        mcp_server: FastMCP server instance
        path: Path to mount MCP server (default: /mcp)
    """
    try:
        from asgi_lifespan import LifespanManager
    except ImportError:
        logger.error("asgi-lifespan is required for MCP support. Install with: pip install asgi-lifespan")
        raise ImportError("asgi-lifespan is required for MCP support. Install with: pip install asgi-lifespan")

    # Create the MCP HTTP app with path="/" so routes are at root of mounted app
    # When mounted at /mcp, the endpoint will be accessible at /mcp
    mcp_asgi_app = mcp_server.http_app(path="/")

    # Mount the MCP ASGI app at the specified path
    app.mount(path, mcp_asgi_app)

    # Manage the MCP sub-app's lifespan explicitly
    # FastAPI/Starlette don't automatically enter the lifespan of mounted sub-apps
    # FastMCP's HTTP server initializes its task group in its lifespan
    async def _start_mcp():
        app.state._mcp_lifespan_manager = LifespanManager(mcp_asgi_app)
        await app.state._mcp_lifespan_manager.__aenter__()
        logger.info("MCP server lifespan started")

    async def _stop_mcp():
        manager = getattr(app.state, "_mcp_lifespan_manager", None)
        if manager is not None:
            await manager.__aexit__(None, None, None)
            logger.info("MCP server lifespan stopped")

    app.add_event_handler("startup", _start_mcp)
    app.add_event_handler("shutdown", _stop_mcp)

    logger.info(f"MCP server mounted at {path} with managed lifespan")
