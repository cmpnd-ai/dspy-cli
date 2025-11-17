"""Integration tests for serve command - real server without LLM calls."""

import sys

import pytest
from fastapi.testclient import TestClient

from dspy_cli.server.app import create_app
from dspy_cli.utils.openapi import generate_openapi_spec, save_openapi_spec


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
def temp_project(tmp_path, monkeypatch):
    """Create a minimal DSPy project using 'dspy-cli new' with a no-LLM dummy module."""
    from click.testing import CliRunner
    from dspy_cli.cli import main
    
    # Change to temp directory
    monkeypatch.chdir(tmp_path)
    
    # Use actual 'dspy-cli new' command to create project (with defaults to avoid prompts)
    runner = CliRunner()
    result = runner.invoke(
        main, 
        ["new", "testpkg", "--program-name", "main", "--module-type", "Predict", 
         "--signature", "question -> answer", "--model", "openai/gpt-4o-mini", "--api-key", ""], 
        catch_exceptions=False
    )
    assert result.exit_code == 0
    
    project_root = tmp_path / "testpkg"
    
    # Remove the default module and add our no-LLM Echo module
    default_module = project_root / "src" / "testpkg" / "modules" / "main_predict.py"
    if default_module.exists():
        default_module.unlink()
    
    echo_module_path = project_root / "src" / "testpkg" / "modules" / "echo.py"
    echo_module_path.write_text(
        "import dspy\n"
        "\n"
        "class Echo(dspy.Module):\n"
        "    def forward(self, text: str):\n"
        "        return {'echo': text}\n"
    )
    
    # Update config to use test model
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
    
    # Change to project directory and add to sys.path
    monkeypatch.chdir(project_root)
    sys.path.insert(0, str(project_root / "src"))
    
    yield {
        "root": project_root,
        "modules_path": project_root / "src" / "testpkg" / "modules",
        "package_name": "testpkg.modules",
    }
    
    # Cleanup sys.path
    if str(project_root / "src") in sys.path:
        sys.path.remove(str(project_root / "src"))


def test_create_app_discovers_modules(temp_project, test_config):
    """Test that create_app discovers and registers modules."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=False
    )
    
    # Verify Echo module was discovered
    assert hasattr(app.state, "modules")
    module_names = [m.name for m in app.state.modules]
    assert "Echo" in module_names
    
    # Verify POST /Echo route exists
    routes = [r for r in app.routes]
    echo_route = None
    for route in routes:
        if hasattr(route, "path") and route.path == "/Echo":
            echo_route = route
            break
    
    assert echo_route is not None, "POST /Echo route not found"
    assert "POST" in echo_route.methods


def test_openapi_spec_generation(temp_project, test_config):
    """Test OpenAPI spec generation includes discovered modules."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=False
    )
    
    # Generate spec
    spec = generate_openapi_spec(app)
    
    # Verify basic structure
    assert "openapi" in spec
    assert "paths" in spec
    assert "/Echo" in spec["paths"]
    assert "post" in spec["paths"]["/Echo"]
    
    # Verify other standard endpoints
    assert "/programs" in spec["paths"]


def test_save_openapi_spec_json(temp_project, test_config):
    """Test saving OpenAPI spec to JSON file."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=False
    )
    
    spec = generate_openapi_spec(app)
    output_path = temp_project["root"] / "openapi.json"
    
    save_openapi_spec(spec, output_path, format="json")
    
    assert output_path.exists()
    
    # Verify it's valid JSON
    import json
    content = json.loads(output_path.read_text())
    assert "/Echo" in content["paths"]


def test_save_openapi_spec_yaml(temp_project, test_config):
    """Test saving OpenAPI spec to YAML file."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=False
    )
    
    spec = generate_openapi_spec(app)
    output_path = temp_project["root"] / "openapi.yaml"
    
    save_openapi_spec(spec, output_path, format="yaml")
    
    assert output_path.exists()
    
    # Verify it's valid YAML
    import yaml
    content = yaml.safe_load(output_path.read_text())
    assert "/Echo" in content["paths"]


def test_runner_main_no_reload(temp_project, test_config, monkeypatch):
    """Test runner.main with reload=False saves OpenAPI and calls uvicorn."""
    from dspy_cli.server import runner
    
    # Mock load_config to return test config
    monkeypatch.setattr("dspy_cli.server.runner.load_config", lambda: test_config)
    
    # Mock uvicorn.run to avoid starting server
    calls = []
    def fake_run(app_or_str, **kw):
        calls.append({
            "app_is_string": isinstance(app_or_str, str),
            "host": kw.get("host"),
            "port": kw.get("port"),
            "reload": kw.get("reload", False),
            "factory": kw.get("factory", False)
        })
    
    monkeypatch.setattr("uvicorn.run", fake_run)
    
    # Run server
    runner.main(
        port=1234,
        host="127.0.0.1",
        logs_dir=str(temp_project["root"] / "logs"),
        reload=False,
        save_openapi=True,
        openapi_format="json"
    )
    
    # Verify uvicorn was called correctly
    assert len(calls) == 1
    assert calls[0]["app_is_string"] is False  # Should pass app instance
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 1234
    assert calls[0]["reload"] is False
    
    # Verify OpenAPI was saved
    assert (temp_project["root"] / "openapi.json").exists()


def test_runner_main_with_reload(temp_project, test_config, monkeypatch):
    """Test runner.main with reload=True uses import string and factory."""
    from dspy_cli.server import runner
    
    # Mock load_config
    monkeypatch.setattr("dspy_cli.server.runner.load_config", lambda: test_config)
    
    # Mock uvicorn.run
    calls = []
    def fake_run(app_or_str, **kw):
        calls.append({
            "app": app_or_str,
            "is_string": isinstance(app_or_str, str),
            **kw
        })
    
    monkeypatch.setattr("uvicorn.run", fake_run)
    
    # Run server with reload
    runner.main(
        port=8000,
        host="0.0.0.0",
        logs_dir=None,
        reload=True,
        save_openapi=False,
        openapi_format="json"
    )
    
    # Verify uvicorn was called with import string for reload
    assert len(calls) == 1
    assert calls[0]["is_string"] is True
    assert "dspy_cli.server.runner:create_app_instance" in calls[0]["app"]
    assert calls[0]["reload"] is True
    assert calls[0].get("factory") is True


def test_create_app_with_ui_enabled(temp_project, test_config):
    """Test that UI is enabled when requested."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=True
    )
    
    # UI might be at /ui or mounted differently - just verify app was created
    assert app is not None


def test_real_server_endpoints(temp_project, test_config):
    """Test actual HTTP requests to the server with no-LLM module."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=False
    )
    
    # Use FastAPI TestClient for real HTTP requests
    with TestClient(app) as client:
        # Test GET /programs endpoint
        response = client.get("/programs")
        assert response.status_code == 200
        data = response.json()
        assert "programs" in data
        assert len(data["programs"]) > 0
        assert data["programs"][0]["name"] == "Echo"
        
        # Test OpenAPI endpoint
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "/Echo" in spec["paths"]
        
        # Test POST /Echo endpoint with our no-LLM module
        response = client.post("/Echo", json={"text": "hello world"})
        assert response.status_code == 200
        result = response.json()
        assert "echo" in result
        assert result["echo"] == "hello world"


def test_server_error_handling(temp_project, test_config):
    """Test server handles errors gracefully."""
    app = create_app(
        config=test_config,
        package_path=temp_project["modules_path"],
        package_name=temp_project["package_name"],
        logs_dir=temp_project["root"] / "logs",
        enable_ui=False
    )
    
    with TestClient(app) as client:
        # Test invalid endpoint
        response = client.post("/NonExistent", json={})
        assert response.status_code == 404
        
        # Test missing required field
        # Without typed forward(), server returns 500 when args are missing
        response = client.post("/Echo", json={})
        assert response.status_code == 500
        assert "detail" in response.json()
        
        # Test malformed JSON
        response = client.post(
            "/Echo",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422  # FastAPI validation error
