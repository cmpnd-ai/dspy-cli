"""
Evaluation script for the Discord job posting classifier.

Usage:
    python -m tests.test_eval
    # or
    cd examples/discord-mod && python tests/test_eval.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dspy
from dspy.evaluate import Evaluate

from discord_mod.modules.classify_job_posting import ClassifyJobPosting
from data.eval_dataset import get_eval_dataset, get_dataset_stats, get_dataset_by_category


def intent_metric(example, pred, _trace=None) -> float:
    """Check if the predicted intent matches the expected intent."""
    return 1.0 if pred.intent == example.intent else 0.0


def action_metric(example, pred, _trace=None) -> float:
    """Check if the predicted action matches the expected action."""
    return 1.0 if pred.action == example.action else 0.0


def combined_metric(example, pred, _trace=None) -> float:
    """
    Combined metric: both intent AND action must be correct.
    Returns 1.0 only if both match, 0.0 otherwise.
    """
    intent_correct = pred.intent == example.intent
    action_correct = pred.action == example.action
    return 1.0 if (intent_correct and action_correct) else 0.0


def run_evaluation(model: str = "openai/gpt-5-nano", num_threads: int = 4):
    """Run the full evaluation suite."""
    # Configure DSPy
    lm = dspy.LM(model)
    dspy.configure(lm=lm)

    # Load dataset
    devset = get_eval_dataset()
    stats = get_dataset_stats()

    print("=" * 60)
    print("Discord Moderation Bot Evaluation")
    print("=" * 60)
    print(f"\nDataset: {stats['total']} examples")
    print(f"  Categories: {stats['by_category']}")
    print(f"  Intents: {stats['by_intent']}")
    print(f"  Actions: {stats['by_action']}")
    print(f"\nModel: {model}")
    print("=" * 60)

    # Initialize the module
    classifier = ClassifyJobPosting()

    # Run evaluations with different metrics
    print("\n[1/3] Evaluating Intent Accuracy...")
    intent_evaluator = Evaluate(
        devset=devset,
        metric=intent_metric,
        num_threads=num_threads,
        display_progress=True,
        display_table=5,
    )
    intent_result = intent_evaluator(classifier)
    print(f"Intent Accuracy: {intent_result.score:.1f}%")

    print("\n[2/3] Evaluating Action Accuracy...")
    action_evaluator = Evaluate(
        devset=devset,
        metric=action_metric,
        num_threads=num_threads,
        display_progress=True,
        display_table=5,
    )
    action_result = action_evaluator(classifier)
    print(f"Action Accuracy: {action_result.score:.1f}%")

    print("\n[3/3] Evaluating Combined (Intent + Action)...")
    combined_evaluator = Evaluate(
        devset=devset,
        metric=combined_metric,
        num_threads=num_threads,
        display_progress=True,
        display_table=5,
    )
    combined_result = combined_evaluator(classifier)
    print(f"Combined Accuracy: {combined_result.score:.1f}%")

    # Per-category breakdown
    print("\n" + "=" * 60)
    print("Per-Category Results (Action Accuracy)")
    print("=" * 60)

    categories = ["nuanced", "sanity_general", "sanity_job", "spam", "jobs_channel"]
    for category in categories:
        cat_devset = get_dataset_by_category(category)
        if not cat_devset:
            continue

        cat_evaluator = Evaluate(
            devset=cat_devset,
            metric=action_metric,
            num_threads=num_threads,
            display_progress=False,
        )
        cat_result = cat_evaluator(classifier)
        print(f"  {category}: {cat_result.score:.1f}% ({len(cat_devset)} examples)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Intent Accuracy:     {intent_result.score:.1f}%")
    print(f"  Action Accuracy:     {action_result.score:.1f}%")
    print(f"  Combined Accuracy:   {combined_result.score:.1f}%")
    print("=" * 60)

    return {
        "intent_accuracy": intent_result.score,
        "action_accuracy": action_result.score,
        "combined_accuracy": combined_result.score,
    }


def analyze_errors(model: str = "openai/gpt-5-nano"):
    """Analyze specific error cases for debugging."""
    lm = dspy.LM(model)
    dspy.configure(lm=lm)

    devset = get_eval_dataset()
    classifier = ClassifyJobPosting()

    print("Analyzing predictions...\n")

    errors = []
    for example in devset:
        pred = classifier(
            message=example.message,
            author=example.author,
            channel_name=example.channel_name,
        )

        if pred.intent != example.intent or pred.action != example.action:
            errors.append({
                "example": example,
                "prediction": pred,
            })

    print(f"Found {len(errors)} errors out of {len(devset)} examples\n")

    for i, error in enumerate(errors, 1):
        ex = error["example"]
        pred = error["prediction"]

        print(f"Error {i}:")
        print(f"  Message: {ex.message[:100]}...")
        print(f"  Author: {ex.author}, Channel: {ex.channel_name}")
        print(f"  Expected: intent={ex.intent}, action={ex.action}")
        print(f"  Got:      intent={pred.intent}, action={pred.action}")
        print(f"  Reason:   {pred.reason}")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate Discord moderation classifier")
    parser.add_argument("--model", default="openai/gpt-5-nano", help="Model to use")
    parser.add_argument("--threads", type=int, default=4, help="Number of threads")
    parser.add_argument("--analyze", action="store_true", help="Analyze errors in detail")

    args = parser.parse_args()

    if args.analyze:
        analyze_errors(model=args.model)
    else:
        run_evaluation(model=args.model, num_threads=args.threads)
