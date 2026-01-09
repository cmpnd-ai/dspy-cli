#!/usr/bin/env python3
"""Test script to simulate GitHub webhook locally."""

import hashlib
import hmac
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def create_mock_webhook_payload(repo: str, pr_number: int) -> dict:
    """Create a mock GitHub webhook payload for PR opened event."""
    return {
        "action": "opened",
        "pull_request": {
            "number": pr_number,
            "head": {
                "sha": "abc123def456",  # Mock SHA
            },
        },
        "repository": {
            "full_name": repo,
        },
        "installation": {
            "id": int(os.environ.get("GITHUB_INSTALLATION_ID", "0")),
        },
    }


def sign_payload(payload: bytes, secret: str) -> str:
    """Generate GitHub-style HMAC-SHA256 signature."""
    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


def send_webhook(url: str, payload: dict, secret: str) -> requests.Response:
    """Send mock webhook to local server."""
    body = json.dumps(payload).encode()
    signature = sign_payload(body, secret)

    response = requests.post(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
        },
        timeout=30,
    )
    return response


def main():
    # Get webhook secret from env
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        print("ERROR: GITHUB_WEBHOOK_SECRET not set in .env")
        sys.exit(1)

    # Get installation ID (you need to add this to .env)
    installation_id = os.environ.get("GITHUB_INSTALLATION_ID")
    if not installation_id:
        print("ERROR: GITHUB_INSTALLATION_ID not set in .env")
        print("You can find this in GitHub App settings -> Installations")
        sys.exit(1)

    # Default test values
    repo = sys.argv[1] if len(sys.argv) > 1 else "stanfordnlp/dspy"
    pr_number = int(sys.argv[2]) if len(sys.argv) > 2 else 8902
    url = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000/webhooks/github"

    print(f"Sending mock webhook for {repo}#{pr_number} to {url}")

    payload = create_mock_webhook_payload(repo, pr_number)
    response = send_webhook(url, payload, secret)

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")


if __name__ == "__main__":
    main()
