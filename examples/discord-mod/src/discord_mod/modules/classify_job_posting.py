from typing import Literal

import dspy

from discord_mod.gateways.job_posting_gateway import JobPostingGateway


class ClassifyJobPosting(dspy.Module):
    """Classify Discord messages as job postings, job-seeking, or general chat."""

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
        return self.classifier(
            message=message,
            author=author,
            channel_name=channel_name,
        )


class JobPostingSignature(dspy.Signature):
    """Classify a Discord message and determine moderation action.

    The subject of the Discord server is DSPy, the framework for building and optimizing LLM applications. The server has nothing to do with blockchain, crypto, or NFTs, and these are generally spam.
    
    A job posting or job seeking message will express the primary intent of introducing the user, their qualifications/openness to work, and their availability for hire, or availability to hire others"""

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
