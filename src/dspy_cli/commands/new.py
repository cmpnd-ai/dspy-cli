"""Command to create a new DSPy project."""

import os
import subprocess
from pathlib import Path

import click


@click.command()
@click.argument("project_name")
@click.option(
    "--program-name",
    "-p",
    default=None,
    help="Name of the initial program (default: derived from project name)",
)
def new(project_name, program_name):
    """Create a new DSPy project with boilerplate structure.

    Creates a directory with PROJECT_NAME and sets up a complete
    DSPy project structure with example code, configuration files,
    and a git repository.

    Example:
        dspy-cli new my-project
        dspy-cli new my-project -p custom_program
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

    # Convert project name to Python package name (replace - with _)
    package_name = "dspy_project"  # Always use dspy_project as per spec

    # Determine program name
    if program_name is None:
        # Convert project-name to program_name
        program_name = project_name.replace("-", "_")

    # Validate program name is a valid Python identifier
    if not program_name.replace("_", "").isalnum() or program_name[0].isdigit():
        click.echo(click.style(f"Error: Program name '{program_name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    click.echo(f"Creating new DSPy project: {project_name}")
    click.echo(f"  Package name: {package_name}")
    click.echo(f"  Initial program: {program_name}")
    click.echo()

    try:
        # Create directory structure
        _create_directory_structure(project_path, package_name, program_name)

        # Create configuration files
        _create_config_files(project_path, project_name, program_name)

        # Create Python code files
        _create_code_files(project_path, package_name, program_name)

        # Initialize git repository
        _initialize_git(project_path)

        click.echo(click.style("✓ Project created successfully!", fg="green"))
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  # Edit .env and add your API keys")
        click.echo("  pip install -e .")
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


def _create_config_files(project_path, project_name, program_name):
    """Create configuration files from templates."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent.parent

    # Read and write pyproject.toml
    pyproject_template = (templates_dir / "pyproject.toml.template").read_text()
    pyproject_content = pyproject_template.format(project_name=project_name)
    (project_path / "pyproject.toml").write_text(pyproject_content)

    # Read and write dspy.config.yaml
    config_template = (templates_dir / "dspy.config.yaml.template").read_text()
    config_content = config_template.format(app_id=project_name)
    (project_path / "dspy.config.yaml").write_text(config_content)

    # Read and write .env
    env_template = (templates_dir / "env.template").read_text()
    (project_path / ".env").write_text(env_template)

    # Read and write README.md
    readme_template = (templates_dir / "README.md.template").read_text()
    readme_content = readme_template.format(
        project_name=project_name,
        program_name=program_name
    )
    (project_path / "README.md").write_text(readme_content)

    # Read and write .gitignore
    gitignore_template = (templates_dir / "gitignore.template").read_text()
    (project_path / ".gitignore").write_text(gitignore_template)

    click.echo(f"  Created: {project_name}/pyproject.toml")
    click.echo(f"  Created: {project_name}/dspy.config.yaml")
    click.echo(f"  Created: {project_name}/.env")
    click.echo(f"  Created: {project_name}/README.md")
    click.echo(f"  Created: {project_name}/.gitignore")


def _create_code_files(project_path, package_name, program_name):
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
    signature_class = _to_class_name(program_name) + "Signature"
    signature_template = (templates_dir / "signature.py.template").read_text()
    signature_content = signature_template.format(
        program_name=program_name,
        class_name=signature_class
    )
    (project_path / "src" / package_name / "signatures" / f"{program_name}.py").write_text(signature_content)

    # Create module file
    module_class = f"{_to_class_name(program_name)}Predict"
    module_file = f"{program_name}_predict"
    module_template = (templates_dir / "module_predict.py.template").read_text()
    module_content = module_template.format(
        package_name=package_name,
        program_name=program_name,
        signature_class=signature_class,
        class_name=module_class,
        forward_args="question",
        forward_kwargs="question=question"
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
    click.echo(f"  Created: {package_name}/signatures/{program_name}.py")
    click.echo(f"  Created: tests/test_modules.py")


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


def _to_class_name(snake_case_name):
    """Convert snake_case to PascalCase for class names."""
    return "".join(word.capitalize() for word in snake_case_name.split("_"))
