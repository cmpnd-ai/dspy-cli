"""Utilities for OpenAPI spec generation and management."""

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI


def generate_openapi_spec(app: FastAPI) -> dict[str, Any]:
    """Generate OpenAPI specification from FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        OpenAPI specification as a dictionary
    """
    return app.openapi()


def save_openapi_spec(
    spec: dict[str, Any],
    output_path: Path,
    format: str = "json"
) -> None:
    """Save OpenAPI specification to file.

    Args:
        spec: OpenAPI specification dictionary
        output_path: Path to save the spec file
        format: Output format - 'json' or 'yaml' (default: json)

    Raises:
        ValueError: If format is not 'json' or 'yaml'
    """
    if format not in ["json", "yaml"]:
        raise ValueError(f"Invalid format: {format}. Must be 'json' or 'yaml'")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        with open(output_path, "w") as f:
            json.dump(spec, f, indent=2)
    else:  # yaml
        with open(output_path, "w") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)


def enhance_openapi_metadata(
    app: FastAPI,
    title: str | None = None,
    description: str | None = None,
    version: str | None = None,
    servers: list[dict[str, str]] | None = None,
    extensions: dict[str, Any] | None = None
) -> None:
    """Enhance FastAPI app's OpenAPI metadata.

    Args:
        app: FastAPI application instance
        title: Custom title for the API
        description: Custom description for the API
        version: Custom version for the API
        servers: List of server configurations
        extensions: Custom OpenAPI extensions (x-* fields)
    """
    if title:
        app.title = title
    if description:
        app.description = description
    if version:
        app.version = version

    # Custom openapi function to add extensions and servers
    original_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = original_openapi()

        # Add servers if provided
        if servers:
            openapi_schema["servers"] = servers

        # Add custom extensions to info section
        if extensions:
            for key, value in extensions.items():
                # Ensure extension keys start with x-
                ext_key = key if key.startswith("x-") else f"x-{key}"
                openapi_schema["info"][ext_key] = value

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi


def create_openapi_extensions(
    config: dict[str, Any],
    discovered_modules: list[Any],
    program_models: dict[str, str] | None = None
) -> dict[str, Any]:
    """Create DSPy-specific OpenAPI extensions.

    Args:
        config: DSPy configuration dictionary
        discovered_modules: List of discovered DSPy modules
        program_models: Mapping of program names to model names

    Returns:
        Dictionary of OpenAPI extensions
    """
    extensions = {}

    # Add DSPy metadata
    extensions["x-dspy-config"] = {
        "default_model": config.get("default_model"),
        "programs_count": len(discovered_modules)
    }

    # Add program information
    if discovered_modules:
        extensions["x-dspy-programs"] = [
            {
                "name": module.name,
                "module_path": module.module_path,
                "is_forward_typed": module.is_forward_typed
            }
            for module in discovered_modules
        ]

    # Add program-to-model mappings
    if program_models:
        extensions["x-dspy-program-models"] = program_models

    return extensions
