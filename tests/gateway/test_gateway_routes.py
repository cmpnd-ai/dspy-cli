"""Integration tests for APIGateway with routes."""

import sys

import pytest
from fastapi.testclient import TestClient

from dspy_cli.server.app import create_app


@pytest.fixture
def test_config():
    """Minimal valid config for testing."""
    return {
        "models": {
            "default": "test_model",
            "registry": {
                "test_model": {
                    "model": "openai/gpt-3.5-turbo",
                    "env": "OPENAI_API_KEY",
                    "max_tokens": 4000,
                    "temperature": 1.0,
                    "model_type": "chat"
                }
            }
        }
    }


@pytest.fixture
def gateway_project(tmp_path, monkeypatch):
    """Create a project with a module that uses a custom APIGateway."""
    from click.testing import CliRunner
    from dspy_cli.cli import main
    
    monkeypatch.chdir(tmp_path)
    
    runner = CliRunner()
    result = runner.invoke(
        main, 
        ["new", "gatewaypkg", "--program-name", "main", "--module-type", "Predict", 
         "--signature", "question -> answer", "--model", "openai/gpt-4o-mini", "--api-key", ""], 
        catch_exceptions=False
    )
    assert result.exit_code == 0
    
    project_root = tmp_path / "gatewaypkg"
    
    default_module = project_root / "src" / "gatewaypkg" / "modules" / "main_predict.py"
    if default_module.exists():
        default_module.unlink()
    
    module_path = project_root / "src" / "gatewaypkg" / "modules" / "webhook_processor.py"
    module_path.write_text('''"""Module with custom APIGateway for webhook processing."""
import dspy
from dspy_cli.gateway import APIGateway


class WebhookGateway(APIGateway):
    """Transform webhook payload to pipeline inputs."""
    path = "/webhooks/process"
    
    def to_pipeline_inputs(self, request):
        """Extract text from nested webhook payload."""
        if isinstance(request, dict):
            return {"text": request.get("data", {}).get("content", "")}
        return {"text": str(request)}
    
    def from_pipeline_output(self, output):
        """Wrap output in webhook response format."""
        return {
            "status": "processed",
            "result": output,
        }


class WebhookProcessor(dspy.Module):
    """Process webhook data - no LLM calls."""
    gateway = WebhookGateway
    
    def forward(self, text: str):
        return {"processed_text": text.upper(), "length": len(text)}
''')
    
    config_path = project_root / "dspy.config.yaml"
    config_content = """version: 1
models:
  default: test_model
  registry:
    test_model:
      model: openai/gpt-3.5-turbo
      env: OPENAI_API_KEY
      max_tokens: 4000
      temperature: 1.0
      model_type: chat
"""
    config_path.write_text(config_content)
    
    monkeypatch.chdir(project_root)
    sys.path.insert(0, str(project_root / "src"))
    
    yield {
        "root": project_root,
        "modules_path": project_root / "src" / "gatewaypkg" / "modules",
        "package_name": "gatewaypkg.modules",
    }
    
    if str(project_root / "src") in sys.path:
        sys.path.remove(str(project_root / "src"))


@pytest.fixture
def identity_gateway_project(tmp_path, monkeypatch):
    """Create a project with a module that has no gateway (uses IdentityGateway)."""
    from click.testing import CliRunner
    from dspy_cli.cli import main
    
    monkeypatch.chdir(tmp_path)
    
    runner = CliRunner()
    result = runner.invoke(
        main, 
        ["new", "identitypkg", "--program-name", "main", "--module-type", "Predict", 
         "--signature", "question -> answer", "--model", "openai/gpt-4o-mini", "--api-key", ""], 
        catch_exceptions=False
    )
    assert result.exit_code == 0
    
    project_root = tmp_path / "identitypkg"
    
    default_module = project_root / "src" / "identitypkg" / "modules" / "main_predict.py"
    if default_module.exists():
        default_module.unlink()
    
    module_path = project_root / "src" / "identitypkg" / "modules" / "echo.py"
    module_path.write_text('''"""Simple echo module with no gateway."""
import dspy


class Echo(dspy.Module):
    """Echo back input - no gateway, no LLM calls."""
    
    def forward(self, text: str):
        return {"echo": text}
''')
    
    config_path = project_root / "dspy.config.yaml"
    config_content = """version: 1
models:
  default: test_model
  registry:
    test_model:
      model: openai/gpt-3.5-turbo
      env: OPENAI_API_KEY
      max_tokens: 4000
      temperature: 1.0
      model_type: chat
"""
    config_path.write_text(config_content)
    
    monkeypatch.chdir(project_root)
    sys.path.insert(0, str(project_root / "src"))
    
    yield {
        "root": project_root,
        "modules_path": project_root / "src" / "identitypkg" / "modules",
        "package_name": "identitypkg.modules",
    }
    
    if str(project_root / "src") in sys.path:
        sys.path.remove(str(project_root / "src"))


class TestAPIGatewayRoutes:
    """Tests for APIGateway integration with routes."""

    def test_custom_gateway_path(self, gateway_project, test_config):
        """Custom gateway path should be used instead of module name."""
        app = create_app(
            config=test_config,
            package_path=gateway_project["modules_path"],
            package_name=gateway_project["package_name"],
            logs_dir=gateway_project["root"] / "logs",
            enable_ui=False
        )
        
        with TestClient(app):
            routes = [r.path for r in app.routes if hasattr(r, "path")]
            assert "/webhooks/process" in routes
            assert "/WebhookProcessor" not in routes

    def test_custom_gateway_input_transform(self, gateway_project, test_config):
        """Gateway should transform webhook payload to pipeline inputs."""
        app = create_app(
            config=test_config,
            package_path=gateway_project["modules_path"],
            package_name=gateway_project["package_name"],
            logs_dir=gateway_project["root"] / "logs",
            enable_ui=False
        )
        
        with TestClient(app) as client:
            response = client.post(
                "/webhooks/process",
                json={"data": {"content": "hello world"}}
            )
            assert response.status_code == 200
            result = response.json()
            
            assert result["status"] == "processed"
            assert result["result"]["processed_text"] == "HELLO WORLD"
            assert result["result"]["length"] == 11

    def test_custom_gateway_output_transform(self, gateway_project, test_config):
        """Gateway should wrap pipeline output in response format."""
        app = create_app(
            config=test_config,
            package_path=gateway_project["modules_path"],
            package_name=gateway_project["package_name"],
            logs_dir=gateway_project["root"] / "logs",
            enable_ui=False
        )
        
        with TestClient(app) as client:
            response = client.post(
                "/webhooks/process",
                json={"data": {"content": "test"}}
            )
            assert response.status_code == 200
            result = response.json()
            
            assert "status" in result
            assert "result" in result
            assert result["status"] == "processed"


class TestIdentityGatewayRoutes:
    """Tests for IdentityGateway (default) behavior."""

    def test_no_gateway_uses_module_name_path(self, identity_gateway_project, test_config):
        """Module without gateway should use /{module_name} path."""
        app = create_app(
            config=test_config,
            package_path=identity_gateway_project["modules_path"],
            package_name=identity_gateway_project["package_name"],
            logs_dir=identity_gateway_project["root"] / "logs",
            enable_ui=False
        )
        
        with TestClient(app):
            routes = [r.path for r in app.routes if hasattr(r, "path")]
            assert "/Echo" in routes

    def test_identity_gateway_passthrough(self, identity_gateway_project, test_config):
        """IdentityGateway should pass inputs/outputs unchanged."""
        app = create_app(
            config=test_config,
            package_path=identity_gateway_project["modules_path"],
            package_name=identity_gateway_project["package_name"],
            logs_dir=identity_gateway_project["root"] / "logs",
            enable_ui=False
        )
        
        with TestClient(app) as client:
            response = client.post("/Echo", json={"text": "hello"})
            assert response.status_code == 200
            result = response.json()
            
            assert result == {"echo": "hello"}

    def test_backward_compatibility(self, identity_gateway_project, test_config):
        """Existing modules without gateways should work unchanged."""
        app = create_app(
            config=test_config,
            package_path=identity_gateway_project["modules_path"],
            package_name=identity_gateway_project["package_name"],
            logs_dir=identity_gateway_project["root"] / "logs",
            enable_ui=False
        )
        
        with TestClient(app) as client:
            response = client.get("/programs")
            assert response.status_code == 200
            programs = response.json()["programs"]
            assert len(programs) == 1
            assert programs[0]["name"] == "Echo"
            
            response = client.post("/Echo", json={"text": "test input"})
            assert response.status_code == 200
            assert response.json()["echo"] == "test input"
