#!/usr/bin/env python
"""
Analyze tool execution logs.

Usage:
    python scripts/analyze_tool_logs.py                    # Analyze all logs
    python scripts/analyze_tool_logs.py logs/tools/tools_2024-01-13.jsonl  # Specific file
    python scripts/analyze_tool_logs.py --last 100         # Last 100 entries
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
    """Analyze and print statistics for tool execution logs."""
    if not entries:
        print("No entries to analyze.")
        return

    print(f"=== Tool Execution Analysis ({len(entries)} entries) ===\n")

    # Time range
    timestamps = [e.get("timestamp", "") for e in entries if e.get("timestamp")]
    if timestamps:
        first = timestamps[0][:19]
        last = timestamps[-1][:19]
        print(f"Time range: {first} to {last}\n")

    # Tool Distribution
    tools = Counter()
    for e in entries:
        tool = e.get("tool_name", "unknown")
        tools[tool] += 1

    print("Tool Usage:")
    for tool, count in tools.most_common(15):
        pct = count / len(entries) * 100
        bar = "#" * int(pct / 2)
        print(f"  {tool:30s} {count:4d} ({pct:5.1f}%) {bar}")

    # Success Rate
    successful = [e for e in entries if e.get("metrics", {}).get("success")]
    failed = [e for e in entries if not e.get("metrics", {}).get("success")]
    success_rate = len(successful) / len(entries) * 100
    print(f"\nSuccess Rate: {len(successful)}/{len(entries)} ({success_rate:.1f}%)")

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

    # Latency by Tool
    latency_by_tool = {}
    for e in entries:
        tool = e.get("tool_name", "unknown")
        latency = e.get("metrics", {}).get("latency_ms", 0)
        if latency:
            if tool not in latency_by_tool:
                latency_by_tool[tool] = []
            latency_by_tool[tool].append(latency)

    if latency_by_tool:
        print("\nLatency by Tool (avg ms):")
        tool_avgs = [
            (tool, sum(lats) / len(lats))
            for tool, lats in latency_by_tool.items()
            if lats
        ]
        tool_avgs.sort(key=lambda x: -x[1])  # Sort by latency descending
        for tool, avg_lat in tool_avgs[:10]:
            print(f"  {tool:30s} {avg_lat:6.0f} ms")

    # Source Events
    sources = Counter()
    for e in entries:
        source = e.get("source_event", "unknown")
        sources[source] += 1

    if sources:
        print("\nSource Events:")
        for source, count in sources.most_common(10):
            print(f"  {source:30s} {count:4d}")

    # Errors
    if failed:
        print(f"\nErrors: {len(failed)}")
        error_types = Counter()
        for e in failed:
            error = e.get("error", "Unknown")[:60]
            error_types[error] += 1

        for error, count in error_types.most_common(5):
            print(f"  [{count}x] {error}")

    # Tool Success Rate Breakdown
    print("\nSuccess Rate by Tool:")
    tool_success = {}
    for e in entries:
        tool = e.get("tool_name", "unknown")
        success = e.get("metrics", {}).get("success", False)
        if tool not in tool_success:
            tool_success[tool] = {"success": 0, "fail": 0}
        if success:
            tool_success[tool]["success"] += 1
        else:
            tool_success[tool]["fail"] += 1

    for tool, stats in sorted(tool_success.items()):
        total = stats["success"] + stats["fail"]
        rate = stats["success"] / total * 100 if total > 0 else 0
        if rate < 100:  # Only show tools with failures
            print(f"  {tool:30s} {rate:5.1f}% ({stats['success']}/{total})")


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
        log_dir = Path("logs/tools")
        if not log_dir.exists():
            print(f"No logs found in {log_dir}")
            print("Run VibeMind to generate some tool executions first.")
            sys.exit(1)

        entries = []
        for log_file in sorted(log_dir.glob("*.jsonl")):
            entries.extend(load_logs(log_file))

    if last_n:
        entries = entries[-last_n:]

    analyze_logs(entries)


if __name__ == "__main__":
    main()
