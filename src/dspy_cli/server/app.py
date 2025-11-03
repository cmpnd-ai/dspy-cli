"""FastAPI application factory."""

import logging
from pathlib import Path
from typing import Dict

import dspy
from fastapi import FastAPI

from dspy_cli.config import get_model_config, get_program_model
from dspy_cli.discovery import discover_modules
from dspy_cli.server.logging import setup_logging
from dspy_cli.server.routes import create_program_routes

logger = logging.getLogger(__name__)


def create_app(
    config: Dict,
    package_path: Path,
    package_name: str,
    logs_dir: Path,
    enable_ui: bool = False
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Loaded configuration dictionary
        package_path: Path to the modules package
        package_name: Python package name for modules
        logs_dir: Directory for log files
        enable_ui: Whether to enable the web UI

    Returns:
        Configured FastAPI application
    """
    # Setup logging
    setup_logging()

    # Create FastAPI app
    app = FastAPI(
        title="DSPy API",
        description="Automatically generated API for DSPy programs",
        version="0.1.0"
    )

    # Store logs directory in app state
    app.state.logs_dir = logs_dir

    # Discover modules
    logger.info(f"Discovering modules in {package_path}")
    modules = discover_modules(package_path, package_name)

    if not modules:
        logger.warning("No DSPy modules discovered!")

    # Configure default model
    default_model_alias = config["models"]["default"]
    default_model_config = get_model_config(config, default_model_alias)
    _configure_dspy_model(default_model_config)

    logger.info(f"Configured default model: {default_model_alias}")

    # Create LM instances for each program and store them
    app.state.program_lms = {}
    for module in modules:
        # Get model for this program (could be overridden)
        model_alias = get_program_model(config, module.name)
        model_config = get_model_config(config, model_alias)

        # Create LM instance for this program
        lm = _create_lm_instance(model_config)
        app.state.program_lms[module.name] = lm

        logger.info(f"Created LM for program: {module.name} (model: {model_alias})")

    # Create routes for each discovered module
    for module in modules:
        # Get the LM instance for this program
        lm = app.state.program_lms[module.name]
        model_alias = get_program_model(config, module.name)
        model_config = get_model_config(config, model_alias)

        create_program_routes(app, module, lm, model_config, config)

        logger.info(f"Registered program: {module.name} (model: {model_alias})")

    # Add programs list endpoint
    @app.get("/programs")
    async def list_programs():
        """List all discovered programs and their schemas."""
        from dspy_cli.discovery.module_finder import get_signature_fields

        programs = []
        for module in modules:
            model_alias = get_program_model(config, module.name)

            program_info = {
                "name": module.name,
                "model": model_alias,
                "endpoint": f"/{module.name}",
            }

            # Add signature information if available
            if module.signature:
                fields = get_signature_fields(module.signature)
                program_info["schema"] = fields

            programs.append(program_info)

        return {"programs": programs}

    # Store modules in app state for access by routes
    app.state.modules = modules
    app.state.config = config

    # Register UI routes if enabled
    if enable_ui:
        from fastapi.staticfiles import StaticFiles
        from dspy_cli.server.ui import create_ui_routes

        # Mount static files
        static_dir = Path(__file__).parent.parent / "templates" / "ui" / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logger.info("Mounted static files for UI")
        else:
            logger.warning(f"Static directory not found: {static_dir}")

        # Create UI routes
        create_ui_routes(app, modules, config, logs_dir)
        logger.info("UI routes registered")

    return app


def _create_lm_instance(model_config: Dict) -> dspy.LM:
    """Create a DSPy LM instance from configuration.

    Args:
        model_config: Model configuration dictionary

    Returns:
        Configured LM instance
    """
    # Extract configuration
    model = model_config.get("model")
    model_type = model_config.get("model_type", "chat")
    temperature = model_config.get("temperature")
    max_tokens = model_config.get("max_tokens")
    api_key = model_config.get("api_key")
    api_base = model_config.get("api_base")

    # Build kwargs
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if api_key is not None:
        kwargs["api_key"] = api_key
    if api_base is not None:
        kwargs["api_base"] = api_base

    # Create and return LM instance
    return dspy.LM(
        model=model,
        model_type=model_type,
        **kwargs
    )


def _configure_dspy_model(model_config: Dict):
    """Configure DSPy with a language model.

    Args:
        model_config: Model configuration dictionary
    """
    # Create LM instance
    lm = _create_lm_instance(model_config)

    # Configure DSPy
    dspy.settings.configure(lm=lm)

    model = model_config.get("model")
    model_type = model_config.get("model_type", "chat")
    api_base = model_config.get("api_base")
    base_info = f" (base: {api_base})" if api_base else ""
    logger.info(f"Configured DSPy with model: {model} (type: {model_type}){base_info}")
