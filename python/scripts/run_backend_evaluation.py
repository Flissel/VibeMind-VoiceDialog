#!/usr/bin/env python
"""
Selbstständige Backend-Evaluation

Führt alle synthetischen Utterances durch den echten
IntentClassifier und generiert einen umfassenden Report.

Usage:
    python run_backend_evaluation.py
    python run_backend_evaluation.py --category generate
    python run_backend_evaluation.py --difficulty hard
    python run_backend_evaluation.py --limit 20
"""
import asyncio
import os
import sys
import json
import argparse
from datetime import datetime
from collections import Counter
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


async def run_full_evaluation(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: Optional[int] = None,
    verbose: bool = False
):
    """Führe Backend-Evaluation durch."""

    from swarm.evaluation.evaluation_runner import EvaluationRunner
    from swarm.evaluation.conversation_generator import (
        get_all_utterances,
        get_utterances_by_category,
        get_utterances_by_difficulty,
        get_stats
    )
    from swarm.evaluation.intent_taxonomy import IntentCategory

    print("=" * 60)
    print("   VibeMind Backend Self-Evaluation")
    print("=" * 60)

    # 1. Zeige Test-Coverage
    stats = get_stats()
    print(f"\nTest Coverage:")
    print(f"  - Total Utterances: {stats['total']}")
    print(f"  - Intents Covered: {stats['intents_covered']}")
    print(f"  - Easy: {stats['by_difficulty']['easy']}")
    print(f"  - Medium: {stats['by_difficulty']['medium']}")
    print(f"  - Hard: {stats['by_difficulty']['hard']}")

    # 2. Filter utterances basierend auf Argumenten
    utterances = get_all_utterances()
    filter_name = "Full"

    if category:
        try:
            cat = IntentCategory(category.lower())
            utterances = get_utterances_by_category(cat)
            filter_name = f"Category: {category}"
        except ValueError:
            print(f"\nERROR: Unbekannte Kategorie '{category}'")
            print(f"Verfügbar: {[c.value for c in IntentCategory]}")
            return None

    if difficulty:
        utterances = get_utterances_by_difficulty(difficulty)
        filter_name = f"Difficulty: {difficulty}"

    if limit and limit < len(utterances):
        utterances = utterances[:limit]
        filter_name += f" (limit {limit})"

    if not utterances:
        print("\nERROR: Keine Utterances gefunden für diese Filter!")
        return None

    # 3. Erstelle Runner
    print(f"\nInitialisiere IntentClassifier...")
    try:
        runner = EvaluationRunner(use_analysis_team=False)
        print("  [OK] IntentClassifier geladen")
    except Exception as e:
        print(f"  [ERROR] Fehler beim Laden: {e}")
        return None

    # 4. Führe Evaluation durch
    print(f"\n{'='*60}")
    print(f"  Starte Evaluation: {filter_name}")
    print(f"  {len(utterances)} Utterances zu testen")
    print(f"{'='*60}")

    if len(utterances) > 50:
        estimated_time = len(utterances) * 2  # ~2 Sekunden pro Test
        print(f"\n  Geschätzte Dauer: {estimated_time // 60} Minuten")

    print("\n  Progress:")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Callback für Progress
    completed = [0]
    correct_count = [0]

    def progress_callback(result):
        completed[0] += 1
        if result.is_correct:
            correct_count[0] += 1

        # Progress alle 10 Tests oder bei Fehlern
        if completed[0] % 10 == 0 or not result.is_correct:
            accuracy = correct_count[0] / completed[0] * 100
            status = "OK" if result.is_correct else "XX"

            if verbose or not result.is_correct:
                print(f"  [{completed[0]:3}/{len(utterances)}] [{status}] "
                      f"Acc: {accuracy:.1f}% | "
                      f"'{result.utterance.text[:40]}...'")
                if not result.is_correct:
                    print(f"              Expected: {result.utterance.expected_intent}")
                    print(f"              Got:      {result.predicted_intent}")
            else:
                print(f"  [{completed[0]:3}/{len(utterances)}] Running... Accuracy: {accuracy:.1f}%", end="\r")

    # Run evaluation
    report = await runner.run_all(
        utterances,
        name=f"Backend Evaluation {timestamp}",
        progress_callback=progress_callback
    )

    # 5. Zeige Ergebnisse
    print("\n" + "=" * 60)
    print("   ERGEBNISSE")
    print("=" * 60)

    print(f"\n  Overall Accuracy: {report.accuracy * 100:.1f}%")
    print(f"  Correct: {report.correct} / {report.total_tests}")
    print(f"  Incorrect: {report.incorrect}")
    print(f"  Avg Latency: {report.avg_latency_ms:.0f}ms")

    # 6. Per-Category Breakdown
    if report.per_category_accuracy:
        print("\n  --- Per Category ---")
        for cat, cat_stats in sorted(report.per_category_accuracy.items(),
                                key=lambda x: x[1].get('accuracy', 0)):
            acc = cat_stats.get('accuracy', 0) * 100
            status = "[OK]" if acc >= 80 else "[!!]" if acc >= 60 else "[XX]"
            total = cat_stats.get('total', 0)
            correct = cat_stats.get('correct', 0)
            print(f"  {status} {cat:<15}: {acc:>5.1f}% ({correct}/{total})")

    # 7. Per-Difficulty Breakdown
    if report.per_difficulty_accuracy:
        print("\n  --- Per Difficulty ---")
        for diff in ['easy', 'medium', 'hard']:
            if diff in report.per_difficulty_accuracy:
                diff_stats = report.per_difficulty_accuracy[diff]
                acc = diff_stats.get('accuracy', 0) * 100
                total = diff_stats.get('total', 0)
                correct = diff_stats.get('correct', 0)
                print(f"  {diff:<10}: {acc:>5.1f}% ({correct}/{total})")

    # 8. Top Failures
    if report.failures:
        print(f"\n  --- Top {min(10, len(report.failures))} Failures ---")
        for i, fail in enumerate(report.failures[:10], 1):
            input_text = fail.get('input_text', '')[:50]
            print(f"\n  {i}. Input: \"{input_text}...\"")
            print(f"     Expected: {fail.get('expected_intent')}")
            print(f"     Got:      {fail.get('predicted_intent')}")
            if fail.get('confidence'):
                print(f"     Confidence: {fail.get('confidence'):.2f}")

    # 9. Confusion Analysis
    if report.failures:
        print("\n  --- Häufigste Verwechslungen ---")
        confusion = Counter()
        for fail in report.failures:
            pair = (fail.get('expected_intent'), fail.get('predicted_intent'))
            confusion[pair] += 1

        for (expected, got), count in confusion.most_common(5):
            print(f"  {expected} -> {got}: {count}x")

    # 10. Speichere Report
    reports_dir = os.path.join(os.path.dirname(__file__), "evaluation_reports")
    os.makedirs(reports_dir, exist_ok=True)

    md_path = os.path.join(reports_dir, f"report_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())
    print(f"\n  Report gespeichert: {md_path}")

    # 11. Speichere JSON für weitere Analyse
    json_path = os.path.join(reports_dir, f"results_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"  JSON gespeichert: {json_path}")

    print("\n" + "=" * 60)
    print("   Evaluation abgeschlossen!")
    print("=" * 60)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="VibeMind Backend Self-Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python run_backend_evaluation.py                    # Alle Tests
  python run_backend_evaluation.py --category create  # Nur CREATE-Intents
  python run_backend_evaluation.py --difficulty hard  # Nur schwere Tests
  python run_backend_evaluation.py --limit 20         # Nur erste 20 Tests
  python run_backend_evaluation.py -v                 # Verbose Output
        """
    )

    parser.add_argument(
        "--category", "-c",
        help="Filter by category (query, create, modify, delete, navigate, generate, automate, preview, conversation, evaluation)"
    )
    parser.add_argument(
        "--difficulty", "-d",
        choices=["easy", "medium", "hard"],
        help="Filter by difficulty"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all test results, not just failures"
    )

    args = parser.parse_args()

    # Prüfe API Key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("=" * 60)
        print("ERROR: OPENROUTER_API_KEY nicht gesetzt!")
        print("=" * 60)
        print("\nBitte in .env setzen:")
        print("  OPENROUTER_API_KEY=sk-or-xxx")
        print("\nOder als Umgebungsvariable:")
        print("  export OPENROUTER_API_KEY=sk-or-xxx")
        sys.exit(1)

    # Run evaluation
    asyncio.run(run_full_evaluation(
        category=args.category,
        difficulty=args.difficulty,
        limit=args.limit,
        verbose=args.verbose
    ))


if __name__ == "__main__":
    main()
