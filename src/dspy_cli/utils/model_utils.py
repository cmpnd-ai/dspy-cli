"""Utilities for working with LLM model providers."""

import os


def parse_model_string(model_str: str) -> dict:
    """Parse a LiteLLM model string into provider and model components.

    Args:
        model_str: Model string in format "provider/model" (e.g., "anthropic/claude-sonnet-4-5")

    Returns:
        Dict with 'provider' and 'model' keys

    Examples:
        >>> parse_model_string("anthropic/claude-sonnet-4-5")
        {'provider': 'anthropic', 'model': 'claude-sonnet-4-5', 'full': 'anthropic/claude-sonnet-4-5'}

        >>> parse_model_string("openai/gpt-4o")
        {'provider': 'openai', 'model': 'gpt-4o', 'full': 'openai/gpt-4o'}
    """
    if '/' not in model_str:
        # If no provider specified, assume openai
        return {
            'provider': 'openai',
            'model': model_str,
            'full': f'openai/{model_str}'
        }

    parts = model_str.split('/', 1)
    return {
        'provider': parts[0],
        'model': parts[1],
        'full': model_str
    }


def is_local_model(provider: str) -> bool:
    """Check if a provider is a local model provider that doesn't need API keys.

    Args:
        provider: Provider name (e.g., "ollama", "vllm", "anthropic")

    Returns:
        True if provider is local and doesn't need API keys
    """
    local_providers = ['ollama', 'vllm', 'lmstudio', 'text-generation-inference', 'tgi']
    return provider.lower() in local_providers


def is_reasoning_model(provider: str, model: str) -> bool:
    """Check if a model is an OpenAI reasoning model that requires higher max_tokens.

    OpenAI reasoning models (o1, o3, gpt-5 series) require higher max_tokens limits
    to accommodate their extended reasoning processes.

    Args:
        provider: Provider name (e.g., "openai")
        model: Model name (e.g., "o1-preview", "gpt-5-mini", "gpt-5.1")

    Returns:
        True if model is a reasoning model that requires max_tokens=16000

    Examples:
        >>> is_reasoning_model("openai", "o1-preview")
        True

        >>> is_reasoning_model("openai", "gpt-5-mini")
        True

        >>> is_reasoning_model("openai", "gpt-4o")
        False
    """
    if provider.lower() != 'openai':
        return False

    # Check for o1-* and o3-* series
    if model.startswith('o1-') or model.startswith('o3-'):
        return True

    # Check for gpt-5 (exact match)
    if model == 'gpt-5':
        return True

    # Check for gpt-5-* series (e.g., gpt-5-mini)
    if model.startswith('gpt-5-'):
        return True

    # Check for gpt-5.x versions (e.g., gpt-5.1, gpt-5.2)
    if model.startswith('gpt-5.'):
        return True

    return False


def detect_api_key(provider: str) -> tuple[str | None, str]:
    """Detect API key environment variable for a given provider.

    Args:
        provider: Provider name (e.g., "anthropic", "openai")

    Returns:
        Tuple of (api_key_value or None, env_var_name)

    Examples:
        >>> detect_api_key("anthropic")
        ("sk-ant-...", "ANTHROPIC_API_KEY")  # if set

        >>> detect_api_key("openai")
        (None, "OPENAI_API_KEY")  # if not set
    """
    provider_lower = provider.lower()

    # Map of common provider names to their standard env var patterns
    provider_env_map = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'cohere': 'COHERE_API_KEY',
        'together': 'TOGETHER_API_KEY',
        'together_ai': 'TOGETHER_API_KEY',
        'togetherai': 'TOGETHER_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'gemini': 'GOOGLE_API_KEY',
        'groq': 'GROQ_API_KEY',
        'mistral': 'MISTRAL_API_KEY',
        'huggingface': 'HUGGINGFACE_API_KEY',
        'replicate': 'REPLICATE_API_KEY',
        'ai21': 'AI21_API_KEY',
        'bedrock': 'AWS_ACCESS_KEY_ID',  # AWS uses different pattern
        'vertex_ai': 'GOOGLE_APPLICATION_CREDENTIALS',
    }

    # Get the standard env var name for this provider
    env_var_name = provider_env_map.get(provider_lower)

    # If not in our map, construct a standard pattern: {PROVIDER}_API_KEY
    if not env_var_name:
        env_var_name = f"{provider.upper()}_API_KEY"

    # Try to get the value from environment
    api_key = os.getenv(env_var_name)

    return api_key, env_var_name


def generate_model_config(model_str: str, api_key: str | None, api_base: str | None = None) -> dict:
    """Generate model configuration for dspy.config.yaml.

    Args:
        model_str: Full model string (e.g., "anthropic/claude-sonnet-4-5")
        api_key: API key value (or None for local models)
        api_base: Optional custom API base URL (for local models or custom endpoints)

    Returns:
        Dict with model configuration
    """
    parsed = parse_model_string(model_str)
    provider = parsed['provider']
    model = parsed['model']
    _, env_var_name = detect_api_key(provider)

    # Determine max_tokens based on model type
    # OpenAI reasoning models (o1/o3/gpt-5) need higher limits for extended reasoning
    if is_reasoning_model(provider, model):
        max_tokens = 16000
    else:
        max_tokens = 8192  # Increased default from 4096

    config = {
        'model': model_str,
        'model_type': 'chat',
        'max_tokens': max_tokens,
        'temperature': 1.0,
    }

    # Add API key env var if not a local model
    if not is_local_model(provider):
        config['env'] = env_var_name

    # Add api_base if provided (for local models or custom endpoints)
    if api_base:
        config['api_base'] = api_base

    return config


def get_provider_display_name(provider: str) -> str:
    """Get a user-friendly display name for a provider.

    Args:
        provider: Provider name (e.g., "anthropic", "openai")

    Returns:
        Display name (e.g., "Anthropic", "OpenAI")
    """
    display_names = {
        'anthropic': 'Anthropic',
        'openai': 'OpenAI',
        'cohere': 'Cohere',
        'together': 'Together AI',
        'together_ai': 'Together AI',
        'togetherai': 'Together AI',
        'google': 'Google',
        'gemini': 'Google Gemini',
        'groq': 'Groq',
        'mistral': 'Mistral',
        'huggingface': 'Hugging Face',
        'replicate': 'Replicate',
        'ai21': 'AI21 Labs',
        'ollama': 'Ollama (local)',
        'vllm': 'vLLM (local)',
        'lmstudio': 'LM Studio (local)',
    }

    return display_names.get(provider.lower(), provider.capitalize())
