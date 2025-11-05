import dspy
from blog_tools.signatures.headline_generator import HeadlineGeneratorSignature

class HeadlineGeneratorPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(HeadlineGeneratorSignature)

    def forward(self, blog_post: str) -> list[str]:
        return self.predictor(blog_post=blog_post).headline_candidates
