"""Command to generate new components in existing DSPy projects."""

from pathlib import Path

import click

from dspy_cli.config.validator import find_package_directory, validate_project_structure
from dspy_cli.utils.signature_utils import parse_signature_string, to_class_name, build_forward_components
from dspy_cli.utils.constants import MODULE_TYPES

GATEWAY_TYPES = {
    "api": {
        "template": "gateway_api.py.template",
        "suffix": "gateway",
        "description": "HTTP request/response transformation",
    },
    "cron": {
        "template": "gateway_cron.py.template",
        "suffix": "cron_gateway",
        "description": "Scheduled background execution",
    },
}


@click.group(name="generate")
def generate():
    """Generate new components in an existing DSPy project.

    Use 'g' as a shorthand alias for 'generate'.

    Example:
        dspy-cli generate scaffold my_program
        dspy-cli g scaffold my_program -m CoT -s "question -> answer"
    """
    pass


@generate.command()
@click.argument("program_name")
@click.option(
    "--module",
    "-m",
    default="Predict",
    help=f"DSPy module type to use. Available: {', '.join(MODULE_TYPES.keys())} (default: Predict)",
)
@click.option(
    "--signature",
    "-s",
    default=None,
    help='Inline signature string (e.g., "question -> answer" or "context: list[str], question -> answer")',
)
def scaffold(program_name, module, signature):
    """Generate a new DSPy program with signature and module files.

    Creates:
    - A signature file in src/<package>/signatures/
    - A module file in src/<package>/modules/

    Examples:
        # Basic scaffold with default Predict module
        dspy-cli g scaffold categorizer

        # Scaffold with ChainOfThought
        dspy-cli g scaffold categorizer -m CoT

        # Scaffold with custom signature
        dspy-cli g scaffold qa -m CoT -s "question -> answer"

        # Complex signature with types
        dspy-cli g scaffold search -s "query, context: list[str] -> answer, confidence: float"
    """
    click.echo(f"Generating scaffold for program: {program_name}")
    click.echo()

    # Validate we're in a DSPy project
    if not validate_project_structure():
        click.echo(click.style("Error: Not in a valid DSPy project directory", fg="red"))
        click.echo()
        click.echo("Make sure you're in a directory created with 'dspy-cli new'")
        click.echo("Required files: dspy.config.yaml, src/")
        raise click.Abort()

    # Validate module type
    if module not in MODULE_TYPES:
        click.echo(click.style(f"Error: Unknown module type '{module}'", fg="red"))
        click.echo()
        click.echo(f"Available module types: {', '.join(MODULE_TYPES.keys())}")
        raise click.Abort()

    # Find package directory
    package_dir = find_package_directory()
    if not package_dir:
        click.echo(click.style("Error: Could not find package in src/", fg="red"))
        raise click.Abort()

    package_name = package_dir.name

    # Convert dashes to underscores for valid Python identifier
    original_program_name = program_name
    program_name = program_name.replace("-", "_")

    if original_program_name != program_name:
        click.echo(f"  Note: Converted '{original_program_name}' to '{program_name}' for Python compatibility")

    # Validate program name is valid Python identifier
    if not program_name.replace("_", "").isalnum() or program_name[0].isdigit():
        click.echo(click.style(f"Error: Program name '{program_name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    # Parse signature if provided
    signature_fields = None
    if signature:
        signature_fields = parse_signature_string(signature)
        click.echo(f"  Signature: {signature}")

    click.echo(f"  Module type: {module}")
    click.echo(f"  Package: {package_name}")
    click.echo()

    try:
        # Create signature file
        _create_signature_file(package_dir, program_name, signature, signature_fields)

        # Create module file
        _create_module_file(package_dir, package_name, program_name, module, signature_fields)

        click.echo(click.style("✓ Scaffold created successfully!", fg="green"))
        click.echo()
        click.echo("Files created:")
        file_name_base = program_name.lower()
        click.echo(f"  • signatures/{file_name_base}.py")
        click.echo(f"  • modules/{file_name_base}_{MODULE_TYPES[module]['suffix']}.py")

    except Exception as e:
        click.echo(click.style(f"Error creating scaffold: {e}", fg="red"))
        raise click.Abort()


@generate.command()
@click.argument("program_name")
@click.option(
    "--signature",
    "-s",
    default=None,
    help='Inline signature string (e.g., "question -> answer" or "context: list[str], question -> answer")',
)
def signature(program_name, signature):
    """Generate a new DSPy signature file only.

    Creates a signature file in src/<package>/signatures/ without creating a module.

    Examples:
        # Create signature with default fields (question -> answer)
        dspy-cli g signature my_sig

        # Create signature with custom fields
        dspy-cli g signature categorizer -s "post -> tags: list[str]"

        # Complex signature with multiple inputs and outputs
        dspy-cli g signature qa -s "context: list[str], question -> answer, confidence: float"
    """
    click.echo(f"Generating signature: {program_name}")
    click.echo()

    # Validate we're in a DSPy project
    if not validate_project_structure():
        click.echo(click.style("Error: Not in a valid DSPy project directory", fg="red"))
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

    # Convert dashes to underscores for valid Python identifier
    original_program_name = program_name
    program_name = program_name.replace("-", "_")

    if original_program_name != program_name:
        click.echo(f"  Note: Converted '{original_program_name}' to '{program_name}' for Python compatibility")

    # Validate program name is valid Python identifier
    if not program_name.replace("_", "").isalnum() or program_name[0].isdigit():
        click.echo(click.style(f"Error: Program name '{program_name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    # Parse signature if provided
    signature_fields = None
    if signature:
        signature_fields = parse_signature_string(signature)
        click.echo(f"  Signature: {signature}")
    else:
        click.echo("  Using default signature (question: str -> answer: str)")

    click.echo(f"  Package: {package_name}")
    click.echo()

    try:
        # Create signature file
        _create_signature_file(package_dir, program_name, signature, signature_fields)

        click.echo(click.style("✓ Signature created successfully!", fg="green"))
        click.echo()
        file_name = program_name.lower()
        click.echo(f"File created: signatures/{file_name}.py")

    except Exception as e:
        click.echo(click.style(f"Error creating signature: {e}", fg="red"))
        raise click.Abort()


@generate.command()
@click.argument("program_name")
@click.option(
    "--module",
    "-m",
    default="Predict",
    help=f"DSPy module type to use. Available: {', '.join(MODULE_TYPES.keys())} (default: Predict)",
)
def module(program_name, module):
    """Generate a new DSPy module file only.

    Creates a module file in src/<package>/modules/ with an inline signature.
    The module uses a placeholder signature: "question: str -> answer: str"

    Examples:
        # Create basic Predict module
        dspy-cli g module my_module

        # Create ChainOfThought module
        dspy-cli g module analyzer -m CoT

        # Create ReAct module
        dspy-cli g module agent -m ReAct
    """
    click.echo(f"Generating module: {program_name}")
    click.echo()

    # Validate we're in a DSPy project
    if not validate_project_structure():
        click.echo(click.style("Error: Not in a valid DSPy project directory", fg="red"))
        click.echo()
        click.echo("Make sure you're in a directory created with 'dspy-cli new'")
        click.echo("Required files: dspy.config.yaml, src/")
        raise click.Abort()

    # Validate module type
    if module not in MODULE_TYPES:
        click.echo(click.style(f"Error: Unknown module type '{module}'", fg="red"))
        click.echo()
        click.echo(f"Available module types: {', '.join(MODULE_TYPES.keys())}")
        raise click.Abort()

    # Find package directory
    package_dir = find_package_directory()
    if not package_dir:
        click.echo(click.style("Error: Could not find package in src/", fg="red"))
        raise click.Abort()

    package_name = package_dir.name

    # Convert dashes to underscores for valid Python identifier
    original_program_name = program_name
    program_name = program_name.replace("-", "_")

    if original_program_name != program_name:
        click.echo(f"  Note: Converted '{original_program_name}' to '{program_name}' for Python compatibility")

    # Validate program name is valid Python identifier
    if not program_name.replace("_", "").isalnum() or program_name[0].isdigit():
        click.echo(click.style(f"Error: Program name '{program_name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    click.echo(f"  Module type: {module}")
    click.echo(f"  Package: {package_name}")
    click.echo("  Using inline signature: \"question: str -> answer: str\"")
    click.echo()

    try:
        # Create module file with inline signature
        _create_module_file_inline(package_dir, package_name, program_name, module)

        click.echo(click.style("✓ Module created successfully!", fg="green"))
        click.echo()
        file_name_base = program_name.lower()
        click.echo(f"File created: modules/{file_name_base}_{MODULE_TYPES[module]['suffix']}.py")

    except Exception as e:
        click.echo(click.style(f"Error creating module: {e}", fg="red"))
        raise click.Abort()


@generate.command()
@click.argument("name")
@click.option(
    "--type",
    "-t",
    "gateway_type",
    default="api",
    help=f"Gateway type. Available: {', '.join(GATEWAY_TYPES.keys())} (default: api)",
)
@click.option(
    "--path",
    "-p",
    default=None,
    help="Custom HTTP path for API gateway (default: /{Name})",
)
@click.option(
    "--schedule",
    "-s",
    default="0 * * * *",
    help="Cron schedule for cron gateway (default: hourly)",
)
@click.option(
    "--public/--private",
    default=False,
    help="Whether the endpoint requires authentication (default: private/requires auth)",
)
def gateway(name, gateway_type, path, schedule, public):
    """Generate a new gateway file.

    Creates a gateway file in src/<package>/gateways/ for transforming
    HTTP requests/responses or scheduling background jobs.

    Examples:
        # Create API gateway with default settings
        dspy-cli g gateway webhook

        # Create API gateway with custom path
        dspy-cli g gateway slack -p /webhooks/slack

        # Create public API gateway (no auth required)
        dspy-cli g gateway health --public

        # Create cron gateway for scheduled execution
        dspy-cli g gateway moderator -t cron -s "*/5 * * * *"
    """
    click.echo(f"Generating gateway: {name}")
    click.echo()

    # Validate we're in a DSPy project
    if not validate_project_structure():
        click.echo(click.style("Error: Not in a valid DSPy project directory", fg="red"))
        click.echo()
        click.echo("Make sure you're in a directory created with 'dspy-cli new'")
        click.echo("Required files: dspy.config.yaml, src/")
        raise click.Abort()

    # Validate gateway type
    if gateway_type not in GATEWAY_TYPES:
        click.echo(click.style(f"Error: Unknown gateway type '{gateway_type}'", fg="red"))
        click.echo()
        click.echo(f"Available gateway types: {', '.join(GATEWAY_TYPES.keys())}")
        raise click.Abort()

    # Find package directory
    package_dir = find_package_directory()
    if not package_dir:
        click.echo(click.style("Error: Could not find package in src/", fg="red"))
        raise click.Abort()

    package_name = package_dir.name

    # Convert dashes to underscores for valid Python identifier
    original_name = name
    name = name.replace("-", "_")

    if original_name != name:
        click.echo(f"  Note: Converted '{original_name}' to '{name}' for Python compatibility")

    # Validate name is valid Python identifier
    if not name.replace("_", "").isalnum() or name[0].isdigit():
        click.echo(click.style(f"Error: Gateway name '{name}' is not a valid Python identifier", fg="red"))
        raise click.Abort()

    gateway_info = GATEWAY_TYPES[gateway_type]
    click.echo(f"  Type: {gateway_type} ({gateway_info['description']})")
    click.echo(f"  Package: {package_name}")

    if gateway_type == "api":
        effective_path = path if path else f"/{to_class_name(name)}"
        click.echo(f"  Path: {effective_path}")
        click.echo(f"  Auth required: {not public}")
    else:
        click.echo(f"  Schedule: {schedule}")

    click.echo()

    try:
        _create_gateway_file(package_dir, name, gateway_type, path, schedule, public)

        click.echo(click.style("✓ Gateway created successfully!", fg="green"))
        click.echo()
        file_name = f"{name.lower()}_{gateway_info['suffix']}.py"
        click.echo(f"File created: gateways/{file_name}")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Edit the gateway file to implement your transformation logic")
        click.echo("  2. Add 'gateway = YourGateway' to your module class")

    except Exception as e:
        click.echo(click.style(f"Error creating gateway: {e}", fg="red"))
        raise click.Abort()


def _create_gateway_file(package_dir, name, gateway_type, path, schedule, public):
    """Create a gateway file."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent
    gateway_info = GATEWAY_TYPES[gateway_type]

    # Ensure gateways directory exists
    gateways_dir = package_dir / "gateways"
    gateways_dir.mkdir(exist_ok=True)

    # Create __init__.py if it doesn't exist
    init_file = gateways_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Gateway definitions."""\n')

    # Generate file path
    file_name = f"{name.lower()}_{gateway_info['suffix']}.py"
    gateway_file_path = gateways_dir / file_name

    # Check if file already exists
    if gateway_file_path.exists():
        click.echo(click.style(f"Warning: Gateway file already exists: {gateway_file_path}", fg="yellow"))
        if not click.confirm("Overwrite?"):
            raise click.Abort()

    # Generate class name
    class_name = to_class_name(name) + "Gateway"
    module_name = to_class_name(name)

    # Default path if not specified
    effective_path = path if path else f"/{module_name}"

    # Load and format template
    template = (templates_dir / gateway_info["template"]).read_text()
    content = template.format(
        module_name=module_name,
        class_name=class_name,
        path=effective_path,
        schedule=schedule,
        requires_auth=str(not public),
    )

    gateway_file_path.write_text(content)
    click.echo(f"  Created: gateways/{file_name}")


def _create_signature_file(package_dir, program_name, signature_str, signature_fields):
    """Create a signature file for the program."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent
    # Convert to lowercase/snake_case for filename
    file_name = program_name.lower()
    signature_file_path = package_dir / "signatures" / f"{file_name}.py"

    # Check if file already exists
    if signature_file_path.exists():
        click.echo(click.style(f"Warning: Signature file already exists: {signature_file_path}", fg="yellow"))
        if not click.confirm("Overwrite?"):
            raise click.Abort()

    # Generate signature content
    signature_class = to_class_name(program_name) + "Signature"

    if signature_fields:
        # Generate from parsed signature
        content = f'"""Signature definitions for {file_name}."""\n\nimport dspy\n\n'
        content += f"class {signature_class}(dspy.Signature):\n"
        content += '    """\n    """\n\n'

        # Add input fields
        for field in signature_fields['inputs']:
            content += f"    {field['name']}: {field['type']} = dspy.InputField(desc=\"\")\n"

        # Add output fields
        for field in signature_fields['outputs']:
            content += f"    {field['name']}: {field['type']} = dspy.OutputField(desc=\"\")\n"
    else:
        # Use default template
        signature_template = (templates_dir / "signature.py.template").read_text()
        content = signature_template.format(
            program_name=file_name,  # Use lowercase for docstring
            class_name=signature_class
        )

    signature_file_path.write_text(content)
    click.echo(f"  Created: signatures/{file_name}.py")


def _create_module_file(package_dir, package_name, program_name, module_type, signature_fields):
    """Create a module file for the program."""
    from dspy_cli.templates import code_templates

    templates_dir = Path(code_templates.__file__).parent
    module_info = MODULE_TYPES[module_type]
    # Convert to lowercase/snake_case for filename
    file_name_base = program_name.lower()
    module_file = f"{file_name_base}_{module_info['suffix']}"
    module_file_path = package_dir / "modules" / f"{module_file}.py"

    # Check if file already exists
    if module_file_path.exists():
        click.echo(click.style(f"Warning: Module file already exists: {module_file_path}", fg="yellow"))
        if not click.confirm("Overwrite?"):
            raise click.Abort()

    # Generate class name
    signature_class = to_class_name(program_name) + "Signature"

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

    # Build forward method components from signature fields
    # If no signature was provided, use default fields (question: str -> answer: str)
    fields_for_forward = signature_fields if signature_fields else {
        'inputs': [{'name': 'question', 'type': 'str'}],
        'outputs': [{'name': 'answer', 'type': 'str'}]
    }
    forward_components = build_forward_components(fields_for_forward)

    # Load and format template
    module_template = (templates_dir / module_info['template']).read_text()
    # Use lowercase filename for import
    signature_file_name = program_name.lower()
    content = module_template.format(
        package_name=package_name,
        program_name=signature_file_name,  # Use lowercase for import path
        signature_class=signature_class,
        class_name=module_class,
        forward_params=forward_components['forward_params'],
        forward_kwargs=forward_components['forward_kwargs']
    )

    module_file_path.write_text(content)
    click.echo(f"  Created: modules/{module_file}.py")


def _create_module_file_inline(package_dir, package_name, program_name, module_type):
    """Create a module file with inline signature (no signature import)."""
    module_info = MODULE_TYPES[module_type]
    # Convert to lowercase/snake_case for filename
    file_name_base = program_name.lower()
    module_file = f"{file_name_base}_{module_info['suffix']}"
    module_file_path = package_dir / "modules" / f"{module_file}.py"

    # Check if file already exists
    if module_file_path.exists():
        click.echo(click.style(f"Warning: Module file already exists: {module_file_path}", fg="yellow"))
        if not click.confirm("Overwrite?"):
            raise click.Abort()

    # Determine module class name based on module type
    if module_type in ["CoT", "ChainOfThought"]:
        class_suffix = "CoT"
        predictor_class = "dspy.ChainOfThought"
    elif module_type in ["PoT", "ProgramOfThought"]:
        class_suffix = "PoT"
        predictor_class = "dspy.ProgramOfThought"
    elif module_type == "ReAct":
        class_suffix = "ReAct"
        predictor_class = "dspy.ReAct"
    elif module_type == "Refine":
        class_suffix = "Refine"
        predictor_class = "dspy.Refine"
    elif module_type == "MultiChainComparison":
        class_suffix = "MCC"
        predictor_class = "dspy.MultiChainComparison"
    else:
        class_suffix = "Predict"
        predictor_class = "dspy.Predict"

    module_class = f"{to_class_name(program_name)}{class_suffix}"

    # Use default signature fields for forward method
    default_fields = {
        'inputs': [{'name': 'question', 'type': 'str'}],
        'outputs': [{'name': 'answer', 'type': 'str'}]
    }
    forward_components = build_forward_components(default_fields)

    # Generate module content with inline signature
    content = f'''import dspy


class {module_class}(dspy.Module):

    def __init__(self):
        super().__init__()
        self.predictor = {predictor_class}("question: str -> answer: str")

    def forward(self, {forward_components['forward_params']}) -> dspy.Prediction:
        return self.predictor({forward_components['forward_kwargs']})
'''

    module_file_path.write_text(content)
    click.echo(f"  Created: modules/{module_file}.py")


# Create alias for the group
g = generate
