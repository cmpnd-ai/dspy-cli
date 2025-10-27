"""Example DSPy module using Predict."""

import dspy
from blog_tools.signatures.tagger import TaggerSignature


class TaggerCoT(dspy.Module):
    """
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.ChainOfThought(TaggerSignature)

    def forward(self, **kwargs):
        return self.predictor(**kwargs)
