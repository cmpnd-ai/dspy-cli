"""CronGateway for Discord job posting moderation.

This gateway handles all Discord API interactions:
- Fetching new messages from monitored channels
- Taking moderation actions based on classification results

The pipeline module (ClassifyJobPosting) stays pure - it only knows about
message content, not Discord API details.
"""

import logging
import os
from typing import Any, Dict, List

from dspy_cli.gateway import CronGateway

from discord_mod.utils.discord_client import DiscordClient

logger = logging.getLogger(__name__)


class JobPostingGateway(CronGateway):
    """Poll Discord channels and moderate job postings.
    
    Configuration via environment variables:
        DISCORD_BOT_TOKEN: Bot authentication token
        DISCORD_CHANNEL_IDS: Comma-separated channel IDs to monitor
        DISCORD_JOBS_CHANNEL_ID: Channel ID to move job posts to
        DRY_RUN: Set to "true" to log actions without executing them
    """

    schedule = "*/5 * * * *"  # Every 5 minutes

    def __init__(self):
        # Validate required environment variables
        missing = []
        if not os.environ.get("DISCORD_BOT_TOKEN"):
            missing.append("DISCORD_BOT_TOKEN")
        if not os.environ.get("DISCORD_CHANNEL_IDS"):
            missing.append("DISCORD_CHANNEL_IDS")
        if not os.environ.get("DISCORD_JOBS_CHANNEL_ID"):
            missing.append("DISCORD_JOBS_CHANNEL_ID")
        if not os.environ.get("DISCORD_AUDIT_CHANNEL_ID"):
            missing.append("DISCORD_AUDIT_CHANNEL_ID")
        
        if missing:
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            logger.error("Set these variables")
            raise SystemExit(1)

        # DRY_RUN: Log actions instead of executing them
        self.dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"
        
        self.client = DiscordClient(
            token=os.environ.get("DISCORD_BOT_TOKEN", ""),
        )
        self.channel_ids = os.environ.get("DISCORD_CHANNEL_IDS", "").split(",")
        self.jobs_channel_id = os.environ.get("DISCORD_JOBS_CHANNEL_ID")
        self.audit_channel_id = os.environ.get("DISCORD_AUDIT_CHANNEL_ID")
        
        if self.dry_run:
            logger.info("DRY_RUN mode - actions will be logged, not executed")

    async def get_pipeline_inputs(self) -> List[Dict[str, Any]]:
        """Fetch recent unprocessed messages from monitored channels."""
        inputs = []

        for channel_id in self.channel_ids:
            if not channel_id.strip():
                continue

            messages = await self.client.get_recent_messages(
                channel_id=channel_id.strip(),
                limit=20,
            )

            for msg in messages:
                if msg.get("author", {}).get("bot", False):
                    continue

                inputs.append({
                    "message": msg["content"],
                    "author": msg["author"]["username"],
                    "channel_name": msg.get("channel_name", "unknown"),
                    "_meta": {
                        "message_id": msg["id"],
                        "channel_id": channel_id.strip(),
                        "author_id": msg["author"]["id"],
                    },
                })

        logger.info(f"Fetched {len(inputs)} messages to classify")
        return inputs

    async def on_complete(self, inputs: Dict[str, Any], output: Any) -> None:
        """Take moderation action based on classification result."""
        meta = inputs.get("_meta", {})
        message_id = meta.get("message_id")
        channel_id = meta.get("channel_id")
        author = inputs.get("author", "unknown")

        action = output.get("action", "allow")
        intent = output.get("intent", "other")
        reason = output.get("reason", "")

        logger.info(
            f"Message {message_id} from {author}: "
            f"intent={intent}, action={action}, reason={reason}"
        )

        if action == "allow":
            return

        if self.dry_run:
            await self._log_dry_run_action(action, inputs, output)
            await self._send_audit_log(action, inputs, output, dry_run=True)
            return

        if action == "move" and self.jobs_channel_id:
            original_content = inputs["message"]
            await self.client.send_message(
                channel_id=self.jobs_channel_id,
                content=f"**Moved from <#{channel_id}>**\n"
                        f"*Originally posted by {author}:*\n\n{original_content}",
            )
            await self.client.delete_message(
                channel_id=channel_id,
                message_id=message_id,
            )
            await self.client.send_dm(
                user_id=meta["author_id"],
                content=f"Your job posting was moved to <#{self.jobs_channel_id}>. "
                        f"Please post job-related content there in the future.",
            )
            logger.info(f"Moved message {message_id} to jobs channel")
            await self._send_audit_log(action, inputs, output, dry_run=False)

        elif action == "flag":
            await self.client.add_reaction(
                channel_id=channel_id,
                message_id=message_id,
                emoji="⚠️",
            )
            logger.info(f"Flagged message {message_id} for review")
            await self._send_audit_log(action, inputs, output, dry_run=False)

        elif action == "delete":
            await self.client.delete_message(
                channel_id=channel_id,
                message_id=message_id,
            )
            await self.client.send_dm(
                user_id=meta["author_id"],
                content=f"Your message was removed: {reason}\n\n"
                        f"If you believe this was a false positive, please let us know.",
            )
            logger.info(f"Deleted message {message_id}")
            await self._send_audit_log(action, inputs, output, dry_run=False)

    async def _send_audit_log(
        self, action: str, inputs: Dict[str, Any], output: Any, dry_run: bool
    ) -> None:
        """Send audit log to moderator channel."""
        if not self.audit_channel_id:
            return

        meta = inputs.get("_meta", {})
        message_id = meta.get("message_id", "unknown")
        channel_id = meta.get("channel_id", "unknown")
        author = inputs.get("author", "unknown")
        intent = output.get("intent", "unknown")
        reason = output.get("reason", "")
        message_preview = inputs.get("message", "")[:100]

        dry_run_prefix = "🔍 **[DRY RUN]** " if dry_run else ""
        
        action_emoji = {"move": "📦", "flag": "⚠️", "delete": "🗑️"}.get(action, "❓")

        audit_message = (
            f"{dry_run_prefix}{action_emoji} **Action: {action.upper()}**\n"
            f"**Author:** {author}\n"
            f"**Channel:** <#{channel_id}>\n"
            f"**Intent:** {intent}\n"
            f"**Reason:** {reason}\n"
            f"**Message:** `{message_preview}{'...' if len(inputs.get('message', '')) > 100 else ''}`\n"
            f"**Message ID:** {message_id}"
        )

        try:
            await self.client.send_message(
                channel_id=self.audit_channel_id,
                content=audit_message,
            )
        except Exception as e:
            logger.warning(f"Failed to send audit log: {e}")

    async def _log_dry_run_action(
        self, action: str, inputs: Dict[str, Any], output: Any
    ) -> None:
        """Log what would happen without executing."""
        meta = inputs.get("_meta", {})
        message_id = meta.get("message_id")
        channel_id = meta.get("channel_id")
        author = inputs.get("author", "unknown")
        reason = output.get("reason", "")

        if action == "move":
            logger.info(
                f"[DRY RUN] WOULD move message {message_id} from {author} "
                f"to jobs channel {self.jobs_channel_id}"
            )
            logger.info(f"[DRY RUN] WOULD delete original from #{channel_id}")
            logger.info(f"[DRY RUN] WOULD DM {meta.get('author_id')} about the move")

        elif action == "flag":
            logger.info(
                f"[DRY RUN] WOULD add ⚠️ reaction to message {message_id}"
            )

        elif action == "delete":
            logger.info(
                f"[DRY RUN] WOULD delete message {message_id}: {reason}"
            )
            logger.info(f"[DRY RUN] WOULD DM {meta.get('author_id')}: {reason}")
