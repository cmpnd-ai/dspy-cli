"""Interactive prompt utilities for DSPy CLI."""

import click
from dspy_cli.utils.constants import UNIQUE_MODULE_TYPES, MODULE_TYPES
from dspy_cli.utils.signature_utils import parse_signature_string


def prompt_project_name(default: str | None = None) -> str:
    """Prompt user for project name.

    Args:
        default: Default value to show in prompt

    Returns:
        Project name entered by user
    """
    default_text = default or "my-project"

    project_name = click.prompt(
        click.style("What is your project name?", fg="cyan"),
        default=default_text,
        type=str
    )

    return project_name.strip()


def prompt_setup_first_program() -> bool:
    """Ask user if they want to specify their first program.

    Returns:
        True if user wants to customize, False to use defaults
    """
    return click.confirm(
        click.style("Would you like to specify your first program?", fg="cyan"),
        default=True
    )


def prompt_program_name(default: str | None = None) -> str:
    """Prompt user for their first program name.

    Args:
        default: Default value to show in prompt

    Returns:
        Program name entered by user
    """
    if not default:
        default = "my_program"

    program_name = click.prompt(
        click.style("What is the name of your first DSPy program?", fg="cyan"),
        default=default,
        type=str
    )

    return program_name.strip()


def prompt_module_type(default: str | None = None) -> str:
    """Prompt user to select a module type.

    Args:
        default: Default module type (defaults to "Predict")

    Returns:
        Selected module type
    """
    if not default:
        default = "Predict"

    click.echo(click.style("Choose a module type:", fg="cyan"))

    # Display module options with descriptions
    for i, module_type in enumerate(UNIQUE_MODULE_TYPES, 1):
        module_info = MODULE_TYPES[module_type]
        display = module_info['display_name']
        desc = module_info['description']

        if module_type == default:
            click.echo(f"  {i}. {click.style(display, fg='green', bold=True)} - {desc} (default)")
        else:
            click.echo(f"  {i}. {display} - {desc}")

    # Get user selection
    while True:
        choice = click.prompt(
            "Enter number or name",
            default="1" if default == "Predict" else default,
            type=str
        )

        # Try to parse as number
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(UNIQUE_MODULE_TYPES):
                return UNIQUE_MODULE_TYPES[choice_num - 1]
        except ValueError:
            # Not a number, try as module name
            # Check if it matches any module type (case-insensitive)
            for module_type in MODULE_TYPES.keys():
                if choice.lower() == module_type.lower():
                    # Return the canonical name (not the alias)
                    if module_type in UNIQUE_MODULE_TYPES:
                        return module_type
                    # If it's an alias, return the canonical version
                    elif module_type == "CoT":
                        return "ChainOfThought"
                    elif module_type == "PoT":
                        return "ProgramOfThought"

        click.echo(click.style("Invalid choice. Please enter a number (1-6) or module name.", fg="red"))


def prompt_signature_guided() -> dict:
    """Prompt user to build a signature field-by-field.

    Returns:
        Signature fields dict with 'inputs' and 'outputs' lists
    """
    click.echo(click.style("Let's build your signature step by step.", fg="cyan"))

    inputs = []
    outputs = []

    # Prompt for input fields
    click.echo(click.style("Input fields:", fg="yellow"))
    while True:
        field_name = click.prompt("  Field name (or press Enter to finish inputs)", default="", show_default=False)
        if not field_name:
            break

        field_type = click.prompt("  Field type", default="str")
        inputs.append({'name': field_name.strip(), 'type': field_type.strip()})

    if not inputs:
        # Default to question:str if no inputs provided
        inputs.append({'name': 'question', 'type': 'str'})
        click.echo(click.style("  Using default input: question:str", fg="yellow"))

    # Prompt for output fields
    click.echo(click.style("Output fields:", fg="yellow"))
    while True:
        field_name = click.prompt("  Field name (or press Enter to finish outputs)", default="", show_default=False)
        if not field_name:
            break

        field_type = click.prompt("  Field type", default="str")
        outputs.append({'name': field_name.strip(), 'type': field_type.strip()})

    if not outputs:
        # Default to answer:str if no outputs provided
        outputs.append({'name': 'answer', 'type': 'str'})
        click.echo(click.style("  Using default output: answer:str", fg="yellow"))
    return {'inputs': inputs, 'outputs': outputs}


def prompt_signature(default: str | None = None) -> tuple[str, dict | None]:
    """Prompt user for signature string with option for guided input.

    Args:
        default: Default signature string

    Returns:
        Tuple of (signature_string, signature_fields_dict or None)
        If user enters '?' or 'help', enters guided mode and returns (generated_string, fields_dict)
    """
    if not default:
        default = "question:str -> answer:str"

    click.echo(click.style("Enter your signature or type '?' for guided input:", fg="cyan"))
    click.echo(click.style("  Examples: 'question -> answer', 'post:str -> tags:list[str], category:str'", fg="bright_black"))

    signature = click.prompt(
        "Signature",
        default=default,
        type=str
    )

    # Strip both whitespace and optional quotes
    signature = signature.strip().strip('"').strip("'")

    # Check for help/guided mode
    if signature.lower() in ['?', 'help', 'guide', 'guided']:
        signature_fields = prompt_signature_guided()

        # Build signature string from fields
        input_parts = [f"{f['name']}:{f['type']}" if f['type'] != 'str' else f['name']
                      for f in signature_fields['inputs']]
        output_parts = [f"{f['name']}:{f['type']}" if f['type'] != 'str' else f['name']
                       for f in signature_fields['outputs']]

        signature_str = f"{', '.join(input_parts)} -> {', '.join(output_parts)}"
        click.echo(click.style(f"Generated signature: {signature_str}", fg="green"))
        return signature_str, signature_fields

    # Try to parse the signature
    try:
        signature_fields = parse_signature_string(signature)
        return signature, signature_fields
    except Exception as e:
        click.echo(click.style(f"Warning: Could not parse signature: {e}", fg="yellow"))
        click.echo(click.style("Using default signature instead.", fg="yellow"))
        return default, None


def prompt_model(default: str | None = None) -> str:
    """Prompt user for model string.

    Args:
        default: Default model string

    Returns:
        Model string (e.g., "anthropic/claude-sonnet-4-5")
    """
    if not default:
        default = "openai/gpt-5-mini"

    click.echo(click.style("Enter your model (LiteLLM format):", fg="cyan"))
    click.echo(click.style("  Examples: 'anthropic/claude-sonnet-4-5', 'openai/gpt-4o', 'ollama/llama2'", fg="bright_black"))

    model = click.prompt(
        "Model",
        default=default,
        type=str
    )

    return model.strip()


def prompt_api_key(provider_display: str, env_var_name: str, detected_key: str | None = None) -> str | None:
    """Prompt user for API key.

    Args:
        provider_display: User-friendly provider name (e.g., "Anthropic")
        env_var_name: Environment variable name (e.g., "ANTHROPIC_API_KEY")
        detected_key: Pre-detected API key from environment (if any)

    Returns:
        API key entered by user, or None if skipped
    """
    if detected_key:
        # Mask the key for display
        if len(detected_key) > 8:
            masked_key = detected_key[:8] + "..." + detected_key[-4:]
        else:
            masked_key = "***"

        click.echo(click.style(f"Found {env_var_name} in environment: {masked_key}", fg="green"))

        # Ask if they want to use the detected key or enter a new one
        use_detected = click.confirm(
            "Proceed with this API key?",
            default=True
        )

        if use_detected:
            return detected_key
        # If they don't want to use the detected key, fall through to prompt for a new one

    # Prompt for API key
    click.echo(click.style(f"Enter your {provider_display} API key:", fg="cyan"))
    click.echo(click.style(f"  (This will be stored in .env as {env_var_name})", fg="bright_black"))
    click.echo(click.style("  Press Enter to skip and set it manually later", fg="bright_black"))

    api_key = click.prompt(
        f"{env_var_name}",
        default="",
        show_default=False,
        hide_input=True,  # Hide API key input
        type=str
    )

    if not api_key:
        return None

    return api_key.strip()


def prompt_api_base(provider: str) -> str | None:
    """Prompt user for custom API base URL (for local models).

    Args:
        provider: Provider name

    Returns:
        API base URL or None
    """
    click.echo(click.style(f"Enter custom API base URL for {provider} (optional):", fg="cyan"))
    click.echo(click.style("  Example for Ollama: 'http://localhost:11434'", fg="bright_black"))
    click.echo(click.style("  Press Enter to skip", fg="bright_black"))

    api_base = click.prompt(
        "API Base URL",
        default="",
        show_default=False,
        type=str
    )

    if not api_base:
        return None

    return api_base.strip()
