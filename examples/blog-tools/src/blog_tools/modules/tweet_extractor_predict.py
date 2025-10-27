"""Example DSPy module using Predict."""

import dspy
from blog_tools.signatures.tweet_extractor import TweetExtractorSignature


class TweetExtractorPredict(dspy.Module):
    """
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(TweetExtractorSignature)

    def forward(self, **kwargs):
        return self.predictor(**kwargs)
