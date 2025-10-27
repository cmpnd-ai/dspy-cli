"""Shared utilities for signature parsing and manipulation."""

import click


def parse_signature_string(signature_str):
    """Parse a signature string to extract field information.

    Args:
        signature_str: String like "question -> answer" or "context: list[str], question -> answer"

    Returns:
        Dictionary with 'inputs' and 'outputs' lists of field info dicts
    """
    try:
        # Use DSPy's make_signature to parse the string
        import dspy
        sig = dspy.Signature(signature_str)

        inputs = []
        for field_name, field_info in sig.input_fields.items():
            field_type = field_info.annotation if hasattr(field_info, 'annotation') else str
            type_str = type_to_string(field_type)
            inputs.append({
                'name': field_name,
                'type': type_str,
                'type_annotation': field_type
            })

        outputs = []
        for field_name, field_info in sig.output_fields.items():
            field_type = field_info.annotation if hasattr(field_info, 'annotation') else str
            type_str = type_to_string(field_type)
            outputs.append({
                'name': field_name,
                'type': type_str,
                'type_annotation': field_type
            })

        return {'inputs': inputs, 'outputs': outputs}
    except Exception as e:
        click.echo(click.style(f"Error parsing signature string: {e}", fg="red"))
        raise click.Abort()


def type_to_string(type_obj):
    """Convert a type object to a string representation.

    Preserves the dspy. prefix for DSPy types like dspy.Image, dspy.Audio, etc.
    """
    # Check if it's a generic type (e.g., List[str], Dict[str, int])
    if hasattr(type_obj, '__origin__'):
        # Handle generic types like list[str], dict[str, int], etc.
        return str(type_obj).replace('typing.', '')
    elif hasattr(type_obj, '__name__'):
        # Check if this is a dspy type (module starts with 'dspy')
        if hasattr(type_obj, '__module__') and type_obj.__module__.startswith('dspy'):
            return f"dspy.{type_obj.__name__}"
        return type_obj.__name__
    else:
        # Fallback to string representation
        return str(type_obj).replace('typing.', '')


def to_class_name(snake_case_name):
    """Convert snake_case to PascalCase for class names."""
    return "".join(word.capitalize() for word in snake_case_name.split("_"))
