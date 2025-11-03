"""Command to create a new DSPy project."""

import os
import subprocess
from pathlib import Path

import click

from dspy_cli.utils.signature_utils import parse_signature_string, to_class_name


@click.command()
@click.argument("project_name")
@click.option(
    "--program-name",
    "-p",
    default=None,
    help="Name of the initial program (default: derived from project name)",
)
@click.option(
    "--signature",
    "-s",
    default=None,
    help='Inline signature string (e.g., "question -> answer" or "post -> tags: list[str]")',
)
@click.option(
    "--link-dspy-cli",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Add a uv path override for local dspy-cli development",
)
def new(project_name, program_name, signature, link_dspy_cli):
    """Create a new DSPy project with boilerplate structure.

    Creates a directory with PROJECT_NAME and sets up a complete
    DSPy project structure with example code, configuration files,
    and a git repository.

    Example:
        dspy-cli new my-project
        dspy-cli new my-project -p custom_program
        dspy-cli new my-project -s "post -> tags: list[str]"
        dspy-cli new my-project -p analyzer -s "text, context: list[str] -> summary"
    """
    # Validate project name
    if not project_name or not project_name.strip():
        click.echo(click.style("Error: Project name cannot be empty", fg="red"))
        raise click.Abort()

    project_path = Path.cwd() / project_name

    # Check if directory already exists
    if project_path.exists():
        click.echo(click.style(f"Error: Directory '{project_name}' already exists", fg="red"))
        raise click.Abort()

    # Convert project name to Python package name (replace - with _, lowercase)
    package_name = project_name.replace("-", "_").lower()

    # Determine program name
    if program_name is None:
        # Convert project-name to program_name
        program_name = project_name.replace("-", "_")
    else:
        # Convert dashes to underscores in user-provided program name
        original_program_name = program_name
        program_name = program_name.replace("-", "_")
        if original_program_name != program_name:
            click.echo(f"Note: Converted program name '{original_program_name}' to '{program_name}' for Python compatibility")

    # Validate program name is a valid Python identifier
    if not program_name.replace("_", "").isalnum() or program_name[0].isdigit():
        click.echo(click.style(f"Error: Program name '{program_name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    # Parse signature if provided
    signature_fields = None
    if signature:
        signature_fields = parse_signature_string(signature)

    click.echo(f"Creating new DSPy project: {project_name}")
    click.echo(f"  Package name: {package_name}")
    click.echo(f"  Initial program: {program_name}")
    if signature:
        click.echo(f"  Signature: {signature}")
    click.echo()

    try:
        # Create directory structure
        _create_directory_structure(project_path, package_name, program_name)

        # Create configuration files
        _create_config_files(project_path, project_name, program_name, package_name)

        # Add uv path override if requested
        _add_uv_override_if_requested(project_path, link_dspy_cli)

        # Create Python code files
        _create_code_files(project_path, package_name, program_name, signature, signature_fields)

        # Initialize git repository
        _initialize_git(project_path)

        click.echo(click.style("✓ Project created successfully!", fg="green"))
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  # Edit .env and add your API keys")
        click.echo("  uv sync")
        click.echo("  source .venv/bin/activate")
        click.echo("  dspy-cli serve")

    except Exception as e:
        click.echo(click.style(f"Error creating project: {e}", fg="red"))
        # Clean up partially created directory
        if project_path.exists():
            import shutil
            shutil.rmtree(project_path)
        raise click.Abort()


def _create_directory_structure(project_path, package_name, program_name):
    """Create the directory structure for the project."""
    directories = [
        project_path / "src" / package_name,
        project_path / "src" / package_name / "modules",
        project_path / "src" / package_name / "signatures",
        project_path / "src" / package_name / "optimizers",
        project_path / "src" / package_name / "metrics",
        project_path / "src" / package_name / "utils",
        project_path / "data",
        project_path / "logs",
        project_path / "tests",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        click.echo(f"  Created: {directory.relative_to(project_path.parent)}")


def _add_uv_override_if_requested(project_path, link_dspy_cli):
    """Add uv path override for dspy-cli if requested."""
    # Check flag or environment variable
    link = link_dspy_cli or os.getenv("DSPY_CLI_PATH")
    if not link:
        return
    
    # Convert to relative path
    link_path = Path(link).resolve()
    try:
        rel_path = os.path.relpath(link_path, project_path)
    except ValueError:
        # Different drives on Windows, use absolute
        rel_path = str(link_path)
    
    # Append uv.sources block
    uv_block = f'\n[tool.uv.sources]\ndspy-cli = {{ path = "{rel_path}", editable = true }}\n'
    pyproject_path = project_path / "pyproject.toml"
    current_content = pyproject_path.read_text()
    pyproject_path.write_text(current_content + uv_block)
    
    click.echo(click.style(f"  Added uv path override: dspy-cli -> {rel_path}", fg="cyan"))
    click.echo(click.style("  Note: This is for local development only - do not commit this override", fg="yellow"))


def _create_config_files(project_path, project_name, program_name, package_name):
    """Create configuration files from templates."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent.parent

    # Read and write pyproject.toml
    pyproject_template = (templates_dir / "pyproject.toml.template").read_text()
    pyproject_content = pyproject_template.format(project_name=project_name)
    (project_path / "pyproject.toml").write_text(pyproject_content)
    click.echo(f"  Created: {project_name}/pyproject.toml")

    # Read and write dspy.config.yaml
    config_template = (templates_dir / "dspy.config.yaml.template").read_text()
    config_content = config_template.format(app_id=project_name)
    (project_path / "dspy.config.yaml").write_text(config_content)
    click.echo(f"  Created: {project_name}/dspy.config.yaml")

    # Read and write Dockerfile
    dockerfile_template = (templates_dir / "Dockerfile.template").read_text()
    (project_path / "Dockerfile").write_text(dockerfile_template)
    click.echo(f"  Created: {project_name}/Dockerfile")

    # Read and write .dockerignore
    dockerignore_template = (templates_dir / ".dockerignore.template").read_text()
    (project_path / ".dockerignore").write_text(dockerignore_template)
    click.echo(f"  Created: {project_name}/.dockerignore")

    # Read and write .env
    env_template = (templates_dir / "env.template").read_text()
    (project_path / ".env").write_text(env_template)
    click.echo(f"  Created: {project_name}/.env")

    # Read and write README.md
    readme_template = (templates_dir / "README.md.template").read_text()
    readme_content = readme_template.format(
        project_name=project_name,
        program_name=program_name,
        package_name=package_name
    )
    (project_path / "README.md").write_text(readme_content)
    click.echo(f"  Created: {project_name}/README.md")

    # Read and write .gitignore
    gitignore_template = (templates_dir / "gitignore.template").read_text()
    (project_path / ".gitignore").write_text(gitignore_template)
    click.echo(f"  Created: {project_name}/.gitignore")

def _create_code_files(project_path, package_name, program_name, signature, signature_fields):
    """Create Python code files from templates."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent

    # Create __init__.py files
    (project_path / "src" / package_name / "__init__.py").write_text(
        f'"""DSPy project: {package_name}."""\n'
    )
    (project_path / "src" / package_name / "modules" / "__init__.py").write_text("")
    (project_path / "src" / package_name / "signatures" / "__init__.py").write_text("")
    (project_path / "src" / package_name / "optimizers" / "__init__.py").write_text("")
    (project_path / "src" / package_name / "metrics" / "__init__.py").write_text("")
    (project_path / "src" / package_name / "utils" / "__init__.py").write_text("")

    # Create signature file
    signature_class = to_class_name(program_name) + "Signature"
    file_name = program_name.lower()

    if signature_fields:
        # Generate from parsed signature
        signature_content = f'"""Signature definitions for {file_name}."""\n\nimport dspy\n\n'
        signature_content += f"class {signature_class}(dspy.Signature):\n"
        signature_content += '    """\n    """\n\n'

        # Add input fields
        for field in signature_fields['inputs']:
            signature_content += f"    {field['name']}: {field['type']} = dspy.InputField(desc=\"\")\n"

        # Add output fields
        for field in signature_fields['outputs']:
            signature_content += f"    {field['name']}: {field['type']} = dspy.OutputField(desc=\"\")\n"
    else:
        # Use default template
        signature_template = (templates_dir / "signature.py.template").read_text()
        signature_content = signature_template.format(
            program_name=file_name,
            class_name=signature_class
        )

    (project_path / "src" / package_name / "signatures" / f"{file_name}.py").write_text(signature_content)

    # Create module file
    module_class = f"{to_class_name(program_name)}Predict"
    module_file = f"{file_name}_predict"

    module_template = (templates_dir / "module_predict.py.template").read_text()
    module_content = module_template.format(
        package_name=package_name,
        program_name=file_name,
        signature_class=signature_class,
        class_name=module_class
    )
    (project_path / "src" / package_name / "modules" / f"{module_file}.py").write_text(module_content)

    # Create test file
    test_template = (templates_dir / "test_modules.py.template").read_text()
    test_content = test_template.format(
        package_name=package_name,
        module_file=module_file,
        module_class=module_class
    )
    (project_path / "tests" / "test_modules.py").write_text(test_content)

    click.echo(f"  Created: {package_name}/modules/{module_file}.py")
    click.echo(f"  Created: {package_name}/signatures/{file_name}.py")
    click.echo("  Created: tests/test_modules.py")


def _initialize_git(project_path):
    """Initialize a git repository."""
    try:
        subprocess.run(
            ["git", "init"],
            cwd=project_path,
            check=True,
            capture_output=True
        )
        click.echo("  Initialized git repository")
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"  Warning: Could not initialize git: {e}", fg="yellow"))
    except FileNotFoundError:
        click.echo(click.style("  Warning: git not found, skipping repository initialization", fg="yellow"))
