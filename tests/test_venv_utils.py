"""Tests for virtual environment utilities."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


from dspy_cli.utils.venv import sanitize_env_for_exec, validate_python_version


class TestValidatePythonVersion:
    """Tests for Python version validation."""

    def test_current_python_valid(self):
        """Test that current Python passes validation."""
        is_valid, version = validate_python_version(Path(sys.executable), min_version=(3, 9))
        assert isinstance(is_valid, bool)
        assert isinstance(version, str)
        if is_valid:
            parts = version.split('.')
            assert len(parts) >= 2
            assert int(parts[0]) >= 3

    def test_absurd_version_requirement_fails(self):
        """Test that absurdly high version requirement fails."""
        is_valid, _ = validate_python_version(Path(sys.executable), min_version=(99, 0))
        assert is_valid is False

    def test_returns_version_string(self):
        """Test that version string is returned correctly."""
        _, version = validate_python_version(Path(sys.executable))
        assert version
        assert '.' in version
        parts = version.split('.')
        assert len(parts) >= 2


class TestUsesMinusS:
    """Test that validation uses -S flag to avoid sitecustomize."""

    def test_works_with_bad_sitecustomize(self):
        """Test that validation works even with broken sitecustomize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sitecustomize = Path(tmpdir) / "sitecustomize.py"
            sitecustomize.write_text("raise RuntimeError('sitecustomize loaded!')")
            
            env = os.environ.copy()
            env["PYTHONPATH"] = tmpdir
            
            # Without -S, sitecustomize loads and produces error in stderr
            result_without_s = subprocess.run(
                [sys.executable, "-c", "import sys"],
                env=env,
                capture_output=True
            )
            assert b"sitecustomize loaded!" in result_without_s.stderr
            
            # With -S, sitecustomize is skipped (no error in stderr)
            result_with_s = subprocess.run(
                [sys.executable, "-S", "-c", "import sys"],
                env=env,
                capture_output=True
            )
            assert b"sitecustomize loaded!" not in result_with_s.stderr
            
            # validate_python_version should work despite bad sitecustomize
            is_valid, version = validate_python_version(Path(sys.executable))
            assert is_valid
            assert version


class TestSanitizeEnv:
    """Tests for environment sanitization."""

    def test_removes_python_vars(self):
        """Test that Python-specific variables are removed."""
        os.environ["PYTHONPATH"] = "/fake/path"
        os.environ["PYTHONHOME"] = "/fake/home"
        os.environ["VIRTUAL_ENV"] = "/fake/venv"
        os.environ["__PYVENV_LAUNCHER__"] = "/fake/launcher"
        
        sanitized = sanitize_env_for_exec()
        
        removed_vars = ["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__"]
        for var in removed_vars:
            assert var not in sanitized, f"{var} should be removed"
        
        # Cleanup
        for var in removed_vars:
            os.environ.pop(var, None)

    def test_removes_conda_vars(self):
        """Test that CONDA variables are removed."""
        os.environ["CONDA_PREFIX"] = "/fake/conda"
        os.environ["CONDA_DEFAULT_ENV"] = "base"
        
        sanitized = sanitize_env_for_exec()
        
        conda_vars = [k for k in sanitized.keys() if k.startswith("CONDA_")]
        assert len(conda_vars) == 0, f"CONDA vars should be removed, found: {conda_vars}"
        
        # Cleanup
        os.environ.pop("CONDA_PREFIX", None)
        os.environ.pop("CONDA_DEFAULT_ENV", None)

    def test_sets_pythonnousersite(self):
        """Test that PYTHONNOUSERSITE is set."""
        sanitized = sanitize_env_for_exec()
        assert sanitized.get("PYTHONNOUSERSITE") == "1"

    def test_preserves_other_vars(self):
        """Test that non-Python vars are preserved."""
        os.environ["MY_CUSTOM_VAR"] = "test_value"
        
        sanitized = sanitize_env_for_exec()
        assert sanitized.get("MY_CUSTOM_VAR") == "test_value"
        
        # Cleanup
        os.environ.pop("MY_CUSTOM_VAR", None)
