"""
Evaluation dataset loader for the Discord job posting classifier.
"""

import json
from pathlib import Path

import dspy


def get_eval_dataset() -> list[dspy.Example]:
    """Load evaluation dataset from JSONL file."""
    dataset_path = Path(__file__).parent / "eval_dataset.jsonl"

    examples = []
    with open(dataset_path) as f:
        for line in f:
            data = json.loads(line)
            example = dspy.Example(
                message=data["message"],
                author=data["author"],
                channel_name=data["channel_name"],
                intent=data["intent"],
                action=data["action"],
                category=data["category"],
            ).with_inputs("message", "author", "channel_name")
            examples.append(example)

    return examples


def get_dataset_by_category(category: str) -> list[dspy.Example]:
    """Return examples filtered by category."""
    return [ex for ex in get_eval_dataset() if ex.category == category]


def get_dataset_stats() -> dict:
    """Return statistics about the dataset."""
    from collections import Counter

    dataset = get_eval_dataset()
    categories = Counter(ex.category for ex in dataset)
    intents = Counter(ex.intent for ex in dataset)
    actions = Counter(ex.action for ex in dataset)

    return {
        "total": len(dataset),
        "by_category": dict(categories),
        "by_intent": dict(intents),
        "by_action": dict(actions),
    }


if __name__ == "__main__":
    stats = get_dataset_stats()
    print("Dataset Statistics:")
    print(f"  Total examples: {stats['total']}")
    print(f"  By category: {stats['by_category']}")
    print(f"  By intent: {stats['by_intent']}")
    print(f"  By action: {stats['by_action']}")
