"""Signature definitions for tagger."""

import dspy

class TaggerSignature(dspy.Signature):
    """
    Given a blog post, generate relevant tags for the post.
    """

    blog_post: str = dspy.InputField(desc="")
    tags: list = dspy.OutputField(desc="")
