"""Cron Gateway for scheduled pipeline execution."""

from abc import abstractmethod
from typing import Any, Dict, List

from dspy_cli.gateway.base import Gateway
from dspy_cli.gateway.types import PipelineOutput


class CronGateway(Gateway):
    """Gateway for scheduled pipeline execution.
    
    Use this when your pipeline needs to:
    - Run on a schedule (e.g., every 5 minutes)
    - Load input data from external sources (APIs, databases, queues)
    - Take actions based on pipeline outputs (webhooks, API calls)
    
    Batch Mode:
        Set `use_batch = True` to process all inputs in parallel using DSPy's
        module.batch() method. Configure `num_threads` to control parallelism.
    
    Example:
        class DiscordModerationGateway(CronGateway):
            schedule = "*/5 * * * *"  # Every 5 minutes
            use_batch = True          # Enable parallel processing
            num_threads = 4           # Use 4 threads (default: None = DSPy default)
            
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
    use_batch: bool = False  # Enable batch processing with module.batch()
    num_threads: int | None = None  # Number of threads for batch (None = DSPy default)
    max_errors: int | None = None  # Max errors before stopping batch (None = no limit)

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
    async def on_complete(self, inputs: Dict[str, Any], output: PipelineOutput) -> None:
        """Handle pipeline output.
        
        Called after each successful pipeline execution.
        
        Args:
            inputs: The original input dict (including _meta if provided)
            output: The normalized output dict from execute_pipeline
        """
        ...

    async def on_error(self, inputs: Dict[str, Any], error: Exception) -> None:
        """Handle pipeline execution error.
        
        Called when pipeline execution fails for an input. Override to implement
        custom error handling (e.g., logging, alerting, retry logic).
        
        Default implementation does nothing - errors are still logged by the scheduler.
        
        Args:
            inputs: The original input dict (including _meta if provided)
            error: The exception that occurred during execution
        """
        pass

    @staticmethod
    def extract_pipeline_kwargs(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract pipeline kwargs from raw inputs, stripping _-prefixed keys.
        
        Use this to separate pipeline inputs from metadata like _meta.
        
        Args:
            inputs: Raw input dict that may contain _-prefixed keys
            
        Returns:
            Dict with only non-_-prefixed keys (suitable for forward())
        """
        return {k: v for k, v in inputs.items() if not k.startswith("_")}
