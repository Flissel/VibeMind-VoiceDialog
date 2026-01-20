"""
Evaluation CLI - Command-line interface for intent evaluation.

Usage:
    python -m swarm.evaluation.cli run-all
    python -m swarm.evaluation.cli run --category GENERATE
    python -m swarm.evaluation.cli run --intent idea.expand
    python -m swarm.evaluation.cli stats
    python -m swarm.evaluation.cli export --output training.jsonl
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from .intent_taxonomy import IntentCategory
from .conversation_generator import (
    get_all_utterances,
    get_utterances_by_intent,
    get_utterances_by_category,
    get_utterances_by_difficulty,
    get_stats as get_utterance_stats,
    export_to_json,
)
from .evaluation_runner import EvaluationRunner, run_evaluation
from .dashboard import print_full_dashboard, print_live_stats


def cmd_run_all(args):
    """Run all evaluation tests."""
    print("Running full evaluation...")
    print(f"Total utterances: {len(get_all_utterances())}")

    async def run():
        report = await run_evaluation(
            name="Full Evaluation",
            use_analysis_team=args.use_team
        )
        print("\n" + report.to_markdown())

        # Save report
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                if args.output.endswith(".json"):
                    json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
                else:
                    f.write(report.to_markdown())
            print(f"\nReport saved to: {args.output}")

    asyncio.run(run())


def cmd_run(args):
    """Run evaluation with filters."""
    utterances = None
    name = "Filtered Evaluation"

    if args.category:
        try:
            category = IntentCategory(args.category.lower())
            utterances = get_utterances_by_category(category)
            name = f"Category: {category.value}"
        except ValueError:
            print(f"Invalid category: {args.category}")
            print(f"Valid categories: {[c.value for c in IntentCategory]}")
            return

    elif args.intent:
        utterances = get_utterances_by_intent(args.intent)
        name = f"Intent: {args.intent}"
        if not utterances:
            print(f"No utterances found for intent: {args.intent}")
            return

    elif args.difficulty:
        utterances = get_utterances_by_difficulty(args.difficulty)
        name = f"Difficulty: {args.difficulty}"

    if utterances:
        print(f"Running evaluation: {name}")
        print(f"Total utterances: {len(utterances)}")
    else:
        print("Running full evaluation (no filters specified)")
        utterances = get_all_utterances()

    async def run():
        runner = EvaluationRunner(use_analysis_team=args.use_team)
        report = await runner.run_all(utterances, name)
        print("\n" + report.to_markdown())

    asyncio.run(run())


def cmd_stats(args):
    """Show evaluation statistics."""
    if args.live:
        print_live_stats()
    else:
        print_full_dashboard()


def cmd_export(args):
    """Export utterances or results."""
    output = args.output or "utterances.json"

    if args.format == "json":
        export_to_json(output)
        print(f"Exported utterances to: {output}")

    elif args.format == "jsonl":
        utterances = get_all_utterances()
        with open(output, "w", encoding="utf-8") as f:
            for utt in utterances:
                line = json.dumps(utt.to_dict(), ensure_ascii=False)
                f.write(line + "\n")
        print(f"Exported {len(utterances)} utterances to: {output}")

    elif args.format == "corrections":
        try:
            from ...data.conversion_ai_repository import get_conversion_ai_repo
            repo = get_conversion_ai_repo()
            corrections = repo.get_corrections(limit=args.limit or 1000, unused_only=False)

            with open(output, "w", encoding="utf-8") as f:
                json.dump(corrections, f, ensure_ascii=False, indent=2)

            print(f"Exported {len(corrections)} corrections to: {output}")
        except Exception as e:
            print(f"Failed to export corrections: {e}")


def cmd_generate(args):
    """Generate more utterance variants using LLM."""
    print("LLM-based variant generation not yet implemented.")
    print("Use the synthetic utterances from conversation_generator.py")


def main():
    parser = argparse.ArgumentParser(
        description="VibeMind Intent Evaluation CLI",
        prog="python -m swarm.evaluation.cli"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run-all command
    run_all_parser = subparsers.add_parser("run-all", help="Run full evaluation")
    run_all_parser.add_argument("--output", "-o", help="Save report to file")
    run_all_parser.add_argument("--use-team", action="store_true",
                                help="Use multi-agent analysis team")

    # run command
    run_parser = subparsers.add_parser("run", help="Run filtered evaluation")
    run_parser.add_argument("--category", "-c", help="Filter by category")
    run_parser.add_argument("--intent", "-i", help="Filter by intent type")
    run_parser.add_argument("--difficulty", "-d", choices=["easy", "medium", "hard"],
                           help="Filter by difficulty")
    run_parser.add_argument("--use-team", action="store_true",
                           help="Use multi-agent analysis team")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument("--live", action="store_true",
                             help="Show live accuracy stats only")

    # export command
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--format", "-f", default="json",
                              choices=["json", "jsonl", "corrections"],
                              help="Export format")
    export_parser.add_argument("--output", "-o", help="Output file path")
    export_parser.add_argument("--limit", "-l", type=int, help="Limit records")

    # generate command
    generate_parser = subparsers.add_parser("generate",
                                           help="Generate utterance variants")
    generate_parser.add_argument("--intent", "-i", help="Intent to generate for")
    generate_parser.add_argument("--count", "-n", type=int, default=10,
                                help="Number of variants")

    args = parser.parse_args()

    if args.command == "run-all":
        cmd_run_all(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "generate":
        cmd_generate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
