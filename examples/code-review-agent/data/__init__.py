"""Data utilities - re-exports from utils for backward compatibility."""

from code_review_agent.utils import (
    fetch_pr_data,
    format_pr_for_review,
    load_demo_pr,
    convert_mcp_tool,
    build_dspy_tools,
    MCPManager,
)

__all__ = [
    "fetch_pr_data",
    "format_pr_for_review",
    "load_demo_pr",
    "convert_mcp_tool",
    "build_dspy_tools",
    "MCPManager",
]

