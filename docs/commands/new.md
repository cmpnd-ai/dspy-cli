# dspy-cli new

Create a new DSPy project — scaffolds structure, dependencies, and sample program so you start coding immediately.

## Usage

```bash
dspy-cli new PROJECT_NAME [OPTIONS]
```

## What Happens

```bash
$ dspy-cli new test-project
Creating new DSPy project: test-project
  Package name: test_project
  Initial program: test_project

  Created: test-project/src/test_project
  Created: test-project/src/test_project/modules
  Created: test-project/src/test_project/signatures
  Created: test-project/src/test_project/optimizers
  Created: test-project/src/test_project/metrics
  Created: test-project/pyproject.toml
  Created: test-project/dspy.config.yaml
  Created: test-project/Dockerfile
  Created: test-project/.env
  Created: test-project/.gitignore
  Created: test-project/README.md
  ...
  Created: test_project/signatures/test_project.py
  Created: test_project/modules/test_project_predict.py
  Created: tests/test_modules.py
  Initialized git repository
✓ Project created successfully!
```

## Options

- `--program-name`, `-p` - Initial program name
- `--signature`, `-s` - Inline signature (e.g., "question -> answer")

## Examples

```bash
# Simple: Basic project with default program
dspy-cli new test-project

# With signature: Pre-configure input/output fields
dspy-cli new qa-bot -s "question -> answer"
# Output includes: Signature: question -> answer

# Typed outputs: Specify return types for validation
dspy-cli new tagger -s "post -> tags: list[str]"

# Multi-field: Complex inputs and outputs
dspy-cli new analyzer -s "text, context -> sentiment, score: float"
```

## Next Steps

```bash
cd my-project
dspy-cli serve  # Start API server at http://localhost:8000
```

Add API keys to `.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```
