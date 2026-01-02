"""Scheduler for cron-based gateway execution."""

import logging
from pathlib import Path
from typing import Any, Dict, List

import dspy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.gateway import CronGateway
from dspy_cli.server.execution import (
    _convert_dspy_types,
    execute_pipeline,
    execute_pipeline_batch,
)

logger = logging.getLogger(__name__)


class GatewayScheduler:
    """Manages cron-based gateway execution."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.scheduler = AsyncIOScheduler()
        self._jobs: Dict[str, str] = {}
        self._gateways: List[CronGateway] = []

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

        gateway.setup()

        async def execute_job():
            logger.info(f"CronGateway: executing {program_name}")
            instance = module.instantiate()

            try:
                inputs_list = await gateway.get_pipeline_inputs()
            except Exception as e:
                logger.error(f"CronGateway error fetching inputs for {program_name}: {e}", exc_info=True)
                return

            if not inputs_list:
                logger.debug(f"CronGateway: no inputs for {program_name}")
                return

            if gateway.use_batch:
                await self._execute_batch(
                    module=module,
                    instance=instance,
                    gateway=gateway,
                    lm=lm,
                    model_name=model_name,
                    program_name=program_name,
                    inputs_list=inputs_list,
                )
            else:
                await self._execute_sequential(
                    module=module,
                    instance=instance,
                    gateway=gateway,
                    lm=lm,
                    model_name=model_name,
                    program_name=program_name,
                    inputs_list=inputs_list,
                )

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
        self._gateways.append(gateway)
        batch_info = f" batch={gateway.use_batch}" if gateway.use_batch else ""
        threads_info = f" threads={gateway.num_threads}" if gateway.use_batch and gateway.num_threads else ""
        logger.info(f"Registered cron gateway: {program_name} schedule={gateway.schedule}{batch_info}{threads_info}")

    async def _execute_sequential(
        self,
        *,
        module: DiscoveredModule,
        instance: dspy.Module,
        gateway: CronGateway,
        lm: dspy.LM,
        model_name: str,
        program_name: str,
        inputs_list: List[Dict[str, Any]],
    ):
        """Execute pipeline sequentially for each input."""
        for raw_inputs in inputs_list:
            pipeline_inputs = gateway.extract_pipeline_kwargs(raw_inputs)
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
                try:
                    await gateway.on_error(raw_inputs, e)
                except Exception as hook_err:
                    logger.error(f"CronGateway on_error hook failed for {program_name}: {hook_err}", exc_info=True)

    async def _execute_batch(
        self,
        *,
        module: DiscoveredModule,
        instance: dspy.Module,
        gateway: CronGateway,
        lm: dspy.LM,
        model_name: str,
        program_name: str,
        inputs_list: List[Dict[str, Any]],
    ):
        """Execute pipeline in batch mode using DSPy's module.batch()."""
        logger.info(
            f"CronGateway: batch processing {len(inputs_list)} inputs "
            f"for {program_name} (threads={gateway.num_threads or 'default'})"
        )

        results = await execute_pipeline_batch(
            module=module,
            instance=instance,
            lm=lm,
            model_name=model_name,
            program_name=program_name,
            inputs_list=inputs_list,
            logs_dir=self.logs_dir,
            num_threads=gateway.num_threads,
            max_errors=gateway.max_errors,
        )

        for raw_inputs, output, error in results:
            if error:
                logger.error(f"CronGateway batch error for {program_name}: {error}", exc_info=False)
                try:
                    await gateway.on_error(raw_inputs, error)
                except Exception as hook_err:
                    logger.error(f"CronGateway on_error hook failed for {program_name}: {hook_err}", exc_info=True)
                continue
            try:
                await gateway.on_complete(raw_inputs, output)
            except Exception as e:
                logger.error(f"CronGateway on_complete error for {program_name}: {e}", exc_info=True)

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("GatewayScheduler started")

    def shutdown(self):
        """Shutdown the scheduler and all gateways."""
        for gateway in self._gateways:
            try:
                gateway.shutdown()
            except Exception as e:
                logger.error(f"Gateway shutdown error: {e}", exc_info=True)

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("GatewayScheduler shutdown")

    @property
    def job_count(self) -> int:
        """Number of registered cron jobs."""
        return len(self._jobs)
