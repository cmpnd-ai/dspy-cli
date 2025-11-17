"""Command to create a new DSPy project."""

import subprocess
from pathlib import Path

import click

from dspy_cli.utils.signature_utils import parse_signature_string, to_class_name, build_forward_components
from dspy_cli.utils.interactive import (
    prompt_project_name,
    prompt_setup_first_program,
    prompt_program_name,
    prompt_module_type,
    prompt_signature,
    prompt_model,
    prompt_api_key,
)
from dspy_cli.utils.model_utils import (
    parse_model_string,
    is_local_model,
    detect_api_key,
    generate_model_config,
    get_provider_display_name,
)
from dspy_cli.utils.constants import MODULE_TYPES


@click.command()
@click.argument("project_name", required=False)
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
    "--module-type",
    "-m",
    default=None,
    help="DSPy module type (Predict, ChainOfThought, ReAct, etc.)",
)
@click.option(
    "--model",
    default=None,
    help="LiteLLM model string (e.g., anthropic/claude-sonnet-4-5, openai/gpt-4o)",
)
@click.option(
    "--api-key",
    default=None,
    help="API key for the LLM provider (will be stored in .env)",
)
def new(project_name, program_name, signature, module_type, model, api_key):
    """Create a new DSPy project with boilerplate structure.

    Creates a directory with PROJECT_NAME and sets up a complete
    DSPy project structure with example code, configuration files,
    and a git repository.

    Interactive mode (recommended):
        dspy-cli new

    Non-interactive mode:
        dspy-cli new my-project
        dspy-cli new my-project -p custom_program -m CoT
        dspy-cli new my-project -s "post -> tags: list[str]"
        dspy-cli new my-project -p analyzer -s "text -> summary" --model anthropic/claude-sonnet-4-5
    """
    # Interactive prompts for missing parameters
    if not project_name:
        project_name = prompt_project_name()

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

    # Determine if we should prompt for program details or use defaults
    # Only ask in interactive mode (when program_name, module_type, and signature are all None)
    customize_program = True
    if program_name is None and module_type is None and signature is None:
        customize_program = prompt_setup_first_program()

    # Determine program name
    if program_name is None:
        if customize_program:
            # Use default "my_program" instead of deriving from project name
            program_name = prompt_program_name(default="my_program")
        else:
            # Use default without prompting
            program_name = "my_program"

    # Convert to valid Python identifier (replace dashes and spaces with underscores)
    original_program_name = program_name
    program_name = program_name.replace("-", "_").replace(" ", "_")

    if original_program_name != program_name:
        click.echo(f"Note: Converted program name '{original_program_name}' to '{program_name}' for Python compatibility")

    # Validate program name is a valid Python identifier
    if not program_name.replace("_", "").isalnum() or program_name[0].isdigit():
        click.echo(click.style(f"Error: Program name '{program_name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    # Prompt for module type
    if module_type is None:
        if customize_program:
            module_type = prompt_module_type(default="Predict")
        else:
            # Use default without prompting
            module_type = "Predict"
    elif module_type not in MODULE_TYPES:
        click.echo(click.style(f"Error: Unknown module type '{module_type}'", fg="red"))
        click.echo(f"Available: {', '.join(MODULE_TYPES.keys())}")
        raise click.Abort()

    # Prompt for signature
    signature_fields = None
    if signature is None:
        if customize_program:
            signature, signature_fields = prompt_signature()
        else:
            # Use default without prompting
            signature = "question:str -> answer:str"
            signature_fields = None
    else:
        # Strip optional quotes from command-line signature
        signature = signature.strip().strip('"').strip("'")
        # Parse provided signature
        try:
            signature_fields = parse_signature_string(signature)
        except Exception as e:
            click.echo(click.style(f"Error parsing signature: {e}", fg="red"))
            raise click.Abort()

    # Prompt for model
    if model is None:
        model = prompt_model(default="openai/gpt-5-mini")

    # Parse model string
    model_info = parse_model_string(model)
    provider = model_info['provider']
    provider_display = get_provider_display_name(provider)

    # Handle API key for non-local models
    api_key_value = None
    api_key_env_var = None

    if not is_local_model(provider):
        # Detect existing API key
        detected_key, env_var_name = detect_api_key(provider)
        api_key_env_var = env_var_name

        # Use provided API key or prompt for one
        if api_key is not None:
            # API key was provided via CLI
            api_key_value = api_key
        else:
            # Prompt for API key (will ask to confirm if detected, or enter new one)
            api_key_value = prompt_api_key(provider_display, env_var_name, detected_key)
    else:
        # For local models, optionally prompt for api_base
        click.echo(click.style(f"Detected local model provider: {provider_display}", fg="green"))

    # Generate model configuration
    model_config_dict = generate_model_config(model, api_key_value)

    click.echo()
    click.echo(f"Creating new DSPy project: {click.style(project_name, fg='green', bold=True)}")
    click.echo(f"  Package name: {package_name}")
    click.echo(f"  Initial program: {program_name}")
    click.echo(f"  Module type: {MODULE_TYPES[module_type]['display_name']}")
    click.echo(f"  Signature: {signature}")
    click.echo(f"  Model: {model}")
    click.echo()

    try:
        # Create directory structure
        _create_directory_structure(project_path, package_name, program_name)

        # Create configuration files with model config
        _create_config_files(
            project_path,
            project_name,
            program_name,
            package_name,
            model_config_dict,
            api_key_value,
            api_key_env_var
        )

        # Create Python code files with module type
        _create_code_files(
            project_path,
            package_name,
            program_name,
            signature,
            signature_fields,
            module_type
        )

        # Initialize git repository
        _initialize_git(project_path)

        click.echo(click.style("✓ Project created successfully!", fg="green"))
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  cd {project_name}")
        if not api_key_value and not is_local_model(provider):
            click.echo(f"  # Add your {api_key_env_var} to .env")
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

def _create_config_files(project_path, project_name, program_name, package_name, model_config_dict, api_key_value, api_key_env_var):
    """Create configuration files from templates."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent.parent

    # Read and write pyproject.toml
    pyproject_template = (templates_dir / "pyproject.toml.template").read_text()
    pyproject_content = pyproject_template.format(project_name=project_name)
    (project_path / "pyproject.toml").write_text(pyproject_content)
    click.echo(f"  Created: {project_name}/pyproject.toml")

    # Generate model alias (e.g., "openai:gpt-4o-mini" from "openai/gpt-4o-mini")
    model_full = model_config_dict['model']
    model_alias = model_full.replace('/', ':')

    # Format model config as YAML with proper indentation
    model_config_lines = []
    for key, value in model_config_dict.items():
        if isinstance(value, str):
            model_config_lines.append(f"      {key}: {value}")
        else:
            model_config_lines.append(f"      {key}: {value}")
    model_config_yaml = "\n".join(model_config_lines)

    # Read and write dspy.config.yaml
    config_template = (templates_dir / "dspy.config.yaml.template").read_text()
    config_content = config_template.format(
        app_id=project_name,
        default_model_alias=model_alias,
        model_alias=model_alias,
        model_config=model_config_yaml
    )
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

    # Generate .env content
    if api_key_env_var:
        if api_key_value:
            # User provided API key
            api_key_config = f"# {api_key_env_var} for your LLM provider\n{api_key_env_var}={api_key_value}"
        else:
            # User skipped API key, write placeholder
            api_key_config = f"# {api_key_env_var} for your LLM provider\n# Add your API key here\n{api_key_env_var}="
    else:
        # Local model, no API key needed
        api_key_config = "# No API key required for local models"

    # Read and write .env
    env_template = (templates_dir / "env.template").read_text()
    env_content = env_template.format(api_key_config=api_key_config)
    (project_path / ".env").write_text(env_content)
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

def _create_code_files(project_path, package_name, program_name, signature, signature_fields, module_type):
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

    # Get module info from constants
    module_info = MODULE_TYPES[module_type]

    # Determine module class name based on module type
    if module_type in ["CoT", "ChainOfThought"]:
        class_suffix = "CoT"
    elif module_type in ["PoT", "ProgramOfThought"]:
        class_suffix = "PoT"
    elif module_type == "ReAct":
        class_suffix = "ReAct"
    elif module_type == "Refine":
        class_suffix = "Refine"
    elif module_type == "MultiChainComparison":
        class_suffix = "MCC"
    else:
        class_suffix = "Predict"

    module_class = f"{to_class_name(program_name)}{class_suffix}"
    module_file = f"{file_name}_{module_info['suffix']}"

    # Build forward method components from signature fields
    # If no signature was provided, use default fields (question: str -> answer: str)
    fields_for_forward = signature_fields if signature_fields else {
        'inputs': [{'name': 'question', 'type': 'str'}],
        'outputs': [{'name': 'answer', 'type': 'str'}]
    }
    forward_components = build_forward_components(fields_for_forward)

    # Use the appropriate module template
    module_template = (templates_dir / module_info['template']).read_text()
    module_content = module_template.format(
        package_name=package_name,
        program_name=file_name,
        signature_class=signature_class,
        class_name=module_class,
        forward_params=forward_components['forward_params'],
        forward_kwargs=forward_components['forward_kwargs']
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
