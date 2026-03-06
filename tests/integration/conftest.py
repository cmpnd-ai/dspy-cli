"""
Starts mock LLM server and dspy-cli server as subprocess fixtures.
Tests in this directory require these fixtures.
"""
import subprocess
import time
import os
import sys

import httpx
import pytest


MOCK_PORT = 9999
SERVER_PORT = 8000
FIXTURE_PROJECT = os.path.join(os.path.dirname(__file__), "..", "load", "fixture_project")


@pytest.fixture(scope="session", autouse=True)
def mock_lm_server():
    proc = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(__file__), "..", "load", "mock_lm_server.py")],
        env={**os.environ, "MOCK_DELAY_MS": "50", "MOCK_PORT": str(MOCK_PORT)},
    )
    # Wait for mock server to be ready
    for _ in range(10):
        try:
            httpx.get(f"http://127.0.0.1:{MOCK_PORT}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session", autouse=True)
def dspy_cli_server(mock_lm_server):
    proc = subprocess.Popen(
        [sys.executable, "-m", "dspy_cli.server.runner",
         "--port", str(SERVER_PORT), "--host", "127.0.0.1"],
        cwd=FIXTURE_PROJECT,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            resp = httpx.get(f"http://127.0.0.1:{SERVER_PORT}/programs", timeout=2)
            if resp.status_code == 200:
                break
        except Exception:
            time.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()
