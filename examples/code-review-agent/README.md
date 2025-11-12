# Code Review Agent

PR review agent demonstrating ReAct tool use with GitHub API integration.

## Overview

This example uses `dspy.ReAct` with GitHub API tools to:

1. Accept repository name and PR number as input
2. Fetch PR metadata and file diffs using GitHub tools
3. Analyze code changes for issues, security concerns, and test coverage
4. Return structured review with effort estimation and key issues

**Program:** `PRReviewer` (ReAct)  
**Signature:** `ReviewPR` - Input: pr_metadata, file_list → Output: PRReview  
**Tools:** GitHub API (`get_file_contents` and PR data fetching)

## Prerequisites

- Python 3.11+
- OpenAI API key
- GitHub personal access token (optional, for private repos)
- `dspy-cli` installed

## Run Locally

### 1. Install Dependencies

```bash
cd examples/code-review-agent
uv sync
```

### 2. Configure Environment

```bash
# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env
echo "GITHUB_TOKEN=your-token-here" >> .env  # Optional
```

### 3. Start Server

```bash
dspy-cli serve --ui
```

Server starts at `http://localhost:8000`

### 4. Test Endpoint

```bash
curl -X POST http://localhost:8000/PRReviewer \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "stanfordnlp/dspy",
    "pr_number": 1234
  }'
```

Expected output:
```json
{
  "estimated_effort_to_review": 3,
  "relevant_tests": "Yes",
  "key_issues_to_review": [
    {
      "relevant_file": "src/module.py",
      "issue_header": "Potential type error",
      "issue_content": "Function expects string but receives int",
      "start_line": 45,
      "end_line": 47
    }
  ],
  "security_concerns": "No security issues found",
  "score": 85
}
```

## Deploy

```bash
flyctl launch
flyctl secrets set OPENAI_API_KEY=your-key-here
flyctl secrets set GITHUB_TOKEN=your-token-here  # Optional
flyctl deploy
```

Deployment URL: `https://your-app.fly.dev`

See [Deployment Guide](../../docs/deployment.md) for other platforms.

## Integrate

### Python

```python
import requests

response = requests.post(
    'https://your-app.fly.dev/PRReviewer',
    json={
        'repo': 'owner/repo',
        'pr_number': 123
    }
)

review = response.json()
print(f"Effort: {review['estimated_effort_to_review']}/5")
print(f"Tests: {review['relevant_tests']}")
print(f"Issues found: {len(review['key_issues_to_review'])}")
```

### JavaScript

```javascript
const response = await fetch('https://your-app.fly.dev/PRReviewer', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    repo: 'owner/repo',
    pr_number: 123
  })
});

const review = await response.json();
console.log(`Security: ${review.security_concerns}`);
```

### curl

```bash
curl -X POST https://your-app.fly.dev/PRReviewer \
  -H "Content-Type: application/json" \
  -d '{"repo": "owner/repo", "pr_number": 123}'
```

## Architecture

**Module:** `PRReviewer`
- Uses `dspy.ReAct` with GitHub API tools
- Fetches PR data with `download_and_format_pr()`
- Tool: `get_file_contents` - Retrieve full file contents from GitHub
- Returns structured `PRReview` object

**Signature:** `ReviewPR`
- Input fields: `pr_metadata` (dict), `file_list` (list)
- Output field: `pr_review` (PRReview pydantic model)

**Output Structure:** `PRReview`
- `estimated_effort_to_review` (1-5)
- `relevant_tests` (Yes/No/Partial)
- `key_issues_to_review` (list of issues with file, line numbers, description)
- `security_concerns` (string summary)
- Optional: `score` (0-100), `todo_sections`, `estimated_contribution_time_cost`

## Project Structure

```
code-review-agent/
├── src/code_review_agent/
│   ├── modules/
│   │   └── pr_reviewer.py       # PRReviewer ReAct module
│   ├── signatures/
│   │   └── review_pr.py         # ReviewPR signature + PRReview model
│   └── utils/
│       ├── pr_loader.py         # Fetch and format PR data
│       └── github_tools.py      # GitHub API tools
├── openapi.json                 # API specification
└── dspy.config.yaml             # Model configuration
```
