"""Signature definitions for tweet_extractor."""

import dspy

class TweetExtractorSignature(dspy.Signature):
    """
    Given a blog post, generate 3 candidates for sharing the post on Twitter
    """

    post: str = dspy.InputField(desc="")
    tweet_candidates: list = dspy.OutputField(desc="")
