"""Example DSPy module using Predict."""

import os
import re
from typing import Optional
import dspy
from mcp import StdioServerParameters
from code_review_agent.signatures.review_pr import ReviewPR, ReviewPRWithTools
from code_review_agent.utils import load_demo_pr, build_dspy_tools, MCPManager


class PRReviewer(dspy.Module):
    def __init__(self, tools: list[dspy.Tool] | None = None, max_iters: int = 5):
        super().__init__()
        self.tools = tools
        self.max_iters = max_iters
        if tools:
            self.predictor = dspy.ReAct(
                ReviewPRWithTools,
                tools=self.tools,
                max_iters=self.max_iters
            )
        else:
            self.predictor = None

    async def aforward(self, repo: str, pr_number: int, github_token: Optional[str] = None):
        """
        Review a PR from repository name and PR number.
        
        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number
            github_token: Optional GitHub token (uses GITHUB_TOKEN env var if not provided)
        
        Returns:
            PR review result
        """
        return await self.review_from_repo_and_number(repo, pr_number, github_token)
    
    async def aforward_with_data(self, pr_metadata, file_list):
        """
        Review a PR with pre-loaded metadata and files.
        Use this when you already have the PR data loaded.
        """
        print("PRReviewer aforward_with_data")
        return await self.predictor.acall(pr_metadata=pr_metadata, file_list=file_list)
    
    async def review_from_link(self, pr_link: str, github_token: Optional[str] = None):
        """
        Review a PR from a GitHub link.
        
        Args:
            pr_link: GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
            github_token: Optional GitHub token (uses GITHUB_TOKEN env var if not provided)
        
        Returns:
            PR review result
        """
        repo, pr_number = self._parse_pr_link(pr_link)
        return await self.review_from_repo_and_number(repo, pr_number, github_token)
    
    async def review_from_repo_and_number(
        self, 
        repo: str, 
        pr_number: int, 
        github_token: Optional[str] = None
    ):
        """
        Review a PR from repository name and PR number.
        
        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number
            github_token: Optional GitHub token (uses GITHUB_TOKEN env var if not provided)
        
        Returns:
            PR review result
        """
        server_params = StdioServerParameters(
            command="docker",
            args=[
                "run", "-i", "--rm",
                "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                "-e", "GITHUB_TOOLSETS",
                "ghcr.io/github/github-mcp-server"
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": github_token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"),
                "GITHUB_TOOLSETS": "context,repos,pull_requests,actions"
            }
        )
        
        manager = MCPManager(server_params)
        await manager.start()
        
        try:
            dspy_tools = await build_dspy_tools(manager.session)
            pr_data = load_demo_pr(repo=repo, pr_number=pr_number, github_token=github_token)
            
            if not self.predictor:
                self.tools = dspy_tools
                self.predictor = dspy.ReAct(
                    ReviewPRWithTools, 
                    tools=self.tools,
                    max_iters=self.max_iters
                )
            
            result = await self.predictor.acall(
                pr_metadata=pr_data['pr_metadata'],
                file_list=pr_data['files']
            )
            return result.pr_review
        finally:
            await manager.stop()
    
    @staticmethod
    def _parse_pr_link(pr_link: str) -> tuple[str, int]:
        """
        Parse a GitHub PR link to extract repo and PR number.
        
        Args:
            pr_link: GitHub PR URL
            
        Returns:
            Tuple of (repo, pr_number)
            
        Raises:
            ValueError: If the link format is invalid
        """
        pattern = r'github\.com/([^/]+/[^/]+)/pull/(\d+)'
        match = re.search(pattern, pr_link)
        
        if not match:
            raise ValueError(
                f"Invalid GitHub PR link: {pr_link}. "
                "Expected format: https://github.com/owner/repo/pull/123"
            )
        
        repo = match.group(1)
        pr_number = int(match.group(2))
        return repo, pr_number
