# dspy-code-review-agent

A DSPy project created with dspy-cli.

## Setup

1. Configure your API keys in `.env`:
```bash
# Edit .env and add your API keys
OPENAI_API_KEY=your-key-here
```

2. Update model configuration in `dspy.config.yaml` as needed.

## Development

### Project Structure

- `src/dspy_code_review_agent/modules/` - DSPy program implementations
- `src/dspy_code_review_agent/signatures/` - Reusable signatures
- `src/dspy_code_review_agent/optimizers/` - Optimizer configurations
- `src/dspy_code_review_agent/metrics/` - Evaluation metrics
- `src/dspy_code_review_agent/utils/` - Shared helper functions
- `data/` - Training and evaluation data
- `logs/` - API request logs
- `tests/` - Test files

### Running the API

Start the development server:
```bash
dspy-cli serve
```

Or specify custom host/port:
```bash
dspy-cli serve --port 8080 --host 127.0.0.1
```

### Available Endpoints

- `GET /programs` - List all available programs
- `POST /{program}` - Execute a program with JSON input

### Example Request

```bash
curl -X POST http://localhost:8000/dspy_code_review_agent \\
  -H "Content-Type: application/json" \\
  -d '{"question": "your question here"}'
```

## Testing

Run tests:
```bash
pytest
```

## Learn More

- [DSPy Documentation](https://dspy.ai)
