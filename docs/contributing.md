# Contributing

Thank you for your interest in contributing to dspy-cli! This guide will help you get started.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/cmpnd-ai/cli-tool
cd cli-tool/dspy-cli

# Install with uv (recommended)
uv sync --extra dev

# Or with pip
pip install -e '.[dev]'

# Verify installation
dspy-cli --version
```

## Development Setup

### Using uv (Recommended)

```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync --extra dev

# Activate the virtual environment
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows
```

### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows

# Install in editable mode with dev dependencies
pip install -e '.[dev]'
```

## Running Tests

Tests are located in the `tests/` directory and use pytest.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/dspy_cli

# Run specific test file
pytest tests/test_commands.py

# Run specific test
pytest tests/test_commands.py::test_new_command

# Run with verbose output
pytest -v
```

**Important**: Tests require the package to be installed in editable mode (`pip install -e '.[dev]'`) to ensure import behavior matches production.

## Code Style

dspy-cli follows these conventions:

### Import Order

1. Standard library imports
2. Third-party imports (docker, fastapi, pydantic, click, etc.)
3. Local imports

```python
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import click
from fastapi import FastAPI
from pydantic import BaseModel

from dspy_cli.utils.venv import detect_venv_python
from dspy_cli.errors import DSPyError
```

### Naming

- **Functions and variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Type hints required** for all function signatures

### File Paths

- Use `Path` from `pathlib`, not strings
- Example: `Path.cwd() / "dspy.config.yaml"` not `"dspy.config.yaml"`

## Testing Locally

### Test with Sample App

```bash
# From project root
cd sample_app

# Serve locally
dspy-cli serve

# In another terminal, test
curl -X POST "http://localhost:8000/predict/qa" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is DSPy?"}'
```

### Test New Project Creation

```bash
# Create test project
dspy-cli new test-project -s "question -> answer"
cd test-project

# Install and serve
uv sync
dspy-cli serve
```

## Common Development Tasks

### Update Templates

Templates are in `src/dspy_cli/templates/`:

- `pyproject.toml.template`
- `dspy.config.yaml.template`
- `Dockerfile.template`
- Code templates in `code_templates/`

After updating, test with:

```bash
dspy-cli new test-project
```

### Add New Module Type

To support a new DSPy module type in `generate scaffold`:

1. Add to `MODULE_TYPES` in `src/dspy_cli/commands/generate.py`
2. Create template in `src/dspy_cli/templates/code_templates/`
3. Update docs

## Documentation

Documentation uses MkDocs with Material theme.

### Build Docs Locally

```bash
# Install docs dependencies
pip install -e '.[docs]'

# Serve docs locally
mkdocs serve

# Build static site
mkdocs build
```

Visit http://localhost:8000 to preview.

### Update Docs

- `docs/index.md` - Main landing page
- `docs/cli-reference.md` - CLI command reference
- `docs/contributing.md` - This file
- `mkdocs.yml` - MkDocs configuration

## Releasing

For information on how to release new versions to PyPI, see [Releasing](releasing.md).

## Reporting Issues

Found a bug or have a feature request?

1. **Check existing issues**: [GitHub Issues](https://github.com/cmpnd-ai/cli-tool/issues)
2. **Create new issue** with:
   - Clear description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Environment info (OS, Python version, dspy-cli version)

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/cmpnd-ai/cli-tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cmpnd-ai/cli-tool/discussions)

## Code of Conduct

Be respectful, inclusive, and professional. We're all here to build great tools together.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).
