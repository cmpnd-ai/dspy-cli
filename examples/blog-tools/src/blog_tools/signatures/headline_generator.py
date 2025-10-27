"""Signature definitions for headline_generator."""

import dspy

class HeadlineGeneratorSignature(dspy.Signature):
    """
    """

    blog_post: str = dspy.InputField(desc="")
    headline_candidates: list[str] = dspy.OutputField(desc="Potential headlines for the blog post.")
