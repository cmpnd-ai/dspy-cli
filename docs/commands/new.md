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

# Specify module type and model
dspy-cli new chat-bot -m CoT --model anthropic/claude-3-sonnet
```

## Description

Creates project with standard directory layout, dependency configuration, and initial DSPy module. Default signature is `question -> answer` if none specified.

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--program-name` | `-p` | Derived from project name | Name of initial program module |
| `--signature` | `-s` | `question -> answer` | Input/output signature defining the program interface |
| `--module-type` | `-m` | `Predict` | DSPy module type (Predict, CoT, ReAct, etc.) |
| `--model` | - | `openai/gpt-5-mini` | LLM model string (e.g. `openai/gpt-4o`) |
| `--api-key` | - | - | API key for the LLM provider |

## Arguments

- `PROJECT_NAME` - Name of the project directory to create (required)

## Interactive Mode

Running `dspy-cli new` without arguments will start an interactive mode where you can specify the project name, program name, signature, module type, and model.

Expected Outputs:

```
What is your project name? [my-project]: email-subject
Would you like to specify your first program? [Y/n]: Y
What is the name of your first DSPy program? [my_program]: email_subject
Choose a module type:
  1. Predict - Basic prediction module (default)
  2. ChainOfThought (CoT) - Step-by-step reasoning with chain of thought
  3. ProgramOfThought (PoT) - Generates and executes code for reasoning
  4. ReAct - Reasoning and acting with tools
  5. MultiChainComparison - Compare multiple reasoning paths
  6. Refine - Iterative refinement of outputs
Enter number or name [1]: 1
Enter your signature or type '?' for guided input:
  Examples: 'question -> answer', 'post:str -> tags:list[str], category:str'
Signature [question:str -> answer:str]: body, sender, context -> subject, tone, priority
Enter your model (LiteLLM format):
  Examples: 'anthropic/claude-sonnet-4-5', 'openai/gpt-4o', 'ollama/llama2'
Model [openai/gpt-5-mini]: openai/gpt-5-mini
Enter your OpenAI API key:
  (This will be stored in .env as OPENAI_API_KEY)
  Press Enter to skip and set it manually later
OPENAI_API_KEY: your_key_here
```

## Generated Structure

```bash
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

```bash
dspy-cli new blog-tools -p tagger -s "blog_post: str -> tags: list[str]"
```

Project named `blog-tools`, initial program named `TaggerPredict`. Additional programs can be added to `modules/` later.

## Next Steps

1. Configure `.env` with API key
2. Install dependencies: `uv sync`
3. Start server: `dspy-cli serve`

## See Also

- [dspy-cli generate](generate.md) - Generate new modules in existing projects
- [dspy-cli serve](serve.md) - Start development server
- [Deployment Guide](../deployment.md) - Deploy to production
