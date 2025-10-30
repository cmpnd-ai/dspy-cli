"""Example DSPy module using Predict."""

import dspy
from dspy_code_review_agent.signatures.review_pr import ReviewPR


class PRReviewer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(ReviewPR)

    def forward(self, pr_metadata, file_list):
        return self.predictor(pr_metadata=pr_metadata, file_list=file_list)
