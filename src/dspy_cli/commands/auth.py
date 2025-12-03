"""Command to manage API keys for authentication."""

from pathlib import Path

import click

from dspy_cli.utils.auth import generate_api_key, hash_api_key


@click.command()
def auth():
    """Generate API keys for authentication.

    Creates a new API key, automatically adds the hash to .env, and displays
    the plaintext key (shown only once).

    Example:
        dspy-cli auth
    """
    # Check if we're in a DSPy project directory
    config_path = Path.cwd() / "dspy.config.yaml"
    if not config_path.exists():
        click.echo(click.style("Error: Not in a DSPy project directory", fg="red"))
        click.echo("This command must be run from the root of a DSPy project.")
        click.echo("(Looking for dspy.config.yaml)")
        raise click.Abort()

    # Check if .env exists
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        click.echo(click.style("Error: .env file not found", fg="red"))
        click.echo("Make sure you have a .env file in your project root.")
        raise click.Abort()

    # Generate new API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    # Read existing .env content
    env_content = env_path.read_text()
    lines = env_content.split('\n')

    # Look for existing DSPY_API_KEY_HASHES line (commented or uncommented)
    found_line = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Check for uncommented line
        if stripped.startswith("DSPY_API_KEY_HASHES="):
            existing_value = stripped.split('#')[0].strip()
            existing_hashes = existing_value.replace("DSPY_API_KEY_HASHES=", "").strip()
            if existing_hashes:
                lines[i] = f"DSPY_API_KEY_HASHES={existing_hashes},{key_hash}"
            else:
                lines[i] = f"DSPY_API_KEY_HASHES={key_hash}"
            found_line = True
            break
        # Check for commented placeholder line
        elif stripped.startswith("# DSPY_API_KEY_HASHES="):
            # Replace the commented line with active line
            lines[i] = f"DSPY_API_KEY_HASHES={key_hash}"
            found_line = True
            break

    if not found_line:
        # Add new line at the end
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(f"DSPY_API_KEY_HASHES={key_hash}")

    env_content = '\n'.join(lines)
    if not env_content.endswith('\n'):
        env_content += '\n'

    # Write back to .env
    env_path.write_text(env_content)

    # Display success message
    click.echo()
    click.echo(click.style("✓ API Key Generated and Saved!", fg="green", bold=True))
    click.echo()
    click.echo(click.style("IMPORTANT: Save this key securely - it will only be shown once!", fg="yellow", bold=True))
    click.echo()
    click.echo("API Key (use this to make requests):")
    click.echo(click.style(f"  {api_key}", fg="cyan", bold=True))
    click.echo()
    click.echo(click.style(f"✓ Hash automatically added to .env", fg="green"))
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Enable auth in dspy.config.yaml: auth.enabled = true")
    click.echo("  2. Restart your server: dspy-cli serve")
    click.echo()
