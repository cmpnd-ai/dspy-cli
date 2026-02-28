import dspy


class SimplePredict(dspy.Module):
    """Single-predict module. Used to test sync fallback path."""
    def __init__(self):
        self.predict = dspy.Predict("question:str -> answer:str")

    def forward(self, question: str) -> dspy.Prediction:
        return self.predict(question=question)
