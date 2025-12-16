"""Cron Gateway for scheduled pipeline execution."""

from abc import abstractmethod
from typing import Any, Dict, List

from dspy_cli.gateway.base import Gateway


class CronGateway(Gateway):
    """Gateway for scheduled pipeline execution.
    
    Use this when your pipeline needs to:
    - Run on a schedule (e.g., every 5 minutes)
    - Load input data from external sources (APIs, databases, queues)
    - Take actions based on pipeline outputs (webhooks, API calls)
    
    Example:
        class DiscordModerationGateway(CronGateway):
            schedule = "*/5 * * * *"  # Every 5 minutes
            
            async def get_pipeline_inputs(self) -> list[dict]:
                # Fetch unmoderated messages from Discord API
                messages = await fetch_recent_messages()
                return [{"message": m["content"], "author": m["author"]} for m in messages]
            
            async def on_complete(self, inputs: dict, output) -> None:
                # Take action based on moderation result
                if output.action == "delete":
                    await delete_message(inputs["_meta"]["message_id"])
    """

    schedule: str  # Cron expression like "*/5 * * * *"

    @abstractmethod
    async def get_pipeline_inputs(self) -> List[Dict[str, Any]]:
        """Fetch input data from external sources.
        
        Called on each scheduled execution. Returns a list of input dicts,
        and the pipeline will be executed once for each.
        
        Returns:
            List of input dictionaries for pipeline execution.
            Each dict should contain the kwargs for forward().
            Include "_meta" key for data needed in on_complete but not by the pipeline.
        """
        ...

    @abstractmethod
    async def on_complete(self, inputs: Dict[str, Any], output: Any) -> None:
        """Handle pipeline output.
        
        Called after each successful pipeline execution.
        
        Args:
            inputs: The original input dict (including _meta if provided)
            output: The normalized output dict from execute_pipeline
        """
        ...
