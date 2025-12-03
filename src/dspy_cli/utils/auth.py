"""Authentication utilities for API key generation and validation."""

import hashlib
import secrets
import string


def generate_api_key() -> str:
    """Generate a cryptographically secure API key.

    Returns:
        API key in format: ak_<32-char-base58-random>
        Example: ak_Jx7kP9mQrS2tVwXyZaBcDeFgHiJkLmNo
    """
    # Base58 alphabet (no confusing characters: 0, O, I, l)
    base58_alphabet = string.ascii_letters + string.digits
    base58_alphabet = base58_alphabet.replace('0', '').replace('O', '').replace('I', '').replace('l', '')

    # Generate 32 random characters from base58 alphabet
    random_part = ''.join(secrets.choice(base58_alphabet) for _ in range(32))

    return f"ak_{random_part}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256.

    Args:
        api_key: The plaintext API key to hash

    Returns:
        SHA-256 hash in format: sha256:<hex-digest>
    """
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return f"sha256:{key_hash}"


def validate_key_format(api_key: str) -> bool:
    """Validate that an API key has the correct format.

    Args:
        api_key: The API key to validate

    Returns:
        True if format is valid (ak_<32-chars>), False otherwise
    """
    if not api_key.startswith("ak_"):
        return False

    if len(api_key) != 35:  # "ak_" (3) + 32 chars
        return False

    # Check that the random part contains only valid base58 characters
    random_part = api_key[3:]
    base58_alphabet = string.ascii_letters + string.digits
    base58_alphabet = base58_alphabet.replace('0', '').replace('O', '').replace('I', '').replace('l', '')

    return all(c in base58_alphabet for c in random_part)
