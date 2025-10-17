"""Logging utilities for the API server."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log API requests to per-module log files."""

    def __init__(self, app, logs_dir: Path):
        super().__init__(app)
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(exist_ok=True, parents=True)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log it."""
        start_time = time.time()

        # Extract program name from path
        path_parts = request.url.path.strip("/").split("/")
        program_name = path_parts[0] if path_parts else "unknown"

        # Call the endpoint
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log the request
            await self._log_request(
                program_name=program_name,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=duration,
                request=request
            )

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Log the error
            await self._log_request(
                program_name=program_name,
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration=duration,
                request=request,
                error=str(e)
            )

            raise

    async def _log_request(
        self,
        program_name: str,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        request: Request,
        error: str = None
    ):
        """Write request log entry to file."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 2),
        }

        if error:
            log_entry["error"] = error

        # Write to per-program log file
        log_file = self.logs_dir / f"{program_name}.log"

        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logging.error(f"Failed to write log: {e}")


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
