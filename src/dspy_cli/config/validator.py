"""Configuration validation utilities."""

from pathlib import Path
from typing import Optional


def validate_project_structure(base_path: Optional[Path] = None) -> bool:
    """Validate that the current directory is a valid DSPy project.

    Args:
        base_path: Base path to check. If None, uses current directory.

    Returns:
        True if valid project structure, False otherwise
    """
    if base_path is None:
        base_path = Path.cwd()

    # Check for required files
    required_files = [
        "dspy.config.yaml",
        "src",
    ]

    for required in required_files:
        path = base_path / required
        if not path.exists():
            return False

    return True


def find_package_directory(base_path: Optional[Path] = None) -> Optional[Path]:
    """Find the main package directory in src/.

    Args:
        base_path: Base path to search from. If None, uses current directory.

    Returns:
        Path to the package directory, or None if not found
    """
    if base_path is None:
        base_path = Path.cwd()

    src_path = base_path / "src"

    if not src_path.exists():
        return None

    # Look for directories in src/ (should be exactly one package)
    packages = [d for d in src_path.iterdir() 
            if d.is_dir() and (d / "__init__.py").exists()]

    if len(packages) == 1:
        return packages[0]

    return None
