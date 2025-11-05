import dspy
from blog_tools.signatures.tweet_extractor import TweetExtractorSignature


class TweetExtractorPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(TweetExtractorSignature)

    def forward(self, post: str, use_emojis: bool = False) -> dspy.Prediction:
        return self.predictor(post=post, use_emojis=use_emojis)
