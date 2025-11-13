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

Creates a new project with standard directory layout, dependency configuration, and initial DSPy module. Generates `modules/`, `signatures/`, `optimizers/`, `metrics/`, and `utils/` directories along with configuration files (`pyproject.toml`, `dspy.config.yaml`, `Dockerfile`, `.env`).

The initial module is created based on the provided signature (or a default `question -> answer` signature if none is specified).

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

### Directory Purposes

- **modules/** - DSPy program implementations (`dspy.Module` subclasses)
- **signatures/** - Type-safe interfaces defining inputs and outputs
- **optimizers/** - Workflows for improving program performance
- **metrics/** - Functions for measuring program accuracy
- **utils/** - Shared code across modules
- **data/** - Example datasets for training and testing
- **logs/** - Production request/response logs
- **tests/** - Unit and integration tests

## Signature Syntax

Signatures define the program interface using `input -> output` format with optional type annotations.

### Basic Format

```bash
# Single input, single output
-s "question -> answer"

# Multiple inputs
-s "context, question -> answer"

# Multiple outputs
-s "text -> summary, key_points"
```

### Type Annotations

```bash
# String types
-s "text: str -> summary: str"

# Lists
-s "post: str -> tags: list[str]"

# Multiple typed outputs
-s "email: str -> summary: str, action_items: list[str], priority: str"
```

### Examples

```bash
# Email summarizer
-s "email: str -> summary: str, key_points: list[str]"

# Content classifier
-s "email: str, user_context: str -> category: str, confidence: float"

# Code analyzer
-s "code: str, language: str -> explanation: str, complexity: str"

# Content moderator
-s "content: str -> is_safe: bool, issues: list[str]"
```

## Behavior

### Module Generation

The command generates an initial module based on the signature:

**Command:**
```bash
dspy-cli new emoji-picker -s "context: str -> emoji: str, reasoning: str"
```

**Generated signature** (`src/emoji_picker/signatures/emoji_picker_signature.py`):

```python
import dspy

class EmojiPickerSignature(dspy.Signature):
    context: str = dspy.InputField(desc="")
    emoji: str = dspy.OutputField(desc="")
```

**Generated module** (`src/emoji_picker/modules/emoji_picker_predict.py`):

```python
import dspy
from emoji_picker.signatures.emoji_picker_signature import EmojiPickerSignature

class EmojiPickerPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(EmojiPickerSignature)

    def forward(self, context: str) -> dspy.Prediction:
        return self.predictor(context=context)
```

### Program Naming

- Without `-p`: Program name derived from project name (`blog-tools` → `blog_tools`)
- With `-p`: Uses specified program name (`-p tagger` → `TaggerPredict`)

### Dependencies

`pyproject.toml` includes:
- `dspy-ai` - Core DSPy framework
- `python-dotenv` - Environment variable management
- Development dependencies for testing

## Examples

### Basic Project

```bash
dspy-cli new my-feature
cd my-feature
uv sync
source .venv/bin/activate
dspy-cli serve
```

Creates project with default `question -> answer` signature. Serves at `http://localhost:8000/MyFeaturePredict`.

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

After creating a project:

1. **Configure API keys** - Edit `.env`:
   ```bash
   OPENAI_API_KEY=sk-...
   ```

2. **Install dependencies:**
   ```bash
   cd your-project
   uv sync
   source .venv/bin/activate
   ```

3. **Customize signature descriptions** - Edit generated signature file:
   ```python
   class EmojiPickerSignature(dspy.Signature):
       """Select appropriate emoji based on context."""
       
       context: str = dspy.InputField(desc="Text surrounding emoji location")
       emoji: str = dspy.OutputField(desc="Single emoji character")
       reasoning: str = dspy.OutputField(desc="Explanation for emoji choice")
   ```

4. **Start development server:**
   ```bash
   dspy-cli serve --ui
   ```

5. **Test the endpoint:**
   ```bash
   curl -X POST http://localhost:8000/EmojiPickerPredict \
     -H "Content-Type: application/json" \
     -d '{"context": "Great work everyone!"}'
   ```

## Limitations

- Signature parsing supports basic Python types (`str`, `int`, `float`, `bool`, `list`)
- Complex types (nested objects, custom classes) require manual signature editing
- Generated modules use `dspy.Predict` by default (change to `ChainOfThought`, `ReAct`, etc. manually)

## See Also

- [dspy-cli serve](serve.md) - Start development server
- [Deployment Guide](../deployment.md) - Deploy to production
- [Configuration Guide](../configuration.md) - Model configuration
