"""
Evaluation Dashboard - Display live statistics.

Provides terminal-based visualization of evaluation metrics.
"""

import sys
from typing import Optional

from .intent_taxonomy import IntentCategory, get_category_stats
from .conversation_generator import get_stats as get_utterance_stats


def print_live_stats(session_id: Optional[str] = None) -> None:
    """
    Display live evaluation statistics in the terminal.

    Args:
        session_id: Optional session to filter by
    """
    try:
        from ...data.conversion_ai_repository import get_conversion_ai_repo
        repo = get_conversion_ai_repo()
        stats = repo.get_analysis_stats(session_id=session_id)
    except Exception:
        stats = {"total": 0, "correct": 0, "incorrect": 0, "accuracy": 0.0}

    total = stats.get("total", 0)
    correct = stats.get("correct", 0)
    incorrect = stats.get("incorrect", 0)
    accuracy = stats.get("accuracy", 0.0)

    print(f"""
+==========================================+
|     VibeMind Intent Accuracy             |
+==========================================+
| Total Classifications: {total:>6}             |
| Correct:              {correct:>6}             |
| Incorrect:            {incorrect:>6}             |
| Accuracy:             {accuracy*100:>5.1f}%            |
+==========================================+
    """)


def print_category_stats() -> None:
    """Display statistics per intent category."""
    stats = get_category_stats()

    print("\n+------------------------------------------+")
    print("| Category        | Intents | Description  |")
    print("+------------------------------------------+")
    for cat, count in stats.items():
        print(f"| {cat.value:<15} | {count:>7} |")
    print("+------------------------------------------+")


def print_utterance_stats() -> None:
    """Display statistics about synthetic utterances."""
    stats = get_utterance_stats()

    print(f"""
+==========================================+
|     Synthetic Utterance Stats            |
+==========================================+
| Total Utterances: {stats['total']:>6}                  |
| Intents Covered:  {stats['intents_covered']:>6}                  |
+------------------------------------------+
| By Difficulty:                           |
|   Easy:   {stats['by_difficulty']['easy']:>6}                        |
|   Medium: {stats['by_difficulty']['medium']:>6}                        |
|   Hard:   {stats['by_difficulty']['hard']:>6}                        |
+==========================================+
    """)


def print_full_dashboard() -> None:
    """Print complete evaluation dashboard."""
    print("\n" + "=" * 50)
    print("       VIBEMIND EVALUATION DASHBOARD")
    print("=" * 50)

    print_live_stats()
    print_category_stats()
    print_utterance_stats()


def format_stats_for_voice(session_id: Optional[str] = None) -> str:
    """
    Format statistics for voice output (German).

    Args:
        session_id: Optional session filter

    Returns:
        German text suitable for TTS
    """
    try:
        from ...data.conversion_ai_repository import get_conversion_ai_repo
        repo = get_conversion_ai_repo()
        stats = repo.get_analysis_stats(session_id=session_id)
    except Exception:
        return "Ich konnte die Statistiken nicht laden."

    total = stats.get("total", 0)
    correct = stats.get("correct", 0)
    accuracy = stats.get("accuracy", 0.0)

    if total == 0:
        return "Ich habe noch keine Statistiken. Bitte gib mir Feedback nach meinen Aktionen."

    return (
        f"Insgesamt habe ich {total} Anfragen bearbeitet. "
        f"Davon waren {correct} richtig, das entspricht einer Genauigkeit von {accuracy * 100:.0f} Prozent."
    )


if __name__ == "__main__":
    print_full_dashboard()
