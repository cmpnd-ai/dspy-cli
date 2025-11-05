"""GitHub API tools for code review agent."""

import os
from typing import Optional
import requests
import dspy


def get_file_contents(owner: str, repo: str, path: str, github_token: Optional[str] = None) -> str:
    """
    Get file or directory contents from a GitHub repository.
    
    Args:
        owner: Repository owner (username or organization)
        repo: Repository name
        path: Path to file/directory (directories must end with a slash '/')
    
    Returns:
        File contents as string or directory listing
    """
    if github_token is None:
        github_token = os.getenv("GITHUB_TOKEN")
    
    # Remove trailing slash for API call
    api_path = path.rstrip('/')
    
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{api_path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    # Handle directory listing
    if isinstance(data, list):
        files = [f"{item['name']}/" if item['type'] == 'dir' else item['name'] for item in data]
        return f"Directory listing for {path}:\n" + "\n".join(files)
    
    # Handle file content
    if data.get('type') == 'file':
        import base64
        content = base64.b64decode(data['content']).decode('utf-8')
        return content
    
    return f"Unknown content type: {data.get('type')}"


def build_github_tools(github_token: Optional[str] = None) -> list[dspy.Tool]:
    """
    Build DSPy tools for GitHub API operations.
    
    Args:
        github_token: Optional GitHub token (uses GITHUB_TOKEN env var if not provided)
    
    Returns:
        List of DSPy tools
    """
    def get_file_wrapper(owner: str, repo: str, path: str) -> str:
        return get_file_contents(owner, repo, path, github_token)
    
    return [
        dspy.Tool(
            func=get_file_wrapper,
            name="get_file_contents",
        )
    ]
