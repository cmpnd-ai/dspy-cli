"""Example DSPy module using Predict."""

import dspy
from dotenv import load_dotenv
from code_review_agent.signatures.review_pr import PRReview, ReviewPR
from code_review_agent.utils import download_and_format_pr, build_github_tools

class PRReviewer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.ReAct(ReviewPR, tools=build_github_tools())

    async def aforward(self, repo: str, pr_number: int) -> PRReview:
        """
        Review a PR from repository name and PR number.
        
        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number
            github_token: Optional GitHub token (uses GITHUB_TOKEN env var if not provided)
        
        Returns:
            PR review result
        """
        pr_data = download_and_format_pr(repo=repo, pr_number=pr_number)
        
        result = await self.predictor.acall(
            pr_metadata=pr_data['pr_metadata'],
            file_list=pr_data['files']
        )
        return result.pr_review
        


async def main():
    pr_reviewer = PRReviewer()
    dspy.configure(lm=dspy.LM("gpt-5-nano", temperature=1.0, max_tokens=16000))
    
    tasks = [
        pr_reviewer.aforward("stanfordnlp/dspy", 8902),
        pr_reviewer.aforward("stanfordnlp/dspy", 9003),
    ]
    completed_tasks = await asyncio.gather(*tasks)
    print(completed_tasks)

# Usage
if __name__ == "__main__":
    import asyncio
    import mlflow

    mlflow.set_tracking_uri("http://127.0.0.1:5001")
    mlflow.dspy.autolog()
    load_dotenv()

    asyncio.run(main())
