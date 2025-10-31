"""Signature definitions for summarizer."""

import dspy
from typing import Literal, Optional

class SummarizerSignature(dspy.Signature):
    """
    Given a blog post, generate a short summary of 2-3 sentences.
    """

    blog_post: str = dspy.InputField(desc="The content of the blog post to summarize.")
    summary_length: Literal['short', 'medium', 'long'] = dspy.InputField()
    tone: Optional[str] = dspy.InputField(desc="The tone of the summary, e.g., formal, casual, humorous.")
    summary: str = dspy.OutputField(desc="A summary of the blog post.")
