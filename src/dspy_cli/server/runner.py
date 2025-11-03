"""Server runner module for executing DSPy API server."""

import sys
from pathlib import Path

import click
import uvicorn

from dspy_cli.config import ConfigError, load_config
from dspy_cli.config.validator import find_package_directory, validate_project_structure
from dspy_cli.server.app import create_app


def main(port: int, host: str, logs_dir: str | None, ui: bool):
    """Main server execution logic.
    
    Args:
        port: Port to run the server on
        host: Host to bind to
        logs_dir: Directory for logs
        ui: Whether to enable web UI
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

    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style(f"Server starting on http://{host}:{port}", fg="green", bold=True))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()
    click.echo("Press Ctrl+C to stop the server")
    click.echo()

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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--logs-dir", default=None)
    parser.add_argument("--ui", action="store_true")
    args = parser.parse_args()
    
    main(port=args.port, host=args.host, logs_dir=args.logs_dir, ui=args.ui)
