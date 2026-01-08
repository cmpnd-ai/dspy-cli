from typing import Literal

import dspy


class ClassifyJobPosting(dspy.Module):
    """Classify Discord messages as job postings, job-seeking, or general chat."""

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
    """Classify a Discord message for a DSPy (LLM framework) server.

    DELETE any message mentioning blockchain, crypto, NFTs, or Web3 - these are always spam.
    MOVE job postings/seeking to #jobs channel unless already there. Also include long introductions that seem to be more about posting qualifications than just saying hi.
    ALLOW general discussion about DSPy, help questions, or casual mentions of work."""

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
