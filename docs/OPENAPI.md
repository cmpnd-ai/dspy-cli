# OpenAPI Specification Generation

The `dspy-cli serve` command automatically generates OpenAPI 3.1.0 specifications for your DSPy programs.

## Features

- **Automatic generation** on server start (enabled by default)
- **Multiple formats** supported: JSON and YAML
- **Enhanced metadata** from `dspy.config.yaml` (app_id, description)
- **DSPy-specific extensions** with program and model information
- **Always available** via `/openapi.json` endpoint, regardless of file generation

## Usage

### Default Behavior (JSON)

```bash
dspy-cli serve
# Creates openapi.json in project root
```

### YAML Format

```bash
dspy-cli serve --openapi-format yaml
# Creates openapi.yaml in project root
```

### Disable File Generation

```bash
dspy-cli serve --no-save-openapi
# Spec still available at http://localhost:8000/openapi.json
```

## Generated Specification

### Standard OpenAPI Fields

The generated spec includes:

- **Endpoints**: All discovered DSPy programs as POST endpoints
- **Request schemas**: Dynamically generated from DSPy module forward() signatures
- **Response schemas**: Output types from your modules
- **Validation**: Input/output validation via Pydantic models
- **Additional endpoints**: `/programs` for listing all programs

### DSPy-Specific Extensions

The spec includes custom OpenAPI extensions (x-* fields):

```json
{
  "info": {
    "title": "my-app-id",
    "description": "Description from dspy.config.yaml",
    "x-dspy-config": {
      "default_model": "openai:gpt-4",
      "programs_count": 3
    },
    "x-dspy-programs": [
      {
        "name": "CategorizerPredict",
        "module_path": "my_app.modules.categorizer_predict",
        "is_forward_typed": true
      }
    ],
    "x-dspy-program-models": {
      "CategorizerPredict": "openai:gpt-4",
      "SummarizerCoT": "anthropic:claude-3-sonnet"
    }
  }
}
```

## Configuration

### Metadata Source

The OpenAPI spec pulls metadata from `dspy.config.yaml`:

```yaml
app_id: my-blog-tools
description: A set of functions for a content management system.
```

These values populate the OpenAPI `title` and `description` fields.

### Fallback Defaults

If not specified in config:
- **title**: "DSPy API"
- **description**: "Automatically generated API for DSPy programs"
- **version**: "0.1.0"

## Accessing the Specification

### As a File

```bash
# After running dspy-cli serve
cat openapi.json
```

### Via HTTP Endpoint

```bash
# While server is running
curl http://localhost:8000/openapi.json
```

### In Code

```python
from fastapi import FastAPI
from dspy_cli.utils.openapi import generate_openapi_spec

# After creating your FastAPI app
spec = generate_openapi_spec(app)
```

## Integration with Tools

### Swagger UI

FastAPI automatically provides interactive API documentation at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### API Clients

Use the generated spec to create type-safe API clients:

```bash
# Generate TypeScript client
npx openapi-typescript openapi.json -o types.ts

# Generate Python client
openapi-generator-cli generate -i openapi.json -g python
```

### Validation

Validate your spec:

```bash
# Install validator
npm install -g @ibm/openapi-validator

# Validate spec
lint-openapi openapi.json
```

## Command-Line Options

```bash
dspy-cli serve [OPTIONS]

Options:
  --save-openapi / --no-save-openapi
                                Save OpenAPI spec to file on server start
                                (default: enabled)
  --openapi-format [json|yaml]  Format for OpenAPI spec file
                                (default: json)
```

## Examples

### Example: JSON Spec

```bash
cd my-project
dspy-cli serve
```

Creates `openapi.json`:
```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "my-project",
    "description": "Automatically generated API for DSPy programs",
    "version": "0.1.0"
  },
  "paths": {
    "/MyProgramPredict": {
      "post": {
        "summary": "Run Program",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/MyProgramPredictRequest"
              }
            }
          }
        }
      }
    }
  }
}
```

### Example: YAML Spec

```bash
dspy-cli serve --openapi-format yaml
```

Creates `openapi.yaml`:
```yaml
openapi: 3.1.0
info:
  title: my-project
  description: Automatically generated API for DSPy programs
  version: 0.1.0
paths:
  /MyProgramPredict:
    post:
      summary: Run Program
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MyProgramPredictRequest'
```

## Troubleshooting

### Spec Not Generated

If `openapi.json` isn't created:
1. Check that `--no-save-openapi` wasn't used
2. Verify write permissions in project directory
3. Check server logs for errors

### Missing Program Schemas

If programs don't appear in the spec:
1. Ensure modules subclass `dspy.Module`
2. Verify `forward()` method has type annotations
3. Check that modules are in `src/<package>/modules/`

### Incorrect Metadata

If title/description are wrong:
1. Check `app_id` in `dspy.config.yaml`
2. Verify `description` field in config
3. Ensure config file is in project root

## Implementation Details

- **Utility module**: `src/dspy_cli/utils/openapi.py`
- **Integration point**: `src/dspy_cli/server/app.py` (metadata enhancement)
- **File generation**: `src/dspy_cli/server/runner.py` (on server start)
- **Uses**: FastAPI's built-in `app.openapi()` method
