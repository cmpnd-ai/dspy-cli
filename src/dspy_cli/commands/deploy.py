"""Command to deploy DSPy applications to the control plane."""

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import click
import requests
import yaml


@click.command()
@click.option(
    "--control-url",
    envvar="DSPY_CONTROL_URL",
    help="Control plane URL (default: derived from dspy.yaml host or http://localhost:9000)",
)
@click.option(
    "--api-key",
    envvar="DSPY_CONTROL_API_KEY",
    help="API key for control plane authentication",
)
@click.option(
    "--api-key-file",
    type=click.Path(exists=True, path_type=Path),
    help="File containing API key for control plane authentication",
)
@click.option(
    "--app-id",
    help="Override app_id from dspy.yaml",
)
@click.option(
    "--module-path",
    help="Override module_path from dspy.yaml (e.g., app.main:QA)",
)
@click.option(
    "--code-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Override code_dir from dspy.yaml",
)
@click.option(
    "--commit-sha",
    help="Git commit SHA (auto-detected if not provided)",
)
@click.option(
    "--source-ref",
    help="Git source reference/branch (auto-detected if not provided)",
)
def deploy(
    control_url: Optional[str],
    api_key: Optional[str],
    api_key_file: Optional[Path],
    app_id: Optional[str],
    module_path: Optional[str],
    code_dir: Optional[Path],
    commit_sha: Optional[str],
    source_ref: Optional[str],
):
    """Deploy a DSPy application to the control plane.

    This command:
    - Reads configuration from dspy.yaml
    - Packages your code as a ZIP file
    - Deploys to the control plane
    - Saves the runtime API key for predictions

    Example:
        dspy-cli deploy
        dspy-cli deploy --control-url http://localhost:9000
        dspy-cli deploy --api-key <key>
    """
    try:
        config = load_deploy_config()
    except Exception as e:
        click.echo(click.style(f"Error loading configuration: {e}", fg="red"))
        click.echo()
        click.echo("Expected format (dspy.config.yaml or dspy.yaml):")
        click.echo("  app_id: myapp")
        click.echo("  module_path: app.main:MyModule")
        click.echo("  code_dir: app")
        click.echo("  host: localhost  # optional")
        raise click.Abort()

    final_app_id = app_id or config.get("app_id")
    final_module_path = module_path or config.get("module_path")
    final_code_dir = code_dir or config.get("code_dir")

    if not final_app_id:
        click.echo(click.style("Error: app_id not found in config or --app-id", fg="red"))
        raise click.Abort()
    if not final_module_path:
        click.echo(click.style("Error: module_path not found in config or --module-path", fg="red"))
        raise click.Abort()
    if not final_code_dir:
        click.echo(click.style("Error: code_dir not found in config or --code-dir", fg="red"))
        raise click.Abort()

    final_control_url = resolve_control_url(control_url, config.get("host"))

    final_api_key = resolve_api_key(api_key, api_key_file)

    if not commit_sha or not source_ref:
        detected_sha, detected_ref = detect_git_metadata()
        final_commit_sha = commit_sha or detected_sha
        final_source_ref = source_ref or detected_ref

    click.echo(f"Deploying {final_app_id} to {final_control_url}...")
    click.echo()

    zip_path = None
    try:
        # Zip the entire project directory (parent of code_dir) to include dspy.config.yaml
        project_root = Path.cwd()
        zip_path = zip_code_dir(project_root)
        
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        if zip_size_mb > 150:
            click.echo(click.style(f"Warning: ZIP file is large ({zip_size_mb:.1f} MB)", fg="yellow"))

        headers = get_auth_header(final_api_key)
        
        response = post_deploy(
            control_url=final_control_url,
            app_id=final_app_id,
            module_path=final_module_path,
            zip_path=zip_path,
            commit_sha=final_commit_sha,
            source_ref=final_source_ref,
            headers=headers,
        )

        if response.get("runtime_api_key"):
            save_runtime_key(final_app_id, response["runtime_api_key"])

        print_deploy_result(response)

    except requests.exceptions.ConnectionError:
        click.echo()
        click.echo(click.style(f"Error: Could not connect to control plane at {final_control_url}", fg="red"))
        click.echo()
        click.echo("Make sure the control plane is running:")
        click.echo("  make run-control")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        click.echo()
        click.echo(click.style(f"Deployment failed: {e}", fg="red"))
        if e.response is not None:
            try:
                error_detail = e.response.json().get("detail", e.response.text)
            except Exception:
                error_detail = e.response.text
            click.echo(click.style(f"Server response: {error_detail}", fg="red"))
            
            if e.response.status_code in (401, 403):
                click.echo()
                click.echo("Authentication failed. Provide an API key via:")
                click.echo("  --api-key <key>")
                click.echo("  --api-key-file <path>")
                click.echo("  DSPY_CONTROL_API_KEY env variable")
                click.echo("  ~/.dspy/control.key file")
        sys.exit(1)
    except Exception as e:
        click.echo()
        click.echo(click.style(f"Error: {e}", fg="red"))
        sys.exit(1)
    finally:
        if zip_path and zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass


def load_deploy_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load deployment configuration from YAML file."""
    # Try dspy.config.yaml first (new format), then dspy.yaml (old format)
    if path is None:
        if Path("dspy.config.yaml").exists():
            path = "dspy.config.yaml"
        elif Path("dspy.yaml").exists():
            path = "dspy.yaml"
        else:
            raise FileNotFoundError("Configuration file not found: dspy.config.yaml or dspy.yaml")
    
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    if not isinstance(config, dict):
        raise ValueError("Invalid configuration file format")
    
    if "code_dir" in config:
        code_dir = Path(config["code_dir"])
        if not code_dir.is_absolute():
            code_dir = config_path.parent / code_dir
        if not code_dir.exists():
            raise FileNotFoundError(f"code_dir not found: {code_dir}")
        config["code_dir"] = code_dir
    
    return config


def detect_git_metadata() -> tuple[Optional[str], Optional[str]]:
    """Detect git commit SHA and branch/ref."""
    commit_sha = None
    source_ref = None
    
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        commit_sha = result.stdout.strip()
    except Exception:
        pass
    
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        source_ref = result.stdout.strip()
    except Exception:
        pass
    
    return commit_sha, source_ref


def resolve_control_url(cli_url: Optional[str], cfg_host: Optional[str]) -> str:
    """Resolve control plane URL from various sources."""
    if cli_url:
        return cli_url.rstrip("/")
    
    if cfg_host:
        if cfg_host.startswith(("http://", "https://")):
            return cfg_host.rstrip("/")
        return f"http://{cfg_host}:9000"
    
    return "http://localhost:9000"


def resolve_api_key(cli_key: Optional[str], key_file: Optional[Path]) -> Optional[str]:
    """Resolve API key from various sources."""
    if cli_key:
        return cli_key
    
    if key_file:
        return key_file.read_text().strip()
    
    default_key_file = Path.home() / ".dspy" / "control.key"
    if default_key_file.exists():
        return default_key_file.read_text().strip()
    
    return None


def zip_code_dir(code_dir: Path) -> Path:
    """Create a ZIP file from the code directory."""
    temp_file = tempfile.NamedTemporaryFile(mode="wb", suffix=".zip", delete=False)
    temp_file.close()
    zip_path = Path(temp_file.name)
    
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache"}
    skip_patterns = {".pyc", ".pyo", ".pyd", ".so", ".dylib", ".egg-info"}
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in code_dir.rglob("*"):
            if item.is_symlink():
                continue
            
            if any(part in skip_dirs for part in item.parts):
                continue
            
            if any(item.name.endswith(pattern) for pattern in skip_patterns):
                continue
            
            if item.is_file():
                arcname = item.relative_to(code_dir)
                zf.write(item, arcname)
    
    return zip_path


def get_auth_header(api_key: Optional[str]) -> dict[str, str]:
    """Build authentication header if API key is provided."""
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def post_deploy(
    control_url: str,
    app_id: str,
    module_path: str,
    zip_path: Path,
    commit_sha: Optional[str] = None,
    source_ref: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """POST deployment to control plane."""
    url = f"{control_url}/deploy"
    
    data = {
        "app_id": app_id,
        "module_path": module_path,
    }
    
    if commit_sha:
        data["commit_sha"] = commit_sha
    if source_ref:
        data["source_ref"] = source_ref
    
    with open(zip_path, "rb") as f:
        files = {"code": ("code.zip", f, "application/zip")}
        
        response = requests.post(
            url,
            data=data,
            files=files,
            headers=headers or {},
            timeout=120,
        )
    
    response.raise_for_status()
    return response.json()


def save_runtime_key(app_id: str, key: str):
    """Save runtime API key to ~/.dspy/keys/{app_id}.key."""
    keys_dir = Path.home() / ".dspy" / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    
    key_file = keys_dir / f"{app_id}.key"
    key_file.write_text(key)
    
    try:
        key_file.chmod(0o600)
    except Exception:
        pass


def print_deploy_result(response: dict[str, Any]):
    """Print deployment result in format expected by scripts."""
    click.echo()
    click.echo(click.style("Deployment successful!", fg="green", bold=True))
    click.echo()
    click.echo(f"App ID: {response.get('app_id', 'N/A')}")
    click.echo(f"Version: {response.get('version', 'N/A')}")
    click.echo(f"Route: {response.get('route', 'N/A')}")
    
    if response.get("programs"):
        click.echo()
        click.echo(click.style("Programs:", fg="cyan", bold=True))
        for prog in response["programs"]:
            click.echo(f"  • {prog.get('name', 'N/A')}")
            click.echo(f"    {prog.get('url', 'N/A')}")
    
    if response.get("runtime_api_key"):
        click.echo()
        click.echo(f"Key: {response['runtime_api_key']}")
        click.echo()
        click.echo(click.style("Runtime API key saved to ~/.dspy/keys/", fg="cyan"))
