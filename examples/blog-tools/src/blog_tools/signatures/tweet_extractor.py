"""Signature definitions for tweet_extractor."""

import dspy

class TweetExtractorSignature(dspy.Signature):
    """
    Given a blog post, generate 3 candidates for sharing the post on Twitter
    """

    post: str = dspy.InputField(desc="")
    use_emojis: bool = dspy.InputField(desc="Whether or not to include emojis in the tweets.")
    tweet_candidates: list = dspy.OutputField(desc="")
