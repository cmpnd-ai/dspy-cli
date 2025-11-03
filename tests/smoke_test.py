#!/usr/bin/env python3
"""Smoke test to verify basic dspy-cli functionality after installation."""
import tempfile
import sys
from pathlib import Path

def main():
    """Test that dspy-cli new command works with installed package."""
    from click.testing import CliRunner
    from dspy_cli.cli import main as cli_main
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()
        original_cwd = os.getcwd()
        
        try:
            os.chdir(tmpdir)
            result = runner.invoke(cli_main, ['new', 'test-project'], catch_exceptions=False)
            
            if result.exit_code != 0:
                print(f"❌ Smoke test failed: Command exited with code {result.exit_code}", file=sys.stderr)
                print(result.output, file=sys.stderr)
                if result.exception:
                    raise result.exception
                sys.exit(1)
            
            project_path = Path(tmpdir) / "test-project"
        except Exception as e:
            print(f"❌ Smoke test failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            os.chdir(original_cwd)
        
        # Verify key files were created
        required_files = [
            "pyproject.toml",
            "dspy.config.yaml",
            "Dockerfile",
            ".dockerignore",
            ".env",
            "README.md",
            ".gitignore",
        ]
        
        for file_name in required_files:
            file_path = project_path / file_name
            if not file_path.exists():
                print(f"❌ Smoke test failed: {file_name} not created", file=sys.stderr)
                sys.exit(1)
        
        print("✅ Smoke test passed: dspy-cli works correctly")

if __name__ == "__main__":
    main()
