"""GitHub App authentication utilities."""

import logging
import time
from datetime import datetime
from typing import Dict, Tuple

import jwt
import requests

logger = logging.getLogger(__name__)


class GitHubAppAuth:
    """Handle GitHub App authentication and installation tokens.

    GitHub Apps authenticate in two steps:
    1. Generate a JWT signed with the App's private key
    2. Exchange the JWT for an installation access token

    Installation tokens are short-lived (1 hour) and scoped to specific repos.
    """

    def __init__(self, app_id: str, private_key: str):
        """Initialize GitHub App authentication.

        Args:
            app_id: GitHub App ID (numeric string)
            private_key: PEM-encoded RSA private key (can have literal \\n)
        """
        self.app_id = app_id
        # Handle PEM key that may be passed as single-line with \n escaped
        self.private_key = private_key.replace("\\n", "\n")
        # Cache: installation_id -> (token, expiry_timestamp)
        self._token_cache: Dict[int, Tuple[str, float]] = {}

    def _generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        JWTs are valid for up to 10 minutes and are used to request
        installation access tokens.

        Returns:
            Encoded JWT string
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago (clock skew tolerance)
            "exp": now + (10 * 60),  # Expires in 10 minutes
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token for a specific installation.

        Tokens are cached until close to expiry to avoid unnecessary API calls.

        Args:
            installation_id: GitHub App installation ID (from webhook payload)

        Returns:
            Installation access token

        Raises:
            requests.HTTPError: If token exchange fails
        """
        # Check cache (with 60 second buffer before expiry)
        if installation_id in self._token_cache:
            token, expiry = self._token_cache[installation_id]
            if time.time() < expiry - 60:
                logger.debug(f"Using cached token for installation {installation_id}")
                return token

        logger.info(f"Requesting new token for installation {installation_id}")

        # Generate JWT for app authentication
        app_jwt = self._generate_jwt()

        # Exchange JWT for installation token
        response = requests.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        token = data["token"]

        # Parse expiry timestamp (ISO 8601 format: 2024-01-01T00:00:00Z)
        expiry_str = data["expires_at"]
        expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00")).timestamp()

        # Cache the token
        self._token_cache[installation_id] = (token, expiry)
        logger.info(f"Cached new token for installation {installation_id}")

        return token
