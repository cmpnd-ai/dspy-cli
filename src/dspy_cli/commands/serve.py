"""Command to serve DSPy programs as an API."""

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import click

from dspy_cli.server.runner import main as runner_main
from dspy_cli.utils.venv import (
    detect_venv_python,
    has_package,
    is_in_project_venv,
    sanitize_env_for_exec,
    show_install_instructions,
    show_venv_warning,
    validate_python_version,
)


def _exec_clean(target_python: Path, args: list[str]) -> NoReturn:
    """Execute the server using the target Python with a clean environment."""
    env = sanitize_env_for_exec()
    cmd = [str(target_python)] + args
    
    # On Windows, os.execvpe has issues (Python bug #19124), use subprocess
    if sys.platform == "win32":
        try:
            result = subprocess.run(cmd, env=env)
            sys.exit(result.returncode)
        except FileNotFoundError:
            click.echo(click.style(f"Error: Python interpreter not found: {target_python}", fg="red"), err=True)
            sys.exit(1)
        except PermissionError:
            click.echo(click.style(f"Error: Permission denied executing: {target_python}", fg="red"), err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(130)
    else:
        # Unix: use exec for efficient process replacement
        try:
            os.execvpe(str(target_python), cmd, env)
        except OSError as e:
            click.echo(click.style(f"Error executing {target_python}: {e}", fg="red"), err=True)
            sys.exit(1)


@click.command()
@click.option(
    "--port",
    default=8000,
    type=click.IntRange(1, 65535),
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
@click.option(
    "--reload/--no-reload",
    default=True,
    help="Enable auto-reload on file changes (default: enabled)",
)
@click.option(
    "--save-openapi/--no-save-openapi",
    default=True,
    help="Save OpenAPI spec to file on server start (default: enabled)",
)
@click.option(
    "--openapi-format",
    type=click.Choice(["json", "yaml"], case_sensitive=False),
    default="json",
    help="Format for OpenAPI spec file (default: json)",
)
@click.option(
    "--python",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to Python interpreter to use (default: auto-detect)",
)
@click.option(
    "--system",
    is_flag=True,
    help="Use system Python environment instead of project venv",
)
@click.option(
    "--mcp",
    is_flag=True,
    help="Enable Model Context Protocol server at /mcp",
)
@click.option(
    "--auth/--no-auth",
    default=False,
    help="Enable API authentication via DSPY_API_KEY (default: disabled)",
)
def serve(port, host, logs_dir, reload, save_openapi, openapi_format, python, system, mcp, auth):
    """Start an HTTP API server that exposes your DSPy programs.

    This command:
    - Validates that you're in a DSPy project directory
    - Loads configuration from dspy.config.yaml
    - Discovers DSPy modules in src/<package>/modules/
    - Starts a FastAPI server with endpoints for each program

    Example:
        dspy-cli serve
        dspy-cli serve --port 8080 --host 127.0.0.1
        dspy-cli serve --python /path/to/venv/bin/python
    """
    if system:
        runner_main(
            port=port,
            host=host,
            logs_dir=logs_dir,
            reload=reload,
            save_openapi=save_openapi,
            openapi_format=openapi_format,
            mcp=mcp,
            auth=auth,
        )
        return
    
    target_python = None
    if python:
        target_python = Path(python)
        
        # Validate it's actually a Python interpreter
        if not target_python.is_file():
            click.echo(click.style(f"Error: Not a valid Python executable: {target_python}", fg="red"), err=True)
            sys.exit(1)
        
        # On Unix, check if executable
        if sys.platform != "win32" and not os.access(target_python, os.X_OK):
            click.echo(click.style(f"Error: Python interpreter is not executable: {target_python}", fg="red"), err=True)
            sys.exit(1)
        
        # Validate Python version
        is_valid, version = validate_python_version(target_python, min_version=(3, 9))
        if not is_valid:
            if version:
                click.echo(click.style(f"Error: Python {version} is too old. Minimum required: Python 3.9", fg="red"), err=True)
            else:
                click.echo(click.style(f"Error: Could not determine Python version for: {target_python}", fg="red"), err=True)
            sys.exit(1)
    elif not is_in_project_venv():
        target_python = detect_venv_python()
        if not target_python:
            show_venv_warning()
    
    if target_python:
        import dspy_cli
        
        has_cli, local_version = has_package(target_python, "dspy_cli")
        
        if not has_cli:
            global_version = dspy_cli.__version__
            show_install_instructions(target_python, global_version)
            sys.exit(1)
        
        if local_version:
            global_version = dspy_cli.__version__
            local_major = local_version.split('.')[0]
            global_major = global_version.split('.')[0]
            
            if local_major != global_major:
                click.echo(click.style(
                    f"⚠ Version mismatch: local dspy-cli {local_version} vs global {global_version}",
                    fg="yellow"
                ))
                click.echo(f"Consider upgrading: {shlex.quote(str(target_python))} -m uv add 'dspy-cli=={global_version}'")
                click.echo()
        
        args = ["-m", "dspy_cli.server.runner", "--port", str(port), "--host", host]
        if logs_dir:
            args.extend(["--logs-dir", logs_dir])
        if reload:
            args.append("--reload")
        if save_openapi:
            args.append("--save-openapi")
        args.extend(["--openapi-format", openapi_format])
        if mcp:
            args.append("--mcp")
        if auth:
            args.append("--auth")

        _exec_clean(target_python, args)
    else:
        runner_main(
            port=port,
            host=host,
            logs_dir=logs_dir,
            reload=reload,
            save_openapi=save_openapi,
            openapi_format=openapi_format,
            mcp=mcp,
            auth=auth,
        )
