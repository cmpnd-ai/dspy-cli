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

**`app_id`** (required) - Unique identifier

**`models.default`** (required) - Default model alias

**`models.registry`** (required) - Available models

### Registry Entry

**`model`** (required) - Provider/model name (e.g., `openai/gpt-5-mini`)

**`env`** (optional) - Environment variable for API key

**`api_key`** (optional) - Direct API key (use `env` for security)

**`api_base`** (optional) - Custom API endpoint

**`max_tokens`** (optional) - Max response tokens

**`temperature`** (optional) - Sampling temperature (0.0-2.0)

**`model_type`** (optional) - `chat` or `responses` (default: `chat`)

**`program_models`** (optional) - Per-program model overrides

## API Keys

In `.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Reference in config:
```yaml
registry:
  openai:gpt-5-mini:
    env: OPENAI_API_KEY
```
