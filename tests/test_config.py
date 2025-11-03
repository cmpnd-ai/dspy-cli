"""Tests for configuration loading."""

import pytest

from dspy_cli.config import load_config, ConfigError


def test_load_config_missing_file(tmp_path):
    """Test that loading config from missing file raises error."""
    config_path = tmp_path / "nonexistent.yaml"

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_path)

    assert "not found" in str(exc_info.value)


def test_load_config_empty_file(tmp_path):
    """Test that loading empty config file raises error."""
    config_path = tmp_path / "dspy.config.yaml"
    config_path.write_text("")

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_path)

    assert "empty" in str(exc_info.value).lower()


def test_load_config_missing_models_section(tmp_path):
    """Test that config without models section raises error."""
    config_path = tmp_path / "dspy.config.yaml"
    config_path.write_text("other: value")

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_path)

    assert "models" in str(exc_info.value)
