"""Job posting classifier module - pure LLM logic, no Discord API knowledge."""

from typing import Literal

import dspy

from discord_mod.gateways.job_posting_gateway import JobPostingGateway


class ClassifyJobPosting(dspy.Module):
    """Classify Discord messages as job postings, job-seeking, or general chat.
    
    This module contains only the LLM classification logic.
    The gateway handles Discord API interactions (fetching messages, taking actions).
    """

    gateway = JobPostingGateway

    def __init__(self):
        super().__init__()
        self.classifier = dspy.ChainOfThought(JobPostingSignature)

    def forward(
        self,
        message: str,
        author: str,
        channel_name: str,
    ) -> dspy.Prediction:
        """Classify a message and determine the appropriate action.
        
        Args:
            message: The Discord message content
            author: The message author's username
            channel_name: The channel where the message was posted
            
        Returns:
            Prediction with intent, action, and reason fields
        """
        return self.classifier(
            message=message,
            author=author,
            channel_name=channel_name,
        )


class JobPostingSignature(dspy.Signature):
    """Classify a Discord message and determine moderation action.
    
    A Job posting or job seeking message will explicitly state:
    1. A user's resume/openness to work
    2. A user's availability to hire (e.g. "I'm looking for a software engineer to hire immediately")"""

    message: str = dspy.InputField(desc="The Discord message content")
    author: str = dspy.InputField(desc="The message author's username")
    channel_name: str = dspy.InputField(desc="The channel where the message was posted")

    intent: Literal["post_job", "seek_job", "other"] = dspy.OutputField(
        desc="The user's intent: 'post_job' if offering a job, 'seek_job' if looking for work, 'other' for general discussion"
    )
    action: Literal["allow", "move", "flag", "delete"] = dspy.OutputField(
        desc="Action to take: 'allow' if appropriate for channel, 'move' if should be in jobs channel, 'flag' for manual review, 'delete' if spam/violation"
    )
    reason: str = dspy.OutputField(
        desc="Brief explanation of the classification and recommended action"
    )
