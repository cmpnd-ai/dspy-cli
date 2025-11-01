"""Signature definitions for headline_generator."""

import dspy

class HeadlineGeneratorSignature(dspy.Signature):
    """
    Given a blog post, generate candidate headlines for the post.
    """

    blog_post: str = dspy.InputField(desc="")
    headline_candidates: list[str] = dspy.OutputField(desc="Potential headlines for the blog post.")
