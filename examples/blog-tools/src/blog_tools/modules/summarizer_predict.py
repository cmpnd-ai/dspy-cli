"""Example DSPy module using Predict."""

import dspy
from blog_tools.signatures.summarizer import SummarizerSignature


class SummarizerPredict(dspy.Module):
    """
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(SummarizerSignature)

    def forward(self, **kwargs):
        return self.predictor(**kwargs)
