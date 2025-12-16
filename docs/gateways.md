# Gateways

Gateways separate HTTP endpoint concerns from DSPy pipeline logic. They let you transform webhook payloads, customize API paths, and schedule background jobs—all without changing your module's `forward()` method.

**Principle:** Pipelines should transform data, not load it.

## Quick Example

```python
from dspy_cli.gateway import APIGateway

class WebhookGateway(APIGateway):
    path = "/webhooks/slack"
    
    def to_pipeline_inputs(self, request):
        # Transform Slack webhook payload to pipeline format
        return {"text": request["event"]["text"]}
    
    def from_pipeline_output(self, output):
        # Wrap output for Slack API
        return {"response_type": "in_channel", "text": output["reply"]}

class SlackResponder(dspy.Module):
    gateway = WebhookGateway  # <-- Gateway registration
    
    def forward(self, text: str) -> dspy.Prediction:
        # Pure LLM logic - no Slack API knowledge
        return self.predict(text=text)
```

Without gateways, this module would be tightly coupled to Slack's payload format. With gateways, the module stays focused on the LLM task.

## Gateway Types

### APIGateway

Transform HTTP requests and responses. Use when you need to:

- Accept webhook payloads with nested data structures
- Customize the HTTP endpoint path or method
- Wrap outputs in API-specific response formats
- Add or remove authentication requirements

```python
from dspy_cli.gateway import APIGateway

class MyGateway(APIGateway):
    path = "/api/v2/analyze"           # Custom path (default: /{ModuleName})
    method = "POST"                     # HTTP method (default: POST)
    requires_auth = True                # Require authentication (default: True)
    request_model = MyRequestModel      # Optional: Pydantic model for validation
    response_model = MyResponseModel    # Optional: Pydantic model for response
    
    def to_pipeline_inputs(self, request):
        """Transform HTTP request to forward() kwargs."""
        return {"text": request["data"]["content"]}
    
    def from_pipeline_output(self, output):
        """Transform pipeline output to HTTP response."""
        return {"status": "success", "result": output}
```

### IdentityGateway

The default gateway when none is specified. Passes inputs and outputs unchanged for backward compatibility.

```python
# These are equivalent:
class MyModule(dspy.Module):
    def forward(self, text: str): ...

class MyModule(dspy.Module):
    gateway = IdentityGateway
    def forward(self, text: str): ...
```

### CronGateway

Schedule background pipeline execution. Use when you need to:

- Poll external APIs on a schedule
- Process queued items periodically
- Run batch jobs at specific times

```python
from dspy_cli.gateway import CronGateway

class DiscordModerationGateway(CronGateway):
    schedule = "*/5 * * * *"  # Every 5 minutes
    
    async def get_pipeline_inputs(self) -> list[dict]:
        """Fetch data from external source."""
        messages = await fetch_discord_messages()
        return [{"message": m["content"], "author": m["author"]} for m in messages]
    
    async def on_complete(self, inputs: dict, output) -> None:
        """Handle pipeline output."""
        if output["action"] == "delete":
            await delete_discord_message(inputs["_meta"]["message_id"])

class ModerateMessage(dspy.Module):
    gateway = DiscordModerationGateway
    
    def forward(self, message: str, author: str) -> dspy.Prediction:
        return self.classifier(message=message, author=author)
```

## Common Patterns

### Webhook Integration

Accept webhooks from external services (Slack, Discord, GitHub, etc.):

```python
class GitHubWebhookGateway(APIGateway):
    path = "/webhooks/github"
    requires_auth = False  # GitHub uses signature verification
    
    def to_pipeline_inputs(self, request):
        return {
            "action": request["action"],
            "issue_title": request["issue"]["title"],
            "issue_body": request["issue"]["body"],
        }
    
    def from_pipeline_output(self, output):
        return {"processed": True, "label": output["suggested_label"]}
```

### API Versioning

Expose the same module at multiple API versions:

```python
class V1Gateway(APIGateway):
    path = "/api/v1/summarize"
    
class V2Gateway(APIGateway):
    path = "/api/v2/summarize"
    
    def from_pipeline_output(self, output):
        # V2 adds metadata
        return {"summary": output["summary"], "version": "2.0"}
```

### Response Wrapping

Wrap all responses in a consistent envelope:

```python
class EnvelopeGateway(APIGateway):
    def from_pipeline_output(self, output):
        return {
            "success": True,
            "data": output,
            "timestamp": datetime.now().isoformat(),
        }
```

### Public Endpoints

Create endpoints that don't require authentication:

```python
class PublicGateway(APIGateway):
    path = "/public/health-check"
    requires_auth = False
```

## Gateway Discovery

Gateways are discovered automatically when you add a `gateway` class attribute to your module:

```python
class MyModule(dspy.Module):
    gateway = MyCustomGateway  # Must be a Gateway subclass, not an instance
```

If no gateway is specified, `IdentityGateway` is used automatically.

## Cron Schedule Format

CronGateway uses standard cron expressions:

| Expression | Description |
|------------|-------------|
| `* * * * *` | Every minute |
| `*/5 * * * *` | Every 5 minutes |
| `0 * * * *` | Every hour |
| `0 0 * * *` | Daily at midnight |
| `0 9 * * 1-5` | Weekdays at 9 AM |
| `0 0 1 * *` | First day of each month |

Format: `minute hour day-of-month month day-of-week`

## Best Practices

1. **Keep modules pure** — Modules should contain LLM logic only. Put API-specific transformations in gateways.

2. **Use descriptive paths** — `/webhooks/slack` is clearer than `/slack`.

3. **Default to requiring auth** — Set `requires_auth = False` only for public endpoints like webhooks with their own verification.

4. **Handle errors in on_complete** — CronGateway's `on_complete` should handle failures gracefully since there's no HTTP response to report errors.

5. **Pass metadata through** — Use `_meta` keys in inputs to carry IDs or context needed in `on_complete`:

    ```python
    async def get_pipeline_inputs(self):
        return [{"text": m["content"], "_meta": {"msg_id": m["id"]}}]
    
    async def on_complete(self, inputs, output):
        msg_id = inputs["_meta"]["msg_id"]
        await update_message(msg_id, output)
    ```
