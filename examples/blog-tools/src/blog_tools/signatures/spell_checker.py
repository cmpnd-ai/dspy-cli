"""Signature definitions for spell_checker."""

import dspy

class SpellCheckerSignature(dspy.Signature):
    """
    Check a blog post for spelling errors and return the misspelled words with corrections.
    """

    blog_post: str = dspy.InputField()
    corrections: list[dict[str, str]] = dspy.OutputField(desc="A list of corrections for misspelled words.")
