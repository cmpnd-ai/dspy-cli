"""Configuration loader for DSPy projects."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load DSPy configuration from YAML file and environment variables.

    Args:
        config_path: Path to dspy.config.yaml file. If None, searches in current directory.

    Returns:
        Dictionary containing parsed configuration

    Raises:
        ConfigError: If configuration file is missing or invalid
    """
    # Find config file
    if config_path is None:
        config_path = Path.cwd() / "dspy.config.yaml"

    if not config_path.exists():
        raise ConfigError(
            f"Configuration file not found: {config_path}\n"
            "Make sure you're running this command from a DSPy project directory.\n"
            "Create a new project with: dspy-cli new <project-name>"
        )

    # Load environment variables from .env
    env_path = config_path.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Load YAML config
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse configuration file: {e}")

    if not config:
        raise ConfigError("Configuration file is empty")

    # Validate required sections
    if "models" not in config:
        raise ConfigError("Configuration must contain 'models' section")

    models_config = config["models"]

    if "default" not in models_config:
        raise ConfigError("Configuration must specify 'models.default'")

    if "registry" not in models_config:
        raise ConfigError("Configuration must contain 'models.registry'")

    # Resolve environment variables in model configurations
    registry = models_config["registry"]
    for model_name, model_config in registry.items():
        if "env" in model_config:
            env_var = model_config["env"]
            api_key = os.getenv(env_var)
            if api_key:
                model_config["api_key"] = api_key
            else:
                # Warning, but don't fail - allow models without keys for testing
                pass

    return config


def get_model_config(config: Dict[str, Any], model_alias: str) -> Dict[str, Any]:
    """Get configuration for a specific model alias.

    Args:
        config: Loaded configuration dictionary
        model_alias: Model alias (e.g., 'openai:gpt-5-mini')

    Returns:
        Model configuration dictionary

    Raises:
        ConfigError: If model alias is not found in registry
    """
    registry = config["models"]["registry"]

    if model_alias not in registry:
        available = ", ".join(registry.keys())
        raise ConfigError(
            f"Model alias '{model_alias}' not found in registry.\n"
            f"Available models: {available}"
        )

    return registry[model_alias]


def get_program_model(config: Dict[str, Any], program_name: str) -> str:
    """Get the model alias for a specific program.

    Args:
        config: Loaded configuration dictionary
        program_name: Name of the program/module

    Returns:
        Model alias to use for this program (from program_models or default)
    """
    program_models = config.get("program_models", {})

    # Check for program-specific override
    if program_name in program_models:
        return program_models[program_name]

    # Fall back to default
    return config["models"]["default"]
