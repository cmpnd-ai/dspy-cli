# Discord Moderation Bot

A DSPy project that demonstrates the **Gateway pattern** for separating Discord API concerns from LLM pipeline logic.

## Overview

This bot monitors Discord channels for job postings and automatically:
- **Classifies** messages as job postings, job-seeking, or general chat
- **Moves** job posts to a dedicated jobs channel
- **Flags** suspicious content for manual review
- **Deletes** spam or rule violations

### The Gateway Pattern

The key insight is that **pipelines should transform data, not load it**:

```
┌─────────────────────────────────────────────────────────────────┐
│                      JobPostingGateway                          │
│  ┌──────────────────┐              ┌──────────────────────────┐ │
│  │ get_pipeline_    │              │      on_complete()       │ │
│  │    inputs()      │              │                          │ │
│  │                  │              │  • Move to jobs channel  │ │
│  │  • Fetch msgs    │              │  • Send DM to author     │ │
│  │  • Filter bots   │              │  • Add reaction flag     │ │
│  │  • Extract data  │              │  • Delete spam           │ │
│  └────────┬─────────┘              └──────────▲───────────────┘ │
└───────────│────────────────────────────────────│────────────────┘
            │                                    │
            ▼                                    │
┌─────────────────────────────────────────────────────────────────┐
│                    ClassifyJobPosting                           │
│                                                                 │
│   Pure LLM logic - no Discord API knowledge                     │
│                                                                 │
│   Input: message, author, channel_name                          │
│   Output: intent, action, reason                                │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
src/discord_mod/
├── modules/
│   └── classify_job_posting.py  # Pure LLM classification logic
├── gateways/
│   └── job_posting_gateway.py   # Discord API interactions (CronGateway)
└── utils/
    └── discord_client.py        # Discord REST API client
```

## Setup

1. **Create a Discord bot** at https://discord.com/developers/applications

2. **Configure environment variables** in `.env`:
   ```bash
   # Required
   DISCORD_BOT_TOKEN=your-bot-token           # Bot authentication token
   DISCORD_CHANNEL_IDS=123456789,987654321    # Channels to monitor (comma-separated)
   DISCORD_JOBS_CHANNEL_ID=111222333          # Channel to move job posts to
   OPENAI_API_KEY=your-openai-key             # LLM API key

   DISCORD_AUDIT_CHANNEL_ID=444555666         # Channel for moderation audit logs

   # Optional
   DRY_RUN=true                               # Log actions without executing (default: false)
   USE_SAMPLE_DATA=true                       # Use sample messages instead of Discord API
   ```

3. **Install dependencies**:
   ```bash
   uv sync
   ```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | Bot authentication token from Discord Developer Portal |
| `DISCORD_CHANNEL_IDS` | ✅ | Comma-separated channel IDs to monitor |
| `DISCORD_JOBS_CHANNEL_ID` | ✅ | Channel ID where job posts are moved to |
| `OPENAI_API_KEY` | ✅ | OpenAI API key for LLM classification |
| `DISCORD_AUDIT_CHANNEL_ID` | ✅ | Channel for audit logs (move/flag/delete actions) |
| `DRY_RUN` | ❌ | Set to `true` to log actions without executing (default: `false`) |
| `USE_SAMPLE_DATA` | ❌ | Set to `true` to use sample messages for testing |

## Running

Start the server with cron scheduling enabled:

```bash
dspy-cli serve
```

The `ClassifyJobPosting` module uses a `CronGateway` with `schedule = "*/5 * * * *"`, so it will:
1. Poll the configured channels every 5 minutes
2. Classify each new message
3. Take the appropriate moderation action


## Deployment:
fly volumes create processed_data --size 1
fly scale count 1
fly deploy --ha=false

fly secrets set \
  DISCORD_BOT_TOKEN="<Your token>" \
  DISCORD_CHANNEL_IDS="<>" \
  DISCORD_JOBS_CHANNEL_ID="<>" \
  DISCORD_AUDIT_CHANNEL_ID="<Channel Id to send notifications to>" \
  OPENAI_API_KEY="<Your openai key>" \
  DRY_RUN="false"


## How It Works

### The Module (Pure LLM Logic)

```python
class ClassifyJobPosting(dspy.Module):
    gateway = JobPostingGateway  # <-- Gateway registration

    def forward(self, message: str, author: str, channel_name: str):
        # Only LLM classification logic here
        return self.classifier(message=message, author=author, channel_name=channel_name)
```

### The Gateway (Discord API Concerns)

```python
class JobPostingGateway(CronGateway):
    schedule = "*/5 * * * *"

    async def get_pipeline_inputs(self):
        # Fetch from Discord API, transform to pipeline inputs
        messages = await self.client.get_recent_messages(channel_id)
        return [{"message": m["content"], "_meta": {"message_id": m["id"]}} ...]

    async def on_complete(self, inputs, output):
        # Take action based on classification
        if output["action"] == "move":
            await self.client.send_message(jobs_channel, inputs["message"])
            await self.client.delete_message(inputs["_meta"]["message_id"])
```

## Classification Actions

| Action | Description |
|--------|-------------|
| `allow` | Message is appropriate for the channel |
| `move` | Job posting should be in the jobs channel |
| `flag` | Add ⚠️ reaction for manual review |
| `delete` | Remove spam or rule violations, DM the author |

## Testing

Run tests:
```bash
pytest
```

## Learn More

- [Gateway Documentation](https://dspy-cli.readthedocs.io/gateways/)
- [DSPy Documentation](https://dspy.ai)
