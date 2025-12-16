"""Authentication module for DSPy API server.

Provides lightweight bearer token + session cookie authentication.
- API clients use: Authorization: Bearer <DSPY_API_KEY>
- Browser UI uses: Login form -> signed HttpOnly session cookie
"""

import hmac
import logging
import os
import secrets
import time
from hashlib import sha256
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

COOKIE_NAME = "dspy_session"
SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days

# Environment variable names
ENV_API_TOKEN = "DSPY_API_KEY"
ENV_AUTH_ENABLED = "DSPY_CLI_AUTH_ENABLED"

# Paths that don't require authentication (defaults)
DEFAULT_OPEN_PATHS = {"/login", "/health", "/favicon.ico"}


def get_api_token() -> str | None:
    """Get the API token from environment."""
    return os.environ.get(ENV_API_TOKEN)


def is_auth_enabled() -> bool:
    """Check if auth is enabled via environment variable."""
    return os.environ.get(ENV_AUTH_ENABLED, "false").lower() == "true"


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def _sign(token: str, issued_at: int) -> str:
    """Create HMAC signature for session cookie."""
    msg = str(issued_at).encode()
    return hmac.new(token.encode(), msg, sha256).hexdigest()


def create_session_cookie_value(token: str) -> str:
    """Create a signed session cookie value."""
    issued_at = int(time.time())
    sig = _sign(token, issued_at)
    return f"{issued_at}.{sig}"


def verify_session_cookie(token: str, value: str) -> bool:
    """Verify a session cookie value."""
    try:
        issued_str, sig = value.split(".", 1)
        issued_at = int(issued_str)
    except ValueError:
        return False

    if (time.time() - issued_at) > SESSION_MAX_AGE:
        return False

    expected = _sign(token, issued_at)
    return hmac.compare_digest(expected, sig)


def check_auth(request: Request, token: str) -> bool:
    """Check if request is authenticated via bearer token or session cookie.
    
    Returns True if authenticated, False otherwise.
    """
    # Check Bearer token (API clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        provided_token = auth_header.split(" ", 1)[1].strip()
        if hmac.compare_digest(provided_token, token):
            return True

    # Check session cookie (browser UI)
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie and verify_session_cookie(token, cookie):
        return True

    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces authentication on all routes except open paths."""

    def __init__(self, app, token: str, open_paths: set[str] | None = None):
        super().__init__(app)
        self.token = token
        self.open_paths = open_paths if open_paths is not None else DEFAULT_OPEN_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path.rstrip("/") or "/"
        
        # Allow open paths without auth
        if path in self.open_paths or path == "/login":
            return await call_next(request)

        # Allow static files
        if path.startswith("/static"):
            return await call_next(request)

        # Check authentication
        if not check_auth(request, self.token):
            # For API requests, return 401 JSON
            accept = request.headers.get("Accept", "")
            if "application/json" in accept or request.url.path.startswith("/api/"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated. Provide Authorization: Bearer <token> header.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # For browser requests, redirect to login
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


def create_auth_routes(token: str):
    """Create login/logout routes for browser authentication.
    
    Args:
        token: The API token to validate against
        
    Returns:
        APIRouter with /login and /logout routes
    """
    from fastapi import APIRouter, Form

    router = APIRouter()

    @router.get("/login", response_class=HTMLResponse)
    async def login_form(request: Request, error: str | None = None):
        """Render the login form."""
        # If already authenticated, redirect to home
        if check_auth(request, token):
            return RedirectResponse(url="/", status_code=303)

        error_html = ""
        if error:
            error_html = f'<p style="color: #dc2626; margin-bottom: 1rem;">{error}</p>'

        return HTMLResponse(f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - DSPy API</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }}
        .login-card {{
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 400px;
        }}
        h1 {{
            color: #1f2937;
            margin-bottom: 0.5rem;
            font-size: 1.5rem;
        }}
        .subtitle {{
            color: #6b7280;
            margin-bottom: 1.5rem;
            font-size: 0.875rem;
        }}
        label {{
            display: block;
            color: #374151;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }}
        input[type="password"] {{
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 1rem;
            margin-bottom: 1rem;
        }}
        input[type="password"]:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 0.75rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: transform 0.1s, box-shadow 0.1s;
        }}
        button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        .help {{
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid #e5e7eb;
            font-size: 0.75rem;
            color: #6b7280;
        }}
        code {{
            background: #f3f4f6;
            padding: 0.125rem 0.25rem;
            border-radius: 3px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="login-card">
        <h1>DSPy API</h1>
        <p class="subtitle">Enter your API token to continue</p>
        {error_html}
        <form method="post">
            <label for="token">API Token</label>
            <input type="password" id="token" name="token" placeholder="Enter DSPY_API_KEY" autofocus required>
            <button type="submit">Login</button>
        </form>
        <div class="help">
            <p>The token is set via the <code>DSPY_API_KEY</code> environment variable.</p>
        </div>
    </div>
</body>
</html>
""")

    @router.post("/login")
    async def login(request: Request, token_input: str = Form(..., alias="token")):
        """Process login form submission."""
        if not hmac.compare_digest(token_input, token):
            return RedirectResponse(url="/login?error=Invalid+token", status_code=303)

        cookie_value = create_session_cookie_value(token)
        response = RedirectResponse(url="/", status_code=303)
        
        # Set secure cookie if request came over HTTPS
        # Cloud providers set X-Forwarded-Proto when terminating TLS at load balancer
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        is_https = forwarded_proto == "https" or request.url.scheme == "https"
        
        response.set_cookie(
            COOKIE_NAME,
            cookie_value,
            httponly=True,
            secure=is_https,
            samesite="lax",
            max_age=SESSION_MAX_AGE,
        )
        return response

    @router.post("/logout")
    async def logout():
        """Log out by clearing the session cookie."""
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response

    @router.get("/health")
    async def health():
        """Health check endpoint (always open)."""
        return {"status": "ok"}

    return router
