# dspy-cli new

Create a new DSPy project with standard directory structure.

## Synopsis

```bash
dspy-cli new <PROJECT_NAME> [OPTIONS]
```

## Usage

```bash
# Create project with default signature
dspy-cli new my-feature

# Create project with custom signature
dspy-cli new email-summarizer -s "email: str -> summary: str, key_points: list[str]"

# Specify program name
dspy-cli new notion-tools -p emoji_picker -s "context: str -> emoji: str"
```

## Description

Creates project with standard directory layout, dependency configuration, and initial DSPy module. Default signature is `question -> answer` if none specified.

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--program-name` | `-p` | Derived from project name | Name of initial program module |
| `--signature` | `-s` | `question -> answer` | Input/output signature defining the program interface |

## Arguments

- `PROJECT_NAME` - Name of the project directory to create (required)

## Generated Structure

```
my-feature/
├── src/
│   └── my_feature/
│       ├── modules/          # DSPy program implementations
│       ├── signatures/       # Input/output type definitions
│       ├── optimizers/       # Optimization workflows
│       ├── metrics/          # Evaluation functions
│       └── utils/           # Shared utilities
├── data/                    # Training examples and datasets
├── logs/                    # Request/response logs
├── tests/                   # Test files
├── pyproject.toml          # Python dependencies
├── dspy.config.yaml        # Model configuration
├── Dockerfile              # Container definition
└── .env                    # Environment variables
```

## Signature Syntax

Format: `input -> output` with optional type annotations. See [dspy-cli generate](generate.md) for complete syntax reference.

## Examples

### Email Summarizer

```bash
dspy-cli new email-summarizer -s "email: str -> summary: str, key_points: list[str]"
```

Generates:
- Signature: `EmailSummarizerSignature` with `email` input, `summary` and `key_points` outputs
- Module: `EmailSummarizerPredict`
- Endpoint: `/EmailSummarizerPredict`

### Multi-Input Analyzer

```bash
dspy-cli new code-reviewer -s "code: str, language: str -> issues: list[str], suggestions: str"
```

Creates module accepting two inputs (`code`, `language`) and returning two outputs (`issues`, `suggestions`).

### Custom Program Name

```bash
dspy-cli new blog-tools -p tagger -s "blog_post: str -> tags: list[str]"
```

Project named `blog-tools`, initial program named `TaggerPredict`. Additional programs can be added to `modules/` later.

## Next Steps

1. Configure `.env` with API key
2. Install dependencies: `uv sync`
3. Start server: `dspy-cli serve --ui`

## See Also

- [dspy-cli generate](generate.md) - Generate new modules in existing projects
- [dspy-cli serve](serve.md) - Start development server
- [Deployment Guide](../deployment.md) - Deploy to production
