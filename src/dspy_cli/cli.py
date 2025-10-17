"""Main CLI entry point for dspy-cli."""

import click

from dspy_cli.commands.new import new
from dspy_cli.commands.serve import serve


@click.group()
@click.version_option()
def main():
    """dspy-cli: A CLI tool for creating and serving DSPy projects.

    Inspired by Ruby on Rails, dspy-cli provides convention-based
    scaffolding and serving for DSPy applications.
    """
    pass


# Register commands
main.add_command(new)
main.add_command(serve)


if __name__ == "__main__":
    main()
