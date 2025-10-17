"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from dspy_cli.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


def test_cli_help(runner):
    """Test that the CLI help command works."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "dspy-cli" in result.output
    assert "new" in result.output
    assert "serve" in result.output


def test_new_command_help(runner):
    """Test that the new command help works."""
    result = runner.invoke(main, ["new", "--help"])
    assert result.exit_code == 0
    assert "Create a new DSPy project" in result.output


def test_serve_command_help(runner):
    """Test that the serve command help works."""
    result = runner.invoke(main, ["serve", "--help"])
    assert result.exit_code == 0
    assert "HTTP API server" in result.output
