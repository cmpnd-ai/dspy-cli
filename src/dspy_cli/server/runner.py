"""Server runner module for executing DSPy API server."""

import logging
import os
import sys
from pathlib import Path

import click
import uvicorn

from dspy_cli.config import ConfigError, load_config
from dspy_cli.config.validator import find_package_directory, validate_project_structure
from dspy_cli.server.app import create_app
from dspy_cli.utils.openapi import generate_openapi_spec, save_openapi_spec

logger = logging.getLogger(__name__)

# Constants
MCP_DEFAULT_PATH = "/mcp"
ENV_ENABLE_MCP = "DSPY_CLI_ENABLE_MCP"
ENV_LOGS_DIR = "DSPY_CLI_LOGS_DIR"
ENV_AUTH_ENABLED = "DSPY_CLI_AUTH_ENABLED"


def _maybe_mount_mcp(app, enable: bool, *, path: str = MCP_DEFAULT_PATH, notify=None) -> bool:
    """Mount MCP server if enabled.

    Args:
        app: FastAPI application instance
        enable: Whether to enable MCP
        path: Path to mount MCP server at
        notify: Optional callback for user-facing messages (msg, level) -> None

    Returns:
        True if MCP was successfully mounted, False otherwise
    """
    if not enable:
        return False

    try:
        from dspy_cli.server.mcp import create_mcp_server, mount_mcp_http

        server = create_mcp_server(app)
        mount_mcp_http(app, server, path=path)

        if notify:
            notify(f"✓ MCP server enabled at {path}", level="info")
        else:
            logger.info("MCP server mounted at %s", path)
        return True
    except ImportError as e:
        msg = str(e)
        if notify:
            notify(f"Warning: {msg}", level="warn")
        else:
            logger.warning("Could not enable MCP: %s", msg)
    except Exception as e:
        msg = str(e)
        if notify:
            notify(f"Warning: Could not enable MCP: {msg}", level="warn")
        else:
            logger.error("Error mounting MCP server: %s", msg, exc_info=True)
    return False


# Global factory function for uvicorn reload mode
def create_app_instance():
    """Factory function for creating app instance in reload mode.

    This function is called by uvicorn when using reload=True with an import string.
    It reads configuration from environment variables set by main().

    How reload works:
    1. main() sets environment variables (DSPY_CLI_LOGS_DIR, DSPY_CLI_ENABLE_MCP)
    2. main() calls uvicorn.run() with import string and reload=True
    3. Uvicorn watches files in reload_dirs matching reload_includes patterns
    4. On file change, uvicorn restarts the process and calls this factory function
    5. This function recreates the app from scratch with fresh module imports

    Watched files:
    - *.py files in src/ (modules, signatures, utils)
    - dspy.config.yaml (model configuration)
    - .env (API keys and environment variables)
    """
    # Get parameters from environment (set by main() before reload)
    logs_dir = os.environ.get(ENV_LOGS_DIR, "./logs")
    enable_mcp = os.environ.get(ENV_ENABLE_MCP, "false").lower() == "true"
    enable_auth = os.environ.get(ENV_AUTH_ENABLED, "false").lower() == "true"

    # Validate project structure
    if not validate_project_structure():
        raise RuntimeError("Not a valid DSPy project directory")

    package_dir = find_package_directory()
    if not package_dir:
        raise RuntimeError("Could not find package in src/")

    package_name = package_dir.name
    modules_path = package_dir / "modules"

    if not modules_path.exists():
        raise RuntimeError(f"modules directory not found: {modules_path}")

    # Load config
    try:
        config = load_config()
    except ConfigError as e:
        raise RuntimeError(f"Configuration error: {e}")

    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)

    # Create and return the app
    app = create_app(
        config=config,
        package_path=modules_path,
        package_name=f"{package_name}.modules",
        logs_dir=logs_path,
        enable_ui=True,
        enable_auth=enable_auth,
    )

    # Mount MCP if enabled
    _maybe_mount_mcp(app, enable_mcp)

    return app


def main(
    port: int,
    host: str,
    logs_dir: str | None,
    reload: bool = True,
    save_openapi: bool = True,
    openapi_format: str = "json",
    mcp: bool = False,
    auth: bool = False,
):
    """Main server execution logic.

    Args:
        port: Port to run the server on
        host: Host to bind to
        logs_dir: Directory for logs
        reload: Whether to enable auto-reload on file changes
        save_openapi: Whether to save OpenAPI spec to file
        openapi_format: Format for OpenAPI spec (json or yaml)
        mcp: Whether to enable MCP server at /mcp
        auth: Whether to enable API authentication
    """
    click.echo("Starting DSPy API server...")
    click.echo()

    if not validate_project_structure():
        click.echo(click.style("Error: Not a valid DSPy project directory", fg="red"))
        click.echo()
        click.echo("Make sure you're in a directory created with 'dspy-cli new'")
        click.echo("Required files: dspy.config.yaml, src/")
        raise click.Abort()

    package_dir = find_package_directory()
    if not package_dir:
        click.echo(click.style("Error: Could not find package in src/", fg="red"))
        raise click.Abort()

    package_name = package_dir.name
    modules_path = package_dir / "modules"

    if not modules_path.exists():
        click.echo(click.style(f"Error: modules directory not found: {modules_path}", fg="red"))
        raise click.Abort()

    try:
        config = load_config()
    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"))
        raise click.Abort()

    click.echo(click.style("✓ Configuration loaded", fg="green"))

    if logs_dir:
        logs_path = Path(logs_dir)
    else:
        logs_path = Path.cwd() / "logs"
    logs_path.mkdir(exist_ok=True)

    try:
        app = create_app(
            config=config,
            package_path=modules_path,
            package_name=f"{package_name}.modules",
            logs_dir=logs_path,
            enable_ui=True,
            enable_auth=auth,
        )

        # Mount MCP if enabled
        def notify_cli(msg: str, level: str = "info"):
            color = "green" if level == "info" else "yellow"
            click.echo(click.style(msg, fg=color))

        _maybe_mount_mcp(app, mcp, notify=notify_cli)

    except Exception as e:
        click.echo(click.style(f"Error creating application: {e}", fg="red"))
        raise click.Abort()

    click.echo()
    click.echo(click.style("Discovered Programs:", fg="cyan", bold=True))
    click.echo()

    if hasattr(app.state, "modules") and app.state.modules:
        for module in app.state.modules:
            click.echo(f"  • {module.name}")
            click.echo(f"    POST /{module.name}")
    else:
        click.echo(click.style("  No programs discovered", fg="yellow"))
        click.echo()
        click.echo("Make sure your DSPy modules:")
        click.echo("  1. Are in src/<package>/modules/")
        click.echo("  2. Subclass dspy.Module")
        click.echo("  3. Are not named with a leading underscore")
        click.echo("  4. If you are using external dependencies:")
        click.echo("     - Ensure your venv is activated")
        click.echo("     - Make sure you have dspy-cli as a local dependency")
        click.echo("     - Install them using pip install -e .")

    click.echo()
    click.echo(click.style("Additional Endpoints:", fg="cyan", bold=True))
    click.echo()
    click.echo("  GET /programs - List all programs and their schemas")
    click.echo("  GET /openapi.json - OpenAPI specification")
    click.echo("  GET / - Web UI for interactive testing")
    if mcp:
        click.echo("  POST /mcp - Model Context Protocol server")
    click.echo()

    # Generate and save OpenAPI spec if requested
    if save_openapi:
        try:
            spec = generate_openapi_spec(app)
            spec_filename = f"openapi.{openapi_format}"
            spec_path = Path.cwd() / spec_filename
            save_openapi_spec(spec, spec_path, format=openapi_format)
            click.echo(click.style(f"✓ OpenAPI spec saved: {spec_filename}", fg="green"))
            click.echo()
        except Exception as e:
            click.echo(click.style(f"Warning: Could not save OpenAPI spec: {e}", fg="yellow"))
            click.echo()

    host_string = "localhost" if host == "0.0.0.0" else host
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style(f"Server starting on http://{host_string}:{port}", fg="green", bold=True))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()
    if reload:
        click.echo(click.style("Hot reload: ENABLED", fg="green"))
        click.echo("  Watching for changes in:")
        click.echo(f"    • {modules_path}")
        click.echo(f"    • {Path.cwd() / 'dspy.config.yaml'}")
        click.echo()
    if auth:
        token = os.environ.get("DSPY_API_KEY")
        if token:
            click.echo(click.style("Authentication: ENABLED", fg="green"))
            click.echo("  API clients: Authorization: Bearer <token>")
            click.echo("  Browser: Visit /login to authenticate")
            click.echo()
    click.echo("Press Ctrl+C to stop the server")
    click.echo()

    try:
        if reload:
            # Set environment variables for create_app_instance()
            os.environ[ENV_LOGS_DIR] = str(logs_path)
            os.environ[ENV_ENABLE_MCP] = str(mcp).lower()
            os.environ[ENV_AUTH_ENABLED] = str(auth).lower()

            # Get project root and src directory for watching
            project_root = Path.cwd()
            src_dir = project_root / "src"

            # Use import string for reload mode
            uvicorn.run(
                "dspy_cli.server.runner:create_app_instance",
                host=host,
                port=port,
                log_level="info",
                access_log=True,
                reload=True,
                reload_dirs=[str(src_dir), str(project_root)],
                reload_includes=["*.py", "*.yaml"],
                reload_excludes=["*.pyc", "*.pyo", "*.pyd", "*/.venv/*", "*/.git/*", "*/__pycache__/*", "*/venv/*"],
                factory=True,
            )
        else:
            # Use app instance for non-reload mode
            uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)
    except KeyboardInterrupt:
        click.echo()
        click.echo(click.style("Server stopped", fg="yellow"))
        sys.exit(0)
    except Exception as e:
        click.echo()
        click.echo(click.style(f"Server error: {e}", fg="red"))
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--logs-dir", default=None)
    parser.add_argument("--reload", action="store_true", default=True)
    parser.add_argument("--save-openapi", action="store_true", default=True)
    parser.add_argument("--openapi-format", choices=["json", "yaml"], default="json")
    parser.add_argument("--mcp", action="store_true", help="Enable MCP server at /mcp")
    parser.add_argument("--auth", action="store_true", help="Enable API authentication")
    args = parser.parse_args()

    main(
        port=args.port,
        host=args.host,
        logs_dir=args.logs_dir,
        reload=args.reload,
        save_openapi=args.save_openapi,
        openapi_format=args.openapi_format,
        mcp=args.mcp,
        auth=args.auth,
    )
