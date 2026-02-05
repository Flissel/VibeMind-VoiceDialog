#!/usr/bin/env python
"""
Analyze intent classification logs.

Usage:
    python scripts/analyze_intent_logs.py                    # Analyze all logs
    python scripts/analyze_intent_logs.py logs/intents/intents_2024-01-13.jsonl  # Specific file
    python scripts/analyze_intent_logs.py --last 100         # Last 100 entries
"""

import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime
from typing import List, Dict, Any


def load_logs(log_file: Path) -> List[Dict[str, Any]]:
    """Load entries from a JSONL file."""
    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def analyze_logs(entries: List[Dict[str, Any]]) -> None:
    """Analyze and print statistics for log entries."""
    if not entries:
        print("No entries to analyze.")
        return

    print(f"=== Intent Log Analysis ({len(entries)} entries) ===\n")

    # Time range
    timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
    if timestamps:
        first = timestamps[0][:19]
        last = timestamps[-1][:19]
        print(f"Time range: {first} to {last}\n")

    # Intent Distribution
    intents = Counter()
    for e in entries:
        if "error" in e:
            intents["ERROR"] += 1
        elif e.get("classification", {}).get("is_multi_step"):
            intents["MULTI-STEP"] += 1
        else:
            intent = e.get("classification", {}).get("event_type", "unknown")
            intents[intent] += 1

    print("Intent Distribution:")
    for intent, count in intents.most_common(15):
        pct = count / len(entries) * 100
        bar = "#" * int(pct / 2)
        print(f"  {intent:30s} {count:4d} ({pct:5.1f}%) {bar}")

    # Latency Stats
    latencies = [
        e.get("metrics", {}).get("latency_ms", 0)
        for e in entries
        if e.get("metrics", {}).get("latency_ms")
    ]

    if latencies:
        latencies_sorted = sorted(latencies)
        p50_idx = len(latencies_sorted) // 2
        p95_idx = int(len(latencies_sorted) * 0.95)
        p99_idx = int(len(latencies_sorted) * 0.99)

        print(f"\nLatency (ms):")
        print(f"  Min:  {min(latencies):.0f}")
        print(f"  P50:  {latencies_sorted[p50_idx]:.0f}")
        print(f"  P95:  {latencies_sorted[p95_idx]:.0f}")
        print(f"  P99:  {latencies_sorted[p99_idx]:.0f}")
        print(f"  Max:  {max(latencies):.0f}")
        print(f"  Avg:  {sum(latencies)/len(latencies):.0f}")

    # Post-Processing Corrections
    corrected = [
        e for e in entries
        if e.get("post_processing", {}).get("was_corrected")
    ]
    if entries:
        correction_rate = len(corrected) / len(entries) * 100
        print(f"\nPost-Processing Corrections: {len(corrected)}/{len(entries)} ({correction_rate:.1f}%)")

    # Rule Usage
    rules = Counter()
    for e in entries:
        for rule in e.get("post_processing", {}).get("rules_applied", []):
            rules[rule] += 1

    if rules:
        print("\nRule Usage (top 10):")
        for rule, count in rules.most_common(10):
            print(f"  {rule:35s} {count:4d}")

    # Errors
    errors = [e for e in entries if "error" in e]
    if errors:
        print(f"\nErrors: {len(errors)}")
        error_types = Counter(e.get("error", "")[:50] for e in errors)
        for error, count in error_types.most_common(5):
            print(f"  {error}: {count}")

    # Multi-step breakdown
    multi_steps = [e for e in entries if e.get("classification", {}).get("is_multi_step")]
    if multi_steps:
        print(f"\nMulti-Step Classifications: {len(multi_steps)}")
        step_counts = Counter(
            len(e.get("classification", {}).get("steps", []))
            for e in multi_steps
        )
        for count, num in step_counts.most_common():
            print(f"  {count} steps: {num} occurrences")


def main():
    # Parse arguments
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    last_n = None
    log_file = None

    if "--last" in args:
        idx = args.index("--last")
        if idx + 1 < len(args):
            last_n = int(args[idx + 1])
            args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]

    if args:
        log_file = Path(args[0])
        if not log_file.exists():
            print(f"Error: File not found: {log_file}")
            sys.exit(1)
        entries = load_logs(log_file)
    else:
        # Load all logs from default directory
        log_dir = Path("logs/intents")
        if not log_dir.exists():
            print(f"No logs found in {log_dir}")
            print("Run VibeMind to generate some classifications first.")
            sys.exit(1)

        entries = []
        for log_file in sorted(log_dir.glob("*.jsonl")):
            entries.extend(load_logs(log_file))

    if last_n:
        entries = entries[-last_n:]

    analyze_logs(entries)


if __name__ == "__main__":
    main()
