"""Scheduler for cron-based gateway execution."""

import logging
from pathlib import Path
from typing import Dict

import dspy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.gateway import CronGateway
from dspy_cli.server.execution import _convert_dspy_types, execute_pipeline

logger = logging.getLogger(__name__)


class GatewayScheduler:
    """Manages cron-based gateway execution."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.scheduler = AsyncIOScheduler()
        self._jobs: Dict[str, str] = {}

    def register_cron_gateway(
        self,
        module: DiscoveredModule,
        gateway: CronGateway,
        lm: dspy.LM,
        model_name: str,
    ):
        """Register a CronGateway for scheduled execution.

        Args:
            module: DiscoveredModule metadata
            gateway: CronGateway instance with schedule and callbacks
            lm: Language model instance for this program
            model_name: Model name for logging
        """
        program_name = module.name

        async def execute_job():
            logger.info(f"CronGateway: executing {program_name}")
            instance = module.instantiate()

            try:
                inputs_list = await gateway.get_pipeline_inputs()
            except Exception as e:
                logger.error(f"CronGateway error fetching inputs for {program_name}: {e}", exc_info=True)
                return

            for raw_inputs in inputs_list:
                # Strip _meta from inputs before passing to pipeline
                # _meta is used by gateway.on_complete() but not by forward()
                pipeline_inputs = {k: v for k, v in raw_inputs.items() if not k.startswith("_")}
                inputs = _convert_dspy_types(pipeline_inputs, module)
                try:
                    output = await execute_pipeline(
                        module=module,
                        instance=instance,
                        lm=lm,
                        model_name=model_name,
                        program_name=program_name,
                        inputs=inputs,
                        logs_dir=self.logs_dir,
                    )
                    await gateway.on_complete(raw_inputs, output)
                except Exception as e:
                    logger.error(f"CronGateway error for {program_name}: {e}", exc_info=True)

        trigger = CronTrigger.from_crontab(gateway.schedule)
        job_id = f"cron_{program_name}"
        # max_instances=1: Don't start a new run if previous is still running
        # coalesce=True: If multiple runs were missed, only run once
        self.scheduler.add_job(
            execute_job,
            trigger,
            id=job_id,
            max_instances=1,
            coalesce=True,
        )
        self._jobs[program_name] = job_id
        logger.info(f"Registered cron gateway: {program_name} schedule={gateway.schedule}")

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("GatewayScheduler started")

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("GatewayScheduler shutdown")

    @property
    def job_count(self) -> int:
        """Number of registered cron jobs."""
        return len(self._jobs)
