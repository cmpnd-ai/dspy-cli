"""FastAPI application factory with deferred initialization.

The app shell (health endpoints, CORS, auth) is created immediately so the
server port binds fast. Heavy work (module discovery, LM creation, route
registration) is deferred to the ASGI lifespan startup, which runs *after*
the socket is listening. This eliminates false "not listening" warnings from
container orchestrators like Fly.io and Kubernetes.
"""

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import dspy
from dspy_cli.config import get_model_config, get_program_model
from dspy_cli.discovery import discover_modules
from dspy_cli.discovery.gateway_finder import get_gateways_for_module, is_cron_gateway
from dspy_cli.gateway import APIGateway, IdentityGateway
from dspy_cli.server.executor import init_executor, shutdown_executor, DEFAULT_SYNC_WORKERS
from dspy_cli.server.logging import setup_logging
from dspy_cli.server.metrics import get_all_metrics, get_program_metrics_cached
from dspy_cli.server.routes import create_program_routes
from dspy_cli.server.scheduler import GatewayScheduler
from dspy_cli.utils.openapi import enhance_openapi_metadata, create_openapi_extensions

logger = logging.getLogger(__name__)


@dataclass
class _AppInitParams:
    """Parameters stored on app.state for deferred initialization."""
    config: Dict
    package_path: Path
    package_name: str
    logs_dir: Path
    enable_auth: bool
    sync_workers: Optional[int]


def create_app(
    config: Dict,
    package_path: Path,
    package_name: str,
    logs_dir: Path,
    enable_ui: bool = True,
    enable_auth: bool = False,
    sync_workers: int | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Returns a lightweight app shell with health endpoints. Heavy initialization
    (module discovery, LM creation, route registration) is deferred to the
    ASGI lifespan so the server port binds quickly.

    Args:
        config: Loaded configuration dictionary
        package_path: Path to the modules package
        package_name: Python package name for modules
        logs_dir: Directory for log files
        enable_ui: Whether to enable the web UI (always True, kept for compatibility)
        enable_auth: Whether to enable API authentication via DSPY_API_KEY
        sync_workers: Number of threads for sync module execution (overrides config)

    Returns:
        Configured FastAPI application
    """
    setup_logging()

    # Configure default DSPy model synchronously (before async lifespan).
    # dspy.settings.configure() must be called outside async tasks due to DSPy's
    # ownership guard, and it's lightweight (no I/O).
    default_model_alias = config["models"]["default"]
    default_model_config = get_model_config(config, default_model_alias)
    _configure_dspy_model(default_model_config)
    logger.info(f"Configured default model: {default_model_alias}")

    init_params = _AppInitParams(
        config=config,
        package_path=package_path,
        package_name=package_name,
        logs_dir=logs_dir,
        enable_auth=enable_auth,
        sync_workers=sync_workers,
    )

    app = FastAPI(
        title="DSPy API",
        description="Automatically generated API for DSPy programs",
        version="0.1.0",
        lifespan=_make_lifespan(init_params),
    )

    # Pre-init state
    app.state._ready = False
    app.state.modules = []
    app.state.program_lms = {}
    app.state.logs_dir = logs_dir
    app.state.metrics_cache = {}

    # CORS (lightweight, no deferred init needed)
    _setup_cors(app, config)

    # Health endpoints (available as soon as the port binds)
    @app.get("/health/live")
    async def liveness():
        """Liveness probe -- returns 200 if the process is running."""
        return {"status": "alive"}

    @app.get("/health/ready")
    async def readiness():
        """Readiness probe -- returns 200 when all LM instances are initialized."""
        if not app.state._ready:
            return JSONResponse(status_code=503, content={"status": "starting"})
        modules = app.state.modules
        if not modules:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "no modules discovered"})
        missing = [m.name for m in modules if m.name not in app.state.program_lms]
        if missing:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": f"LMs not initialized: {missing}"})
        return {"status": "ready", "programs": len(modules)}

    # Auth middleware (early setup with mutable open_paths so lifespan can add gateway paths)
    if enable_auth:
        _setup_auth_middleware(app)

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_cors(app: FastAPI, config: Dict):
    """Configure CORS middleware (lightweight, runs immediately)."""
    cors_origins: Union[str, List[str], None] = os.environ.get("DSPY_CORS_ORIGINS")
    if cors_origins is None:
        cors_origins = config.get("server", {}).get("cors_origins")

    if cors_origins:
        if cors_origins == "*" or cors_origins == ["*"]:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=False,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            logger.info("CORS enabled for all origins (wildcard mode)")
        else:
            origins = (
                cors_origins
                if isinstance(cors_origins, list)
                else [o.strip() for o in cors_origins.split(",") if o.strip()]
            )
            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            logger.info(f"CORS enabled for origins: {origins}")


def _setup_auth_middleware(app: FastAPI):
    """Set up auth middleware with default open paths.

    The open_paths set is mutable so the lifespan can add gateway public
    paths after module discovery.
    """
    from dspy_cli.server.auth import (
        DEFAULT_OPEN_PATHS,
        AuthMiddleware,
        create_auth_routes,
        generate_token,
        get_api_token,
    )

    token = get_api_token()
    if not token:
        token = generate_token()
        os.environ["DSPY_API_KEY"] = token
        logger.warning("=" * 60)
        logger.warning("DSPY_API_KEY not set. Generated temporary token:")
        logger.warning(f"  {token}")
        logger.warning("Set DSPY_API_KEY as an environment secret for a persistent token.")
        logger.warning("=" * 60)

    auth_router = create_auth_routes(token)
    app.include_router(auth_router)

    # Mutable set -- _deferred_init will add gateway public paths later
    open_paths = set(DEFAULT_OPEN_PATHS)
    app.state._auth_open_paths = open_paths

    app.add_middleware(AuthMiddleware, token=token, open_paths=open_paths)
    logger.info("Authentication enabled")


# ---------------------------------------------------------------------------
# Lifespan & deferred initialization
# ---------------------------------------------------------------------------

def _make_lifespan(params: _AppInitParams):
    """Create the ASGI lifespan context manager.

    Heavy initialization runs here, *after* the server socket is bound.
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # --- Startup (port is already listening at this point) ---
        _deferred_init(app, params)

        # Run any callbacks registered by runner.py (MCP, OpenAPI save, etc.)
        for cb in getattr(app.state, "_on_ready_callbacks", []):
            try:
                cb()
            except Exception as e:
                logger.warning(f"on_ready callback error: {e}")

        scheduler = getattr(app.state, "scheduler", None)
        if scheduler and scheduler.job_count > 0:
            scheduler.start()

        yield

        # --- Shutdown ---
        if scheduler and scheduler.job_count > 0:
            scheduler.shutdown()

        for shutdown_fn in getattr(app.state, "_gateway_shutdowns", []):
            try:
                shutdown_fn()
            except Exception as e:
                logger.warning(f"Gateway shutdown error: {e}")

        shutdown_executor()

    return lifespan


def _deferred_init(app: FastAPI, params: _AppInitParams):
    """Heavy initialization: module discovery, LM creation, route registration.

    Called from the lifespan startup, after the server port is already bound.
    """
    config = params.config

    # Initialize bounded executor for sync module execution
    worker_count = (
        params.sync_workers
        or config.get("server", {}).get("sync_worker_threads")
        or DEFAULT_SYNC_WORKERS
    )
    init_executor(max_workers=worker_count)

    # Discover modules
    logger.info(f"Discovering modules in {params.package_path}")
    modules = discover_modules(params.package_path, params.package_name)

    if not modules:
        logger.warning("No DSPy modules discovered!")

    # Check for duplicate module names
    module_names = [m.name for m in modules]
    duplicates = [name for name in module_names if module_names.count(name) > 1]
    if duplicates:
        duplicate_set = set(duplicates)
        error_msg = f"Error: Duplicate module names found: {', '.join(sorted(duplicate_set))}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Create LM instances for each program (dspy.settings already configured in create_app)
    for module in modules:
        model_alias = get_program_model(config, module.name)
        model_config = get_model_config(config, model_alias)
        lm = _create_lm_instance(model_config)
        app.state.program_lms[module.name] = lm
        logger.info(f"Created LM for program: {module.name} (model: {model_alias})")

    # Initialize scheduler for cron gateways
    scheduler = GatewayScheduler(params.logs_dir)
    app.state.scheduler = scheduler

    # Track registered API paths to detect conflicts
    registered_paths: Dict[str, str] = {}

    # Create routes for each discovered module
    for module in modules:
        lm = app.state.program_lms[module.name]
        model_alias = get_program_model(config, module.name)
        model_config = get_model_config(config, model_alias)
        gateways = get_gateways_for_module(module)

        for gateway in gateways:
            if is_cron_gateway(gateway):
                scheduler.register_cron_gateway(
                    module=module,
                    gateway=gateway,
                    lm=lm,
                    model_name=model_config.get("model", "unknown"),
                )
                logger.info(f"Registered cron gateway: {module.name} ({gateway.__class__.__name__}, schedule: {gateway.schedule})")
            elif isinstance(gateway, APIGateway):
                if gateway.path:
                    route_path = gateway.path
                elif isinstance(gateway, IdentityGateway):
                    route_path = f"/{module.name}"
                else:
                    route_path = f"/{module.name}/{gateway.__class__.__name__}"

                gateway_id = f"{module.name}.{gateway.__class__.__name__}"
                if route_path in registered_paths:
                    existing = registered_paths[route_path]
                    error_msg = (
                        f"Route path conflict: '{route_path}' is used by both "
                        f"{existing} and {gateway_id}. "
                        f"Set explicit 'path' attribute on one of the gateways to resolve."
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                registered_paths[route_path] = gateway_id
                create_program_routes(app, module, lm, model_config, config, gateway=gateway)
                logger.info(f"Registered API gateway: {module.name} ({gateway.__class__.__name__}, path: {route_path}, model: {model_alias})")
            else:
                logger.warning(f"Unknown gateway type for {module.name}: {type(gateway)}")

    # Add programs list endpoint
    @app.get("/programs")
    async def list_programs():
        """List all discovered programs and their schemas."""
        programs = []
        for module in modules:
            model_alias = get_program_model(config, module.name)
            programs.append({
                "name": module.name,
                "model": model_alias,
                "endpoint": f"/{module.name}",
            })
        return {"programs": programs}

    # Add metrics endpoints
    @app.get("/api/metrics")
    async def list_metrics(sort_by: str = "calls", order: str = "desc"):
        """Get aggregated metrics for all programs."""
        program_names = [m.name for m in modules]
        metrics_list = get_all_metrics(
            params.logs_dir,
            program_names,
            app.state.metrics_cache,
            sort_by=sort_by,
            order=order,
        )
        return {"programs": [m.to_dict() for m in metrics_list]}

    @app.get("/api/metrics/{program_name}")
    async def program_metrics(program_name: str):
        """Get detailed metrics for a specific program."""
        if not any(m.name == program_name for m in modules):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Program '{program_name}' not found")

        metrics = get_program_metrics_cached(
            params.logs_dir,
            program_name,
            app.state.metrics_cache,
        )
        return {"metrics": metrics.to_dict()}

    # Store modules and config in app state
    app.state.modules = modules
    app.state.config = config

    # Enhance OpenAPI metadata
    app_id = config.get("app_id", "DSPy API")
    app_description = config.get("description", "Automatically generated API for DSPy programs")
    program_models = {module.name: get_program_model(config, module.name) for module in modules}
    extensions = create_openapi_extensions(config, modules, program_models)
    enhance_openapi_metadata(app, title=app_id, description=app_description, extensions=extensions)
    logger.info("Enhanced OpenAPI metadata with DSPy configuration")

    # Register UI routes
    from fastapi.staticfiles import StaticFiles
    from dspy_cli.server.ui import create_ui_routes

    static_dir = Path(__file__).parent.parent / "templates" / "ui" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info("Mounted static files for UI")
    else:
        logger.warning(f"Static directory not found: {static_dir}")

    create_ui_routes(app, modules, config, params.logs_dir, auth_enabled=params.enable_auth)
    logger.info("UI routes registered")

    # Update auth open paths with gateway public paths discovered during route creation
    if params.enable_auth and hasattr(app.state, "_auth_open_paths"):
        if hasattr(app.state, "public_paths"):
            app.state._auth_open_paths.update(app.state.public_paths)

    # Reset cached OpenAPI schema since routes were added dynamically
    app.openapi_schema = None

    app.state._ready = True
    logger.info("Application initialization complete")


# ---------------------------------------------------------------------------
# LM helpers (unchanged)
# ---------------------------------------------------------------------------

def _create_lm_instance(model_config: Dict) -> dspy.LM:
    """Create a DSPy LM instance from configuration."""
    model = model_config.get("model")
    model_type = model_config.get("model_type", "chat")
    temperature = model_config.get("temperature")
    max_tokens = model_config.get("max_tokens")
    api_key = model_config.get("api_key")
    api_base = model_config.get("api_base")
    cache = model_config.get("cache")

    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if api_key is not None:
        kwargs["api_key"] = api_key
    if api_base is not None:
        kwargs["api_base"] = api_base
    if cache is not None:
        kwargs["cache"] = cache

    return dspy.LM(model=model, model_type=model_type, **kwargs)


def _configure_dspy_model(model_config: Dict):
    """Configure DSPy with a language model."""
    lm = _create_lm_instance(model_config)
    dspy.settings.configure(lm=lm, disable_history=True)

    model = model_config.get("model")
    model_type = model_config.get("model_type", "chat")
    api_base = model_config.get("api_base")
    base_info = f" (base: {api_base})" if api_base else ""
    logger.info(f"Configured DSPy with model: {model} (type: {model_type}){base_info}")
