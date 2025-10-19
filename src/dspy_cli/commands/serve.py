"""Command to serve DSPy programs as an API."""

import sys
from pathlib import Path

import click
import uvicorn

from dspy_cli.config import ConfigError, load_config
from dspy_cli.config.validator import find_package_directory, validate_project_structure
from dspy_cli.server.app import create_app


@click.command()
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to run the server on (default: 8000)",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind to (default: 0.0.0.0)",
)
@click.option(
    "--logs-dir",
    default=None,
    type=click.Path(),
    help="Directory for logs (default: ./logs)",
)
def serve(port, host, logs_dir):
    """Start an HTTP API server that exposes your DSPy programs.

    This command:
    - Validates that you're in a DSPy project directory
    - Loads configuration from dspy.config.yaml
    - Discovers DSPy modules in src/<package>/modules/
    - Starts a FastAPI server with endpoints for each program

    Example:
        dspy-cli serve
        dspy-cli serve --port 8080 --host 127.0.0.1
    """
    click.echo("Starting DSPy API server...")
    click.echo()

    # Validate project structure
    if not validate_project_structure():
        click.echo(click.style("Error: Not a valid DSPy project directory", fg="red"))
        click.echo()
        click.echo("Make sure you're in a directory created with 'dspy-cli new'")
        click.echo("Required files: dspy.config.yaml, src/")
        raise click.Abort()

    # Find package directory
    package_dir = find_package_directory()
    if not package_dir:
        click.echo(click.style("Error: Could not find package in src/", fg="red"))
        raise click.Abort()

    package_name = package_dir.name
    modules_path = package_dir / "modules"

    if not modules_path.exists():
        click.echo(click.style(f"Error: modules directory not found: {modules_path}", fg="red"))
        raise click.Abort()

    # Load configuration
    try:
        config = load_config()
    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"))
        raise click.Abort()

    click.echo(click.style("✓ Configuration loaded", fg="green"))

    # Create logs directory
    if logs_dir:
        logs_path = Path(logs_dir)
    else:
        logs_path = Path.cwd() / "logs"
    logs_path.mkdir(exist_ok=True)

    # Create FastAPI app
    try:
        app = create_app(
            config=config,
            package_path=modules_path,
            package_name=f"{package_name}.modules",
            logs_dir=logs_path
        )
    except Exception as e:
        click.echo(click.style(f"Error creating application: {e}", fg="red"))
        raise click.Abort()

    # Print discovered programs
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

    click.echo()
    click.echo(click.style("Additional Endpoints:", fg="cyan", bold=True))
    click.echo()
    click.echo("  GET /programs - List all programs and their schemas")
    click.echo()

    # Print server information
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style(f"Server starting on http://{host}:{port}", fg="green", bold=True))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()
    click.echo("Press Ctrl+C to stop the server")
    click.echo()

    # Start uvicorn server
    try:
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
