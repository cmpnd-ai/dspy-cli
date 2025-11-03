"""Main CLI entry point for dspy-cli."""

import click

from dspy_cli.commands.new import new
from dspy_cli.commands.serve import serve
from dspy_cli.commands.generate import generate


@click.group()
@click.version_option()
def main():
    """dspy-cli: A CLI tool for creating and serving DSPy projects.

    dspy-cli provides convention-based scaffolding and serving for 
    DSPy applications.
    """
    pass


# Register commands
main.add_command(new)
main.add_command(serve)
main.add_command(generate)
main.add_command(generate, name='g')  # Alias for generate
main.add_command(serve, name='s')  # Alias for serve


if __name__ == "__main__":
    main()
