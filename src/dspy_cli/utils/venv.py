"""Virtual environment detection and management utilities."""

import os
import sys
from pathlib import Path

import click


def detect_venv_python() -> Path | None:
    """Detect project virtual environment Python interpreter.
    
    Returns:
        Path to venv Python interpreter, or None if not found
    """
    python_name = "python.exe" if sys.platform == "win32" else "python"
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    
    for venv_dir in [".venv", "venv"]:
        python_path = Path.cwd() / venv_dir / bin_dir / python_name
        if python_path.exists():
            return python_path
    
    return None


def is_in_project_venv() -> bool:
    """Check if currently running in the project's virtual environment.
    
    Returns:
        True if running in the project's venv, False otherwise
    """
    if sys.prefix == sys.base_prefix:
        return False
    
    project_venv_python = detect_venv_python()
    if not project_venv_python:
        return False
    
    project_venv_dir = project_venv_python.parent.parent
    return Path(sys.prefix).resolve() == project_venv_dir.resolve()


def has_package(python: Path, package_name: str) -> tuple[bool, str | None]:
    """Check if a package is available in the given Python interpreter.
    
    Args:
        python: Path to Python interpreter
        package_name: Name of the package to check for
        
    Returns:
        Tuple of (is_available, version_or_none)
    """
    import subprocess
    
    code = f"import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('{package_name}') else 1)"
    try:
        result = subprocess.run(
            [str(python), "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        has = result.returncode == 0
    except Exception:
        return False, None
    
    version = None
    if has:
        try:
            out = subprocess.check_output(
                [str(python), "-c", f"import importlib.metadata as m; print(m.version('{package_name}'))"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5
            ).strip()
            version = out or None
        except Exception:
            pass
    
    return has, version


def sanitize_env_for_exec() -> dict:
    """Create a sanitized environment for re-execution.
    
    Removes Python-specific variables that could cause conflicts
    when executing in a different Python environment.
    
    Returns:
        Sanitized environment dict
    """
    env = os.environ.copy()
    
    # Remove Python-specific variables
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__", "PYTHONEXECUTABLE"):
        env.pop(key, None)
    
    # Remove Conda variables to avoid contamination
    for key in list(env.keys()):
        if key.startswith("CONDA_"):
            env.pop(key, None)
    
    # Prevent user site-packages from contaminating execution
    env["PYTHONNOUSERSITE"] = "1"
    
    return env


def validate_python_version(python: Path, min_version: tuple = (3, 9)) -> tuple[bool, str]:
    """Validate Python interpreter meets minimum version requirement.
    
    Args:
        python: Path to Python interpreter
        min_version: Minimum required version as tuple (major, minor)
        
    Returns:
        Tuple of (is_valid, version_string)
    """
    import subprocess
    
    # Use -S to avoid sitecustomize/usercustomize interference
    try:
        result = subprocess.run(
            [str(python), "-S", "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, ""
        
        version_str = result.stdout.strip()
        parts = version_str.split('.')
        if len(parts) < 2:
            return False, version_str
        
        major, minor = int(parts[0]), int(parts[1])
        is_valid = (major, minor) >= min_version
        
        return is_valid, version_str
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, ValueError):
        return False, ""


def show_venv_warning():
    """Display warning and guidance when no venv is detected."""
    click.echo(click.style("⚠ Warning: No virtual environment detected", fg="yellow"))
    click.echo()
    click.echo("Running without a project venv may cause import errors if dependencies")
    click.echo("(including dspy-cli) are not installed in your current environment.")
    click.echo()
    click.echo("For best results, either:")
    click.echo("  1. Add dspy-cli to your project:")
    click.echo("     uv add dspy-cli")
    click.echo("  2. Create and activate a venv:")
    click.echo("     uv sync  (or python -m venv .venv && source .venv/bin/activate)")
    click.echo("  3. Use a task runner:")
    click.echo("     uv run dspy-cli serve")
    click.echo("  4. Specify Python interpreter:")
    click.echo("     dspy-cli serve --python /path/to/python")
    click.echo("  5. Use system environment:")
    click.echo("     dspy-cli serve --system")
    click.echo()
    click.echo("Attempting to continue with current environment...")
    click.echo()


def show_install_instructions(target_python: Path, version: str):
    """Show instructions for installing dspy-cli locally."""
    click.echo(click.style("dspy-cli is not installed in your project virtual environment.", fg="yellow"))
    click.echo()
    click.echo("Install it into your project:")
    click.echo("  uv add dspy-cli")
    click.echo()
    click.echo("Then run directly:")
    click.echo("  dspy-cli serve")
    click.echo()
    click.echo("You can bypass this check with --system")
