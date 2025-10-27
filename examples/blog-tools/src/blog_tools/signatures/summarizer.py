"""Signature definitions for summarizer."""

import dspy
from typing import Literal

class SummarizerSignature(dspy.Signature):
    """
    Given a blog post, generate a short summary of 2-3 sentences.
    """

    blog_post: str = dspy.InputField(desc="The content of the blog post to summarize.")
    summary_length: Literal['short', 'medium', 'long'] = dspy.InputField()
    summary: str = dspy.OutputField(desc="A summary of the blog post.")
