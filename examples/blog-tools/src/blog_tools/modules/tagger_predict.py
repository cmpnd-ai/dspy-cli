import dspy
from blog_tools.signatures.tagger import TaggerSignature


class TaggerPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(TaggerSignature)

    def forward(self, blog_post: str) -> dspy.Prediction:
        return self.predictor(blog_post=blog_post)
