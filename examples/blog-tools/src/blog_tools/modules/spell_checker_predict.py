"""Example DSPy module using Predict."""

import dspy
from blog_tools.signatures.spell_checker import SpellCheckerSignature


class SpellCheckerPredict(dspy.Module):
    """
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(SpellCheckerSignature)

    def forward(self, **kwargs):
        return self.predictor(**kwargs)
