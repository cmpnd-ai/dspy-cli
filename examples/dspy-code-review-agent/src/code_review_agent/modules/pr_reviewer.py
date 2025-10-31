"""Example DSPy module using Predict."""

import dspy
from code_review_agent.signatures.review_pr import ReviewPR, ReviewPRWithTools


class PRReviewer(dspy.Module):
    def __init__(self, tools: list[dspy.Tool], max_iters: int = 5):
        super().__init__()
        self.tools = tools
        self.max_iters = max_iters
        self.predictor = dspy.ReAct(
                ReviewPRWithTools, 
                tools=self.tools,
                max_iters=self.max_iters
            )

    async def aforward(self, pr_metadata, file_list):
        print("PRReviewer aforward")
        return await self.predictor.acall(pr_metadata=pr_metadata, file_list=file_list)
