#!/usr/bin/env python
"""Test the job posting classifier in dry run mode.

Usage:
    DRY_RUN=true python scripts/test_dry_run.py
"""

import asyncio
import logging
import os
import sys

# Ensure DRY_RUN is set before any imports
os.environ.setdefault("DRY_RUN", "true")

import dspy
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # Configure the LM
    lm = dspy.LM(
        model="openai/gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    dspy.configure(lm=lm)

    # Import after dspy is configured
    from discord_mod.gateways.job_posting_gateway import JobPostingGateway
    from discord_mod.modules.classify_job_posting import ClassifyJobPosting

    # Create instances
    gateway = JobPostingGateway()
    classifier = ClassifyJobPosting()

    logger.info("=" * 60)
    logger.info("Running job posting classifier in DRY RUN mode")
    logger.info("=" * 60)

    # Get sample inputs (dry run mode returns test data)
    inputs_list = await gateway.get_pipeline_inputs()

    for i, inputs in enumerate(inputs_list, 1):
        logger.info(f"\n--- Message {i}/{len(inputs_list)} ---")
        logger.info(f"Author: {inputs['author']}")
        logger.info(f"Channel: {inputs['channel_name']}")
        logger.info(f"Message: {inputs['message'][:100]}...")

        # Run classification
        result = classifier(
            message=inputs["message"],
            author=inputs["author"],
            channel_name=inputs["channel_name"],
        )

        output = result.toDict()
        logger.info(f"Intent: {output.get('intent')}")
        logger.info(f"Action: {output.get('action')}")
        logger.info(f"Reason: {output.get('reason')}")

        # Log what would happen (dry run)
        await gateway.on_complete(inputs, output)

    logger.info("\n" + "=" * 60)
    logger.info("Dry run complete - no Discord actions were taken")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
