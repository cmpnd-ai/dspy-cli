#!/usr/bin/env python
"""Test Discord integration with real LLM classification.

Usage:
    DRY_RUN=true python scripts/test_with_llm.py
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    import dspy

    # Configure LM
    lm = dspy.LM(
        model="openai/gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    dspy.configure(lm=lm)

    from discord_mod.gateways.job_posting_gateway import JobPostingGateway
    from discord_mod.modules.classify_job_posting import ClassifyJobPosting

    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    logger.info("=" * 60)
    logger.info("Discord + LLM Integration Test")
    logger.info(f"  DRY_RUN: {dry_run}")
    logger.info("=" * 60)

    gateway = JobPostingGateway()
    classifier = ClassifyJobPosting()

    # Fetch messages
    logger.info("\n[FETCH] Getting messages...")
    inputs_list = await gateway.get_pipeline_inputs()
    logger.info(f"Fetched {len(inputs_list)} messages")

    # Export
    output_file = f"classified_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results = []

    for i, inputs in enumerate(inputs_list, 1):
        logger.info(f"\n--- Message {i}/{len(inputs_list)} ---")
        logger.info(f"Author: {inputs['author']}")
        logger.info(f"Message: {inputs['message'][:100]}...")

        # Real LLM classification
        result = classifier(
            message=inputs["message"],
            author=inputs["author"],
            channel_name=inputs["channel_name"],
        )
        output = result.toDict()

        logger.info(f"[LLM] Intent: {output.get('intent')}")
        logger.info(f"[LLM] Action: {output.get('action')}")
        logger.info(f"[LLM] Reason: {output.get('reason')}")

        results.append({
            **inputs,
            "classification": output,
        })

        # Execute action (respects DRY_RUN)
        await gateway.on_complete(inputs, output)

    # Save results
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"\nExported results to {output_file}")

    # Summary
    actions = {}
    for r in results:
        action = r["classification"].get("action", "unknown")
        actions[action] = actions.get(action, 0) + 1

    logger.info("\n" + "=" * 60)
    logger.info("Summary:")
    for action, count in sorted(actions.items()):
        logger.info(f"  {action}: {count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
