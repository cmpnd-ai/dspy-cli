"""Utilities for loading and parsing PR data from GitHub."""

import os
import re
from typing import List, Dict, Tuple, Optional
import requests

from code_review_agent.signatures.review_pr import FilePatchInfo, EditType


def fetch_pr_data(repo: str, pr_number: int, github_token: Optional[str] = None) -> Dict:
    """
    Fetch PR metadata and files from GitHub API.
    
    Args:
        repo: Repository in format "owner/repo"
        pr_number: Pull request number
        github_token: Optional GitHub personal access token for higher rate limits
        
    Returns:
        Dict with PR metadata
    """
    base_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    # Fetch PR metadata
    pr_response = requests.get(base_url, headers=headers)
    pr_response.raise_for_status()
    pr_data = pr_response.json()
    
    # Fetch PR files
    files_response = requests.get(f"{base_url}/files", headers=headers)
    files_response.raise_for_status()
    files_data = files_response.json()
    
    # Check if PR is from a fork
    head_repo = pr_data["head"]["repo"]
    base_repo = pr_data["base"]["repo"]
    is_fork = head_repo and (head_repo["full_name"] != base_repo["full_name"])
    
    return {
        "title": pr_data["title"],
        "body": pr_data.get("body", ""),
        "number": pr_data["number"],
        "head_branch": pr_data["head"]["ref"],
        "head_repo": head_repo["full_name"] if head_repo else None,
        "head_sha": pr_data["head"]["sha"],
        "base_branch": pr_data["base"]["ref"],
        "base_repo": base_repo["full_name"],
        "is_fork": is_fork,
        "ref": f"refs/pull/{pr_data['number']}/head",
        "html_url": pr_data["html_url"],
        "files": files_data,
        "created_at": pr_data["created_at"],
        "user": pr_data["user"]["login"]
    }


def parse_patch_to_hunks(patch: str, filename: str) -> Tuple[str, List[Dict]]:
    """
    Convert unified diff patch to line-numbered format with __new hunk__ and __old hunk__ sections.
    
    Args:
        patch: Unified diff patch string
        filename: Name of the file
        
    Returns:
        Tuple of (formatted_patch_string, hunk_metadata_list)
    """
    if not patch:
        return "", []
    
    formatted_output = f"## File: '{filename}'\n\n"
    hunks = []
    
    # Split patch into hunks (sections starting with @@)
    hunk_pattern = r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@([^\n]*)\n(.*?)(?=\n@@|\Z)'
    matches = re.finditer(hunk_pattern, patch, re.DOTALL)
    
    for match in matches:
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1
        hunk_header = match.group(5).strip()
        hunk_body = match.group(6)
        
        lines = hunk_body.split('\n')
        
        # Build __new hunk__ (with line numbers)
        new_hunk_lines = []
        new_line_num = new_start
        
        # Build __old hunk__ (without line numbers)
        old_hunk_lines = []
        
        for line in lines:
            if not line:
                continue
                
            if line.startswith('+'):
                new_hunk_lines.append(f"{new_line_num} {line}")
                new_line_num += 1
            elif line.startswith('-'):
                old_hunk_lines.append(line)
            else:
                new_hunk_lines.append(f"{new_line_num} {line}")
                old_hunk_lines.append(line)
                new_line_num += 1
        
        formatted_output += f"@@ -{old_start},{old_count} +{new_start},{new_count} @@ {hunk_header}\n"
        formatted_output += "__new hunk__\n"
        formatted_output += '\n'.join(new_hunk_lines) + '\n'
        formatted_output += "__old hunk__\n"
        formatted_output += '\n'.join(old_hunk_lines) + '\n\n'
        
        hunks.append({
            "old_start": old_start,
            "new_start": new_start,
            "old_count": old_count,
            "new_count": new_count,
            "header": hunk_header
        })
    
    return formatted_output, hunks


def determine_edit_type(status: str) -> EditType:
    """Map GitHub file status to edit type."""
    status_map = {
        "added": EditType.ADDED,
        "removed": EditType.DELETED,
        "modified": EditType.MODIFIED,
        "renamed": EditType.RENAMED
    }
    return status_map.get(status, EditType.UNKNOWN)


def count_lines(patch: str) -> Tuple[int, int]:
    """Count added and removed lines in patch."""
    if not patch:
        return 0, 0
    
    lines = patch.split('\n')
    plus_lines = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    minus_lines = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    return plus_lines, minus_lines


def format_pr_for_review(pr_data: Dict) -> Dict:
    """
    Format PR data into the structure expected by DSPy code review agent.
    
    Args:
        pr_data: PR data from fetch_pr_data
        
    Returns:
        Dict with pr_metadata and List[FilePatchInfo]
    """
    formatted_files: List[FilePatchInfo] = []
    full_diff = ""
    
    for file in pr_data["files"]:
        filename = file["filename"]
        patch = file.get("patch", "")
        
        formatted_patch, hunks = parse_patch_to_hunks(patch, filename)
        full_diff += formatted_patch
        
        plus_lines, minus_lines = count_lines(patch)
        
        # Determine language from extension
        ext = filename.split('.')[-1] if '.' in filename else ""
        language_map = {
            "py": "Python",
            "js": "JavaScript",
            "ts": "TypeScript",
            "java": "Java",
            "cpp": "C++",
            "c": "C",
            "go": "Go",
            "rs": "Rust",
            "rb": "Ruby",
            "php": "PHP",
            "md": "Markdown"
        }
        language = language_map.get(ext, ext.upper() if ext else None)
        
        file_patch = FilePatchInfo(
            filename=filename,
            patch=formatted_patch,
            base_file="",
            head_file="",
            edit_type=determine_edit_type(file["status"]),
            num_plus_lines=plus_lines,
            num_minus_lines=minus_lines,
            language=language,
            tokens=-1,
            old_filename=file.get("previous_filename") if file["status"] == "renamed" else None
        )
        
        formatted_files.append(file_patch)
    
    return {
        "pr_metadata": {
            "title": pr_data["title"],
            "description": pr_data["body"],
            "branch": pr_data["head_branch"],
            "head_repo": pr_data["head_repo"],
            "head_sha": pr_data["head_sha"],
            "base_branch": pr_data["base_branch"],
            "base_repo": pr_data["base_repo"],
            "is_fork": pr_data["is_fork"],
            "ref": pr_data["ref"],
            "number": pr_data["number"],
            "url": pr_data["html_url"],
            "created_at": pr_data["created_at"],
            "author": pr_data["user"]
        },
        "files": formatted_files,
        "full_diff": full_diff,
        "num_files": len(formatted_files),
        "total_additions": sum(f.num_plus_lines for f in formatted_files),
        "total_deletions": sum(f.num_minus_lines for f in formatted_files)
    }


def download_and_format_pr(
    repo: str = "stanfordnlp/dspy",
    pr_number: int = 8902,
    github_token: Optional[str] = None
) -> Dict:
    """
    Load a demo PR for testing.
    
    Args:
        repo: GitHub repository (default: stanfordnlp/dspy)
        pr_number: PR number (default: 8902)
        github_token: Optional GitHub token (will use GITHUB_TOKEN env var if not provided)
        
    Returns:
        Formatted PR data ready for review
    """
    if github_token is None:
        github_token = os.getenv("GITHUB_TOKEN")
    
    print(f"Fetching PR #{pr_number} from {repo}...")
    pr_data = fetch_pr_data(repo, pr_number, github_token)
    
    print(f"Processing {len(pr_data['files'])} files...")
    formatted = format_pr_for_review(pr_data)
    
    print(f"✓ Loaded PR: {formatted['pr_metadata']['title']}")
    print(f"  Files changed: {formatted['num_files']}")
    print(f"  +{formatted['total_additions']} -{formatted['total_deletions']}")
    
    return formatted
