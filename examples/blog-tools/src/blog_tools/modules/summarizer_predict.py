import dspy
from blog_tools.signatures.summarizer import SummarizerSignature
from typing import Literal, Optional


class SummarizerPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(SummarizerSignature)

    def forward(
            self, 
            blog_post: str, 
            summary_length: Literal['short', 'medium', 'long'], 
            tone: Optional[str]
            ) -> dspy.Prediction:
        return self.predictor(blog_post=blog_post, summary_length=summary_length, tone=tone)