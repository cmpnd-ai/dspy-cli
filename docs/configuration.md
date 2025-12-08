# Configuration

## Example

```yaml
# dspy.config.yaml
app_id: my-app
models:
  default: openai:gpt-5-mini
  
  registry:
    openai:gpt-5-mini:
      model: openai/gpt-5-mini
      env: OPENAI_API_KEY
      max_tokens: 16000
      temperature: 1.0

    anthropic:sonnet-4.5:
      model: anthropic/claude-sonnet-4-5
      env: ANTHROPIC_API_KEY
      max_tokens: 8192
      temperature: 0.7
    
    local:llama:
      model: ollama/llama3
      api_base: http://localhost:11434
      api_key: placeholder

# Optional: per-program overrides
program_models:
  MyCoT: anthropic:sonnet-4.5
  MyPredict: openai:gpt-5-mini
```

## Fields

| Field | Required | Description |
|-------|----------|-------------|
| `app_id` | Yes | Unique identifier |
| `models.default` | Yes | Default model alias |
| `models.registry` | Yes | Available models |
| `program_models` | No | Per-program model overrides |

### Registry Entry

| Field | Required | Description |
|-------|----------|-------------|
| `model` | Yes | Provider/model name (e.g., `openai/gpt-5-mini`) |
| `env` | No | Environment variable for API key |
| `api_key` | No | Direct API key (use `env` for security) |
| `api_base` | No | Custom API endpoint |
| `max_tokens` | No | Max response tokens |
| `temperature` | No | Sampling temperature (0.0-2.0) |
| `model_type` | No | `chat` or `responses` (default: `chat`) |

## API Keys

In `.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DSPY_API_KEY=your-api-key  # Optional: HTTP auth when running `dspy-cli serve --auth`
```

Reference in config:
```yaml
registry:
  openai:gpt-5-mini:
    env: OPENAI_API_KEY
```
