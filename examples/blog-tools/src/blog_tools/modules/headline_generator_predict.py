"""Example DSPy module using Predict."""

import dspy
from blog_tools.signatures.headline_generator import HeadlineGeneratorSignature


class HeadlineGeneratorPredict(dspy.Module):
    """
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(HeadlineGeneratorSignature)

    def forward(self, **kwargs):
        return self.predictor(**kwargs)
