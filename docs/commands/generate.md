# dspy-cli generate

Generate components in an existing project — adds programs, signatures, and modules without manual file creation.

Alias: `g`

## Usage

```bash
dspy-cli g scaffold PROGRAM_NAME [OPTIONS]
```

## What Happens

```bash
$ dspy-cli g scaffold analyzer -s "text -> summary"
Generating scaffold for program: analyzer

  Signature: text -> summary
  Module type: Predict
  Package: qa_bot

  Created: signatures/analyzer.py
  Created: modules/analyzer_predict.py
✓ Scaffold created successfully!

Files created:
  • signatures/analyzer.py
  • modules/analyzer_predict.py
```

## Options

- `--module`, `-m` - Module type [default: Predict]
- `--signature`, `-s` - Inline signature (e.g., "question -> answer")

## Module Types

`Predict`, `ChainOfThought` (`CoT`), `ProgramOfThought` (`PoT`), `ReAct`, `MultiChainComparison`, `Refine`

## Examples

```bash
# Simple: Basic program with Predict module
dspy-cli g scaffold analyzer -s "text -> summary"
# Creates: analyzer_predict.py

# Chain-of-Thought: Add reasoning capability
dspy-cli g scaffold reasoner -m CoT -s "context: list[str], question -> reasoning, answer"
# Output shows: Module type: CoT
# Creates: reasoner_cot.py

# Multi-input: Complex reasoning task
dspy-cli g scaffold search -m CoT -s "query, context: list[str] -> answer"

# ReAct: Tool-using agent pattern
dspy-cli g scaffold agent -m ReAct -s "task, tools: list[str] -> action, result"
```

## Signature Format

```bash
# Single field I/O
"question -> answer"

# Multiple inputs
"context, question -> answer"

# Typed outputs for validation
"text -> sentiment, score: float"

# Complex structures
"query, docs: list[str] -> answer, citations: list[int]"
```

## Output Structure

Creates two files:

- `signatures/{name}.py` - Input/output schema
- `modules/{name}_{type}.py` - Module implementation (e.g., analyzer_predict.py, reasoner_cot.py)

## Endpoint Naming

Endpoints are derived from the generated module class name. For example:

- **Predict**: `analyzer` → `AnalyzerPredict` → `POST /AnalyzerPredict`
- **CoT**: `reasoner -m CoT` → `ReasonerCoT` → `POST /ReasonerCoT`
- **ReAct**: `agent -m ReAct` → `AgentReAct` → `POST /AgentReAct`

Program names with dashes are converted to underscores in the Python code.
