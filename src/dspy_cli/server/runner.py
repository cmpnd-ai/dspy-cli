"""Server runner module for executing DSPy API server."""

import os
import sys
from pathlib import Path

import click
import uvicorn

from dspy_cli.config import ConfigError, load_config
from dspy_cli.config.validator import find_package_directory, validate_project_structure
from dspy_cli.server.app import create_app


# Global factory function for uvicorn reload mode
def create_app_instance():
    """Factory function for creating app instance in reload mode.

    This function is called by uvicorn when using reload=True with an import string.
    It reads configuration from environment variables set by main().

    How reload works:
    1. main() sets environment variables (DSPY_CLI_LOGS_DIR, DSPY_CLI_ENABLE_UI)
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
    logs_dir = os.environ.get("DSPY_CLI_LOGS_DIR", "./logs")
    enable_ui = os.environ.get("DSPY_CLI_ENABLE_UI", "false").lower() == "true"

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
    return create_app(
        config=config,
        package_path=modules_path,
        package_name=f"{package_name}.modules",
        logs_dir=logs_path,
        enable_ui=enable_ui
    )


def main(port: int, host: str, logs_dir: str | None, ui: bool, reload: bool = True):
    """Main server execution logic.

    Args:
        port: Port to run the server on
        host: Host to bind to
        logs_dir: Directory for logs
        ui: Whether to enable web UI
        reload: Whether to enable auto-reload on file changes
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
            enable_ui=ui
        )
    except Exception as e:
        click.echo(click.style(f"Error creating application: {e}", fg="red"))
        raise click.Abort()

    click.echo()
    click.echo(click.style("Discovered Programs:", fg="cyan", bold=True))
    click.echo()

    if hasattr(app.state, 'modules') and app.state.modules:
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
    if ui:
        click.echo("  GET / - Web UI for interactive testing")
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
        click.echo(f"    • {Path.cwd() / '.env'}")
        click.echo()
    click.echo("Press Ctrl+C to stop the server")
    click.echo()

    try:
        if reload:
            # Set environment variables for create_app_instance()
            os.environ["DSPY_CLI_LOGS_DIR"] = str(logs_path)
            os.environ["DSPY_CLI_ENABLE_UI"] = str(ui).lower()

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
                reload_includes=["*.py", "*.yaml", ".env"],
                factory=True
            )
        else:
            # Use app instance for non-reload mode
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level="info",
                access_log=True
            )
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
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--reload", action="store_true", default=True)
    args = parser.parse_args()

    main(port=args.port, host=args.host, logs_dir=args.logs_dir, ui=args.ui, reload=args.reload)
