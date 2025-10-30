"""Signature definitions for dspy_code_review_agent."""

import dspy
from typing import Dict, List, Union, Optional

from enum import Enum

from pydantic import BaseModel, Field

class EditType(str, Enum):
    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"
    RENAMED = "renamed"
    UNKNOWN = "unknown"

class FilePatchInfo(BaseModel):
    base_file: str
    head_file: str
    patch: str
    filename: str
    tokens: int = -1
    edit_type: EditType = EditType.UNKNOWN
    old_filename: str | None = None
    num_plus_lines: int = -1
    num_minus_lines: int = -1
    language: str | None = None
    ai_file_summary: str | None = None

class KeyIssue(BaseModel):
    """Individual issue found during review"""
    relevant_file: str = Field(description="File path where the issue was found")
    issue_header: str = Field(description="Short title of the issue")
    issue_content: str = Field(description="Detailed description of the issue")
    start_line: int = Field(description="Starting line number")
    end_line: int = Field(description="Ending line number")


class SubPR(BaseModel):
    """Suggested sub-PR if the PR can be split"""
    relevant_files: List[str] = Field(description="Files that belong to this sub-PR")
    title: str = Field(description="Suggested title for the sub-PR")


class TodoSection(BaseModel):
    """TODO/FIXME found in the PR"""
    relevant_file: str
    todo_content: str
    start_line: int
    end_line: int


class PRReview(BaseModel):
    """Complete PR review output"""
    
    estimated_effort_to_review: int = Field(
        ge=1, 
        le=5,
        description="Effort required to review (1=minimal, 5=extensive)",
        alias="estimated_effort_to_review_[1-5]"
    )
    
    relevant_tests: str = Field(
        description="Whether tests are included (Yes/No/Partial)"
    )
    
    key_issues_to_review: List[KeyIssue] = Field(
        default_factory=list,
        description="List of important issues found"
    )
    
    security_concerns: str = Field(
        description="Security analysis summary"
    )
    
    # Optional fields
    score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Overall PR quality score"
    )
    
    can_be_split: Optional[List[SubPR]] = Field(
        None,
        description="Suggestions for splitting the PR"
    )
    
    todo_sections: Optional[List[TodoSection]] = Field(
        None,
        description="TODO/FIXME comments found"
    )
    
    estimated_contribution_time_cost: Optional[str] = Field(
        None,
        description="Estimated time to implement changes"
    )
    
    class Config:
        populate_by_name = True

class KeyIssuesComponentLink(BaseModel):
    relevant_file: str
    issue_header: str  # e.g., 'Possible Bug'
    issue_content: str  # Short summary, no line numbers
    start_line: int
    end_line: int

class PRMetadata(BaseModel):
    title: str
    branch: str
    description: str
    commit_messages: List[str]
    user_questions: str

    # How do I include comments


class ReviewPR(dspy.Signature):
    """
    Provide constructive and concise feedback for a Git Pull Request (PR).
    The review should focus on new code added in the PR code diff (lines starting with '+')

    Notes:
    - Code is in '__new hunk__' (updated) and '__old hunk__' (removed) sections
    - Line numbers only appear in '__new hunk__' for reference
    - Lines prefixed with '+' are new, '-' are removed, ' ' are unchanged
    - When quoting variables/names/paths, use backticks (`) not quotes (')
    - You only see changed code (diff hunks), not the entire codebase
    - Don't question code elements that may be defined elsewhere
    - If code ends at an opening brace/statement (if, for, try), don't treat as incomplete
    """
    pr_metadata: PRMetadata = dspy.InputField(description="PR metadata")
    file_list: List[FilePatchInfo] = dspy.InputField(description="List of files and their patches")
    pr_review: PRReview = dspy.OutputField(description="PR review output")

