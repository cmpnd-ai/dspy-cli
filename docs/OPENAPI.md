# OpenAPI Specification Generation

`dspy-cli serve` automatically generates OpenAPI 3.1.0 specifications for DSPy programs.

## Features

- **Automatic generation** on server start (enabled by default)
- **Multiple formats**: JSON and YAML
- **Enhanced metadata** from `dspy.config.yaml` (app_id, description)
- **DSPy extensions** with program and model information
- **Always available** at `/openapi.json` endpoint

## Usage

```bash
# JSON format (default)
dspy-cli serve

# YAML format
dspy-cli serve --openapi-format yaml

# Disable file generation (still available at /openapi.json)
dspy-cli serve --no-save-openapi
```

## Generated Specification

Includes:

- **Endpoints**: All DSPy programs as POST endpoints
- **Request/response schemas**: From module `forward()` signatures
- **Validation**: Input/output validation via Pydantic
- **Additional endpoints**: `/programs` for listing programs

### DSPy Extensions

Custom OpenAPI extensions (x-* fields):

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
      "CategorizerPredict": "openai:gpt-4"
    }
  }
}
```

## Configuration

Metadata from `dspy.config.yaml`:

```yaml
app_id: my-blog-tools
description: A set of functions for a content management system.
```

Fallback defaults if not specified:

- **title**: "DSPy API"
- **description**: "Automatically generated API for DSPy programs"
- **version**: "0.1.0"

## Accessing the Specification

**As a file:**
```bash
cat openapi.json
```

**Via HTTP:**
```bash
curl http://localhost:8000/openapi.json
```

**In code:**
```python
from dspy_cli.utils.openapi import generate_openapi_spec
spec = generate_openapi_spec(app)
```

## Integration

### Interactive Documentation

FastAPI provides:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Generate API Clients

```bash
# TypeScript
npx openapi-typescript openapi.json -o types.ts

# Python
openapi-generator-cli generate -i openapi.json -g python
```

### Validation

```bash
npm install -g @ibm/openapi-validator
lint-openapi openapi.json
```

## Command Options

```bash
dspy-cli serve [OPTIONS]

Options:
  --save-openapi / --no-save-openapi
                                Save OpenAPI spec to file on server start
                                (default: enabled)
  --openapi-format [json|yaml]  Format for OpenAPI spec file
                                (default: json)
```

## Troubleshooting

**Spec not generated:**

1. Verify `--no-save-openapi` wasn't used
2. Check write permissions
3. Check server logs

**Missing program schemas:**

1. Ensure modules subclass `dspy.Module`
2. Verify `forward()` has type annotations
3. Check modules are in `src/<package>/modules/`

**Incorrect metadata:**

1. Check `app_id` in `dspy.config.yaml`
2. Verify `description` field
3. Ensure config file is in project root

## Implementation

- **Utility**: `src/dspy_cli/utils/openapi.py`
- **Integration**: `src/dspy_cli/server/app.py`
- **Generation**: `src/dspy_cli/server/runner.py`
- **Uses**: FastAPI's `app.openapi()` method
