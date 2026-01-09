"""Utilities for posting reviews to GitHub."""

import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


async def post_github_review(
    token: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    review: Dict[str, Any],
) -> None:
    """Post a review with inline comments to GitHub.

    Maps the PRReview output from the DSPy module to GitHub's Pull Request
    Review API format, including inline comments on specific lines.

    Args:
        token: GitHub installation access token
        repo: Repository full name (owner/repo)
        pr_number: Pull request number
        head_sha: HEAD commit SHA for the review
        review: PRReview output dict from the pipeline

    Raises:
        requests.HTTPError: If GitHub API call fails
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Build inline comments from key_issues_to_review
    comments: List[Dict] = []
    key_issues = review.get("key_issues_to_review", [])

    for issue in key_issues:
        # Handle both dict and Pydantic model
        if hasattr(issue, "model_dump"):
            issue = issue.model_dump()

        file_path = issue.get("relevant_file", "")
        if not file_path:
            continue

        # Build comment body (concise style)
        header = issue.get("issue_header", "Issue")
        content = issue.get("issue_content", "")
        body = f"**{header}**\n\n{content}"

        comment: Dict[str, Any] = {
            "path": file_path,
            "body": body,
        }

        # Add line numbers
        start_line = issue.get("start_line")
        end_line = issue.get("end_line")

        if start_line and end_line:
            if start_line == end_line:
                # Single line comment
                comment["line"] = end_line
            else:
                # Multi-line comment
                comment["start_line"] = start_line
                comment["line"] = end_line
        elif end_line:
            comment["line"] = end_line
        elif start_line:
            comment["line"] = start_line

        # Only add if we have a valid line number
        if "line" in comment:
            comments.append(comment)
        else:
            logger.warning(f"Skipping comment without line number: {file_path}")

    # Build review body summary (concise)
    body_parts = []

    # Effort estimate
    effort = review.get("estimated_effort_to_review_[1-5]") or review.get(
        "estimated_effort_to_review"
    )
    if effort:
        body_parts.append(f"**Effort**: {effort}/5")

    # Test status
    tests = review.get("relevant_tests")
    if tests:
        body_parts.append(f"**Tests**: {tests}")

    # Security concerns
    security = review.get("security_concerns")
    if security and security.lower() not in ("none", "n/a", "no concerns"):
        body_parts.append(f"**Security**: {security}")

    # Score if present
    score = review.get("score")
    if score is not None:
        body_parts.append(f"**Score**: {score}/100")

    # Summary
    if comments:
        body_parts.append(f"\n_{len(comments)} inline comment(s) below._")
    else:
        body_parts.append("\n_No specific issues found._")

    body = " | ".join(body_parts[:3])  # First 3 on one line
    if len(body_parts) > 3:
        body += "\n" + "\n".join(body_parts[3:])

    # Determine review event: REQUEST_CHANGES if critical/security issues
    has_critical = any(
        _is_critical_issue(issue.get("issue_header", "")) for issue in key_issues
    )
    event = "REQUEST_CHANGES" if has_critical else "COMMENT"

    # Build review payload
    review_data: Dict[str, Any] = {
        "commit_id": head_sha,
        "body": body,
        "event": event,
    }

    # Only add comments if we have valid ones
    if comments:
        review_data["comments"] = comments

    logger.info(
        f"Posting {event} review to {repo}#{pr_number} with {len(comments)} comments"
    )

    # Post the review
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"

    response = requests.post(url, headers=headers, json=review_data, timeout=30)

    if response.status_code not in (200, 201):
        logger.error(f"Failed to post review: {response.status_code} {response.text}")
        response.raise_for_status()

    logger.info(f"Successfully posted {event} review with {len(comments)} inline comments")


def _is_critical_issue(issue_header: str) -> bool:
    """Check if an issue header indicates a critical problem.

    Args:
        issue_header: The issue header/title string

    Returns:
        True if the issue should trigger REQUEST_CHANGES
    """
    header_lower = issue_header.lower()
    critical_keywords = [
        "critical",
        "security",
        "vulnerability",
        "injection",
        "xss",
        "sql injection",
        "authentication",
        "authorization",
        "sensitive data",
        "secrets",
        "password",
        "credential",
    ]
    return any(keyword in header_lower for keyword in critical_keywords)
