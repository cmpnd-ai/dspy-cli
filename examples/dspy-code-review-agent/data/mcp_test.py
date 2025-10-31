import os
import dspy
from mcp import StdioServerParameters
from dotenv import load_dotenv
from code_review_agent.utils import load_demo_pr, build_dspy_tools, MCPManager
from code_review_agent.modules.pr_reviewer import PRReviewer

import mlflow
import rich


mlflow.set_tracking_uri("http://127.0.0.1:5001")
mlflow.dspy.autolog()
load_dotenv()


async def review_pr_with_github_mcp(repo: str, pr_number: int):
    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
            "-e", "GITHUB_TOOLSETS",
            "ghcr.io/github/github-mcp-server"
        ],
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"),
            "GITHUB_TOOLSETS": "context,repos,pull_requests,actions"
        }
    )
    
    dspy.configure(lm=dspy.LM("openai/gpt-5-nano", temperature=1.0, max_tokens=16000))
    
    manager = MCPManager(server_params)
    await manager.start()
    
    try:
        rich.print("Session initialized")
        
        dspy_tools = await build_dspy_tools(manager.session)
        rich.print(f"Available tools: {len(dspy_tools)}")
        
        pr_data = load_demo_pr(repo=repo, pr_number=pr_number)
        
        pr_reviewer = PRReviewer(tools=dspy_tools)
        
        result = await pr_reviewer.acall(
            pr_metadata=pr_data['pr_metadata'],
            file_list=pr_data['files']
        )
        rich.print(result.pr_review)
        return result.pr_review
    finally:
        await manager.stop()


# Usage
if __name__ == "__main__":
    import asyncio
    asyncio.run(review_pr_with_github_mcp("stanfordnlp/dspy", 8902))