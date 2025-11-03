"""Tests for serve command validation."""

import subprocess

import pytest
from click.testing import CliRunner

from dspy_cli.cli import main


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestServeValidation:
    """Tests for serve command input validation."""

    def test_invalid_port_too_high(self, runner):
        """Test that port > 65535 is rejected."""
        result = runner.invoke(main, ["serve", "--port", "99999"])
        assert result.exit_code != 0
        assert "range" in result.output.lower()

    def test_invalid_port_zero(self, runner):
        """Test that port 0 is rejected."""
        result = runner.invoke(main, ["serve", "--port", "0"])
        assert result.exit_code != 0
        assert "range" in result.output.lower()

    def test_invalid_port_negative(self, runner):
        """Test that negative port is rejected."""
        result = runner.invoke(main, ["serve", "--port", "-1"])
        assert result.exit_code != 0

    def test_python_as_directory_rejected(self, runner):
        """Test that directory path for --python is rejected."""
        result = runner.invoke(main, ["serve", "--python", "/tmp"])
        assert result.exit_code != 0
        assert "directory" in result.output.lower()

    def test_non_python_executable_rejected(self):
        """Test that non-Python executables are rejected."""
        result = subprocess.run(
            ["dspy-cli", "serve", "--python", "/bin/sh"],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0

    def test_system_flag_exists(self, runner):
        """Test that --system flag is recognized."""
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--system" in result.output

    def test_python_flag_exists(self, runner):
        """Test that --python flag is recognized."""
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--python" in result.output
