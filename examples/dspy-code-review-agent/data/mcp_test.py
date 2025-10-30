import os
import dspy
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from dotenv import load_dotenv
from data.load import load_demo_pr
from dspy_code_review_agent.signatures.review_pr import PRReview
from data.mcp_converter import convert_mcp_tool
import mlflow
import rich


mlflow.set_tracking_uri("http://127.0.0.1:5001")
mlflow.dspy.autolog()
load_dotenv()

class ReviewPRWithTools(dspy.Signature):
    """You are a code review agent. Use available GitHub tools to analyze the PR deeply.
    You can read related files, search for similar patterns, check commit history, etc."""
    
    pr_metadata: dict = dspy.InputField(desc="PR title, description, branch info")
    file_list: list = dspy.InputField(desc="List of files changed in the PR")
    pr_review: PRReview = dspy.OutputField(description="PR review output")


async def review_pr_with_github_mcp(repo: str, pr_number: int):
    # Configure GitHub MCP server
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
            "GITHUB_TOOLSETS": "context,repos,pull_requests,code_security,actions"
        }
    )
    
    dspy.configure(lm=dspy.LM("openai/gpt-5-nano", temperature=1.0, max_tokens=16000))
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available GitHub tools
            tools = await session.list_tools()
            
            # Convert MCP tools to DSPy tools using our custom converter
            dspy_tools = [
                convert_mcp_tool(session, tool) 
                for tool in tools.tools
            ]
            
            # Test the get_file_contents tool with our custom converter
            get_file_contents = [tool for tool in dspy_tools if tool.name == "get_file_contents"][0]
            args = {
                "owner": "stanfordnlp",
                "repo": "dspy",
                "path": "dspy/adapters/chat_adapter.py",
                "ref": "refs/pull/8902/head"
            }
            
            # Call the tool using our custom converter
            file_contents = await get_file_contents.acall(**args)
            
            rich.print(f"\n[bold green]✓ Successfully got file contents![/bold green]")
            rich.print(f"Type: {type(file_contents)}")
            
            if isinstance(file_contents, dict):
                rich.print("\n[cyan]Bundle structure:[/cyan]")
                rich.print(f"  ok: {file_contents.get('ok')}")
                rich.print(f"  texts: {len(file_contents.get('texts', []))} items")
                rich.print(f"  images: {len(file_contents.get('images', []))} items")
                rich.print(f"  audio: {len(file_contents.get('audio', []))} items")
                rich.print(f"  blobs: {len(file_contents.get('blobs', []))} items")
                
                rich.print("\n[yellow]Observation (what the LM sees):[/yellow]")
                rich.print(file_contents.get('observation', ''))
                
                if file_contents.get('texts'):
                    rich.print("\n[green]Full text content available:[/green]")
                    for i, text in enumerate(file_contents['texts']):
                        if text.get('full_text'):
                            rich.print(f"  File {i}: {text.get('name')} ({len(text['full_text'])} chars)")
            else:
                rich.print(f"Direct return: {str(file_contents)[:500]}")
            
            exit()
            
            # Load PR data (your existing code)
            pr_data = load_demo_pr(repo=repo, pr_number=pr_number)
            
            # Create ReAct agent with GitHub MCP tools
            pr_reviewer = dspy.ReAct(
                ReviewPRWithTools, 
                tools=dspy_tools,
                max_iters=5
            )
            
            # Run review
            result = await pr_reviewer.acall(
                pr_metadata=pr_data['pr_metadata'],
                file_list=pr_data['files']
            )
            rich.print(result.pr_review)
            return result.pr_review


# Usage
if __name__ == "__main__":
    import asyncio
    asyncio.run(review_pr_with_github_mcp("stanfordnlp/dspy", 8902))