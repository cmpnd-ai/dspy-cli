import dspy


class AsyncPredict(dspy.Module):
    """Same as SimplePredict but with aforward. Used to test async path."""
    def __init__(self):
        self.predict = dspy.Predict("question:str -> answer:str")

    def forward(self, question: str) -> dspy.Prediction:
        return self.predict(question=question)

    async def aforward(self, question: str) -> dspy.Prediction:
        return await self.predict.acall(question=question)
