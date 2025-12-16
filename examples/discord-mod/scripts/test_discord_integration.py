#!/usr/bin/env python
"""Test Discord API integration with mocked LLM responses.

Tests the gateway's Discord interactions (fetch + actions) without LLM calls.

Usage:
    # Dry run with sample data (no Discord API calls)
    DRY_RUN=true python scripts/test_discord_integration.py

    # Test real Discord fetch, dry run actions
    DISCORD_BOT_TOKEN=... DISCORD_CHANNEL_IDS=123,456 DRY_RUN=true python scripts/test_discord_integration.py
    
    # Test real Discord fetch AND actions (careful!)
    DISCORD_BOT_TOKEN=... DISCORD_CHANNEL_IDS=123,456 python scripts/test_discord_integration.py
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

# Mocked LLM responses - maps message content patterns to outputs
MOCK_CLASSIFICATIONS = {
    "hiring": {"intent": "post_job", "action": "move", "reason": "Job posting in general channel"},
    "looking for work": {"intent": "seek_job", "action": "move", "reason": "Job seeking in general channel"},
    "MAKE $": {"intent": "other", "action": "delete", "reason": "Spam detected"},
    "_default": {"intent": "other", "action": "allow", "reason": "Normal conversation"},
}


def mock_classify(message: str) -> dict:
    """Return mocked classification based on message content."""
    message_lower = message.lower()
    for pattern, result in MOCK_CLASSIFICATIONS.items():
        if pattern.lower() in message_lower:
            return result
    return MOCK_CLASSIFICATIONS["_default"]


async def main():
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    has_token = bool(os.environ.get("DISCORD_BOT_TOKEN"))
    
    logger.info("=" * 60)
    logger.info("Discord Integration Test")
    logger.info(f"  DRY_RUN: {dry_run}")
    logger.info(f"  Has Discord token: {has_token}")
    logger.info("=" * 60)

    # Import gateway
    from discord_mod.gateways.job_posting_gateway import JobPostingGateway
    
    gateway = JobPostingGateway()

    # Test 1: Fetch messages
    logger.info("\n[TEST 1] Fetching messages...")
    inputs_list = await gateway.get_pipeline_inputs()
    logger.info(f"Fetched {len(inputs_list)} messages")

    # Export to JSON for inspection
    output_file = f"fetched_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(inputs_list, f, indent=2, ensure_ascii=False)
    logger.info(f"Exported messages to {output_file}")
    
    if not inputs_list:
        logger.warning("No messages to process. Check DISCORD_CHANNEL_IDS or use DRY_RUN=true for samples.")
        return

    # Test 2: Process each message with mocked LLM
    logger.info("\n[TEST 2] Processing messages with mocked classifier...")
    for i, inputs in enumerate(inputs_list, 1):
        logger.info(f"\n--- Message {i}/{len(inputs_list)} ---")
        logger.info(f"Author: {inputs['author']}")
        logger.info(f"Channel: {inputs['channel_name']}")
        logger.info(f"Message: {inputs['message'][:80]}...")
        
        # Mock the LLM classification
        output = mock_classify(inputs["message"])
        logger.info(f"[MOCKED] Intent: {output['intent']}, Action: {output['action']}")
        logger.info(f"[MOCKED] Reason: {output['reason']}")

        # Test 3: Execute action (respects DRY_RUN)
        await gateway.on_complete(inputs, output)

    # Test 4: Summary
    logger.info("\n" + "=" * 60)
    logger.info("Integration test complete")
    if dry_run:
        logger.info("DRY_RUN was enabled - no Discord actions were executed")
    else:
        logger.info("⚠️  LIVE MODE - actions were executed on Discord!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
