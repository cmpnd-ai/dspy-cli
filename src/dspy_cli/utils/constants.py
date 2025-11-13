"""Shared constants for DSPy CLI."""

# Map of module type aliases to their canonical names, template files, and descriptions
MODULE_TYPES = {
    "Predict": {
        "template": "module_predict.py.template",
        "suffix": "predict",
        "description": "Basic prediction module",
        "display_name": "Predict"
    },
    "ChainOfThought": {
        "template": "module_chain_of_thought.py.template",
        "suffix": "cot",
        "description": "Step-by-step reasoning with chain of thought",
        "display_name": "ChainOfThought (CoT)"
    },
    "CoT": {
        "template": "module_chain_of_thought.py.template",
        "suffix": "cot",
        "description": "Step-by-step reasoning with chain of thought",
        "display_name": "ChainOfThought (CoT)"
    },
    "ProgramOfThought": {
        "template": "module_program_of_thought.py.template",
        "suffix": "pot",
        "description": "Generates and executes code for reasoning",
        "display_name": "ProgramOfThought (PoT)"
    },
    "PoT": {
        "template": "module_program_of_thought.py.template",
        "suffix": "pot",
        "description": "Generates and executes code for reasoning",
        "display_name": "ProgramOfThought (PoT)"
    },
    "ReAct": {
        "template": "module_react.py.template",
        "suffix": "react",
        "description": "Reasoning and acting with tools",
        "display_name": "ReAct"
    },
    "MultiChainComparison": {
        "template": "module_multi_chain_comparison.py.template",
        "suffix": "mcc",
        "description": "Compare multiple reasoning paths",
        "display_name": "MultiChainComparison"
    },
    "Refine": {
        "template": "module_refine.py.template",
        "suffix": "refine",
        "description": "Iterative refinement of outputs",
        "display_name": "Refine"
    },
}

# Get unique module types for interactive selection (exclude aliases)
UNIQUE_MODULE_TYPES = ["Predict", "ChainOfThought", "ProgramOfThought", "ReAct", "MultiChainComparison", "Refine"]
