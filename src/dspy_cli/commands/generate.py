"""Command to generate new components in existing DSPy projects."""

from pathlib import Path

import click

from dspy_cli.config.validator import find_package_directory, validate_project_structure
from dspy_cli.utils.signature_utils import parse_signature_string, to_class_name


# Map of module type aliases to their canonical names and template files
MODULE_TYPES = {
    "Predict": {"template": "module_predict.py.template", "suffix": "predict"},
    "ChainOfThought": {"template": "module_chain_of_thought.py.template", "suffix": "cot"},
    "CoT": {"template": "module_chain_of_thought.py.template", "suffix": "cot"},
    "ProgramOfThought": {"template": "module_program_of_thought.py.template", "suffix": "pot"},
    "PoT": {"template": "module_program_of_thought.py.template", "suffix": "pot"},
    "ReAct": {"template": "module_react.py.template", "suffix": "react"},
    "MultiChainComparison": {"template": "module_multi_chain_comparison.py.template", "suffix": "mcc"},
    "Refine": {"template": "module_refine.py.template", "suffix": "refine"},
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

    # Load and format template
    module_template = (templates_dir / module_info['template']).read_text()
    # Use lowercase filename for import
    signature_file_name = program_name.lower()
    content = module_template.format(
        package_name=package_name,
        program_name=signature_file_name,  # Use lowercase for import path
        signature_class=signature_class,
        class_name=module_class
    )

    module_file_path.write_text(content)
    click.echo(f"  Created: modules/{module_file}.py")


# Create alias for the group
g = generate
