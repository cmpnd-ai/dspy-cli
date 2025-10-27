"""Signature definitions for tagger."""

import dspy

class TaggerSignature(dspy.Signature):
    """
    """

    blog_post: str = dspy.InputField(desc="")
    tags: list = dspy.OutputField(desc="")
