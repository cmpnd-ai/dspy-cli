"""Smoke tests for CLI commands: new, generate, serve."""

import os

import pytest
from click.testing import CliRunner

from dspy_cli.cli import main


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    """Change to temp directory for test, restore after."""
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(old)


def with_new_defaults(args):
    """Add default args to 'new' command to make it non-interactive."""
    out = args[:]
    if "--program-name" not in out and "-p" not in out:
        out += ["--program-name", "main"]
    if "--module-type" not in out and "-m" not in out:
        out += ["--module-type", "Predict"]
    if "--signature" not in out and "-s" not in out:
        out += ["--signature", "question -> answer"]
    if "--model" not in out:
        out += ["--model", "openai/gpt-4o-mini"]
    if "--api-key" not in out:
        out += ["--api-key", ""]  # Empty string to skip API key prompt
    return out


def test_cli_e2e_smoke(runner, tmp_cwd, monkeypatch):
    """End-to-end smoke test: new -> generate -> serve.
    
    Creates project, generates components, validates serve args.
    """
    # 1. Test 'new' command
    res = runner.invoke(main, with_new_defaults(["new", "acme-app"]), catch_exceptions=False)
    assert res.exit_code == 0
    
    proj = tmp_cwd / "acme-app"
    
    # Verify config files created
    for name in ["pyproject.toml", "dspy.config.yaml", "Dockerfile", ".dockerignore", ".env", "README.md", ".gitignore"]:
        assert (proj / name).exists(), f"Missing {name}"
    
    # Verify code structure created
    assert (proj / "src" / "acme_app" / "modules" / "main_predict.py").exists()
    assert (proj / "src" / "acme_app" / "signatures" / "main.py").exists()
    assert (proj / "tests" / "test_modules.py").exists()
    
    # 2. Test 'generate scaffold' command
    os.chdir(proj)
    res = runner.invoke(
        main, 
        ["g", "scaffold", "categorizer", "-m", "CoT", "-s", "question -> answer"],
        catch_exceptions=False
    )
    assert res.exit_code == 0
    assert (proj / "src" / "acme_app" / "signatures" / "categorizer.py").exists()
    assert (proj / "src" / "acme_app" / "modules" / "categorizer_cot.py").exists()
    
    # 3. Test 'generate signature' command
    res = runner.invoke(
        main,
        ["g", "signature", "tags", "-s", "post -> tags: list[str]"],
        catch_exceptions=False
    )
    assert res.exit_code == 0
    assert (proj / "src" / "acme_app" / "signatures" / "tags.py").exists()
    
    # 4. Test 'generate module' command
    res = runner.invoke(
        main,
        ["g", "module", "my_mod", "-m", "Predict"],
        catch_exceptions=False
    )
    assert res.exit_code == 0
    assert (proj / "src" / "acme_app" / "modules" / "my_mod_predict.py").exists()
    
    # 5. Test 'serve' command (stubbed to avoid starting actual server)
    calls = {}
    
    def fake_runner_main(**kwargs):
        calls.update(kwargs)
    
    monkeypatch.setattr("dspy_cli.commands.serve.runner_main", fake_runner_main)
    
    res = runner.invoke(
        main,
        [
            "serve",
            "--system",
            "--host", "127.0.0.1",
            "--port", "8765",
            "--no-reload",
            "--openapi-format", "yaml",
            "--logs-dir", "logs"
        ],
        catch_exceptions=False
    )
    assert res.exit_code == 0
    
    # Verify serve received correct arguments
    assert calls == {
        "port": 8765,
        "host": "127.0.0.1",
        "logs_dir": "logs",
        "reload": False,
        "save_openapi": True,
        "openapi_format": "yaml",
        "mcp": False,
        "auth": False,
    }


def test_new_with_signature(runner, tmp_cwd):
    """Test 'new' command with custom signature."""
    res = runner.invoke(
        main,
        with_new_defaults(["new", "my-project", "-p", "analyzer", "-s", "text, context: list[str] -> summary"]),
        catch_exceptions=False
    )
    assert res.exit_code == 0
    
    proj = tmp_cwd / "my-project"
    assert (proj / "src" / "my_project" / "modules" / "analyzer_predict.py").exists()
    assert (proj / "src" / "my_project" / "signatures" / "analyzer.py").exists()
    
    # Verify signature has correct fields
    sig_content = (proj / "src" / "my_project" / "signatures" / "analyzer.py").read_text()
    assert "text: str = dspy.InputField" in sig_content
    assert "context: list[str] = dspy.InputField" in sig_content
    assert "summary: str = dspy.OutputField" in sig_content


def test_generate_different_module_types(runner, tmp_cwd):
    """Test generating different module types."""
    # Create a project first
    res = runner.invoke(main, with_new_defaults(["new", "test-app"]), catch_exceptions=False)
    assert res.exit_code == 0
    
    proj = tmp_cwd / "test-app"
    os.chdir(proj)
    
    # Test different module types
    test_cases = [
        ("react_mod", "ReAct", "react_mod_react.py"),
        ("pot_mod", "PoT", "pot_mod_pot.py"),
        ("refine_mod", "Refine", "refine_mod_refine.py"),
    ]
    
    for prog_name, mod_type, expected_file in test_cases:
        res = runner.invoke(
            main,
            ["g", "module", prog_name, "-m", mod_type],
            catch_exceptions=False
        )
        assert res.exit_code == 0
        assert (proj / "src" / "test_app" / "modules" / expected_file).exists()


def test_new_invalid_name(runner, tmp_cwd):
    """Test 'new' command rejects invalid project names."""
    # Empty name
    res = runner.invoke(main, ["new", ""], catch_exceptions=False)
    assert res.exit_code != 0
    
    # Program name starting with digit should fail
    res = runner.invoke(main, ["new", "valid-proj", "-p", "1invalid"], catch_exceptions=False)
    assert res.exit_code != 0
    assert "not a valid Python identifier" in res.output


def test_generate_outside_project(runner, tmp_cwd):
    """Test 'generate' commands fail outside a DSPy project."""
    # Try to generate without being in a project
    res = runner.invoke(main, ["g", "scaffold", "test"], catch_exceptions=False)
    assert res.exit_code != 0
    assert "Not in a valid DSPy project" in res.output


def test_new_with_reasoning_model(runner, tmp_cwd):
    """Test 'new' command with OpenAI reasoning models sets max_tokens=16000."""
    test_cases = [
        ("openai/o1-preview", 16000),
        ("openai/o1-mini", 16000),
        ("openai/o3-mini", 16000),
        ("openai/gpt-5", 16000),
        ("openai/gpt-5-mini", 16000),
        ("openai/gpt-5.1", 16000),
    ]

    for model, expected_max_tokens in test_cases:
        project_name = f"test-{model.replace('/', '-').replace('.', '-')}"
        res = runner.invoke(
            main,
            with_new_defaults(["new", project_name, "--model", model]),
            catch_exceptions=False
        )
        assert res.exit_code == 0

        proj = tmp_cwd / project_name
        config_content = (proj / "dspy.config.yaml").read_text()
        assert f"max_tokens: {expected_max_tokens}" in config_content, \
            f"Expected max_tokens: {expected_max_tokens} for model {model}"


def test_new_with_standard_model_uses_new_default(runner, tmp_cwd):
    """Test 'new' command with standard models uses increased default max_tokens=8192."""
    test_cases = [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "anthropic/claude-sonnet-4-5",
    ]

    for model in test_cases:
        project_name = f"test-{model.replace('/', '-')}"
        res = runner.invoke(
            main,
            with_new_defaults(["new", project_name, "--model", model]),
            catch_exceptions=False
        )
        assert res.exit_code == 0

        proj = tmp_cwd / project_name
        config_content = (proj / "dspy.config.yaml").read_text()
        assert "max_tokens: 8192" in config_content, \
            f"Expected max_tokens: 8192 for standard model {model}"
