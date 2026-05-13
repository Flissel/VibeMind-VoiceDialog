"""CLI wrapper for the UserSimulator — systematic Brain training per space.

Examples:
  python scripts/run_brain_simulator.py --spaces all --reps 5
  python scripts/run_brain_simulator.py --spaces bubbles,ideas --reps 10
  python scripts/run_brain_simulator.py --validate-only --spaces bubbles
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.brain_simulator import UserSimulator


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain-url", default="http://localhost:5000")
    ap.add_argument("--spaces", default="all", help="comma-separated or 'all'")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--delay-ms", type=int, default=10)
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--validate-after", action="store_true")
    ap.add_argument("--adaptive", action="store_true",
                    help="Pump weak events with extra reps until target accuracy")
    ap.add_argument("--max-reps", type=int, default=30,
                    help="Max reps per event in adaptive mode (default 30)")
    ap.add_argument("--target-acc", type=float, default=0.75,
                    help="Accuracy threshold in adaptive mode (default 0.75)")
    ap.add_argument("--report", type=str, default="")
    args = ap.parse_args()

    sim = UserSimulator(brain_url=args.brain_url, delay_ms=args.delay_ms)
    all_spaces = sim.all_spaces()
    targets = all_spaces if args.spaces == "all" else [
        s.strip() for s in args.spaces.split(",") if s.strip()
    ]

    print(f"Brain: {args.brain_url}")
    print(f"Spaces: {targets}")
    print(f"Total events: {sum(len(sim.events_for_space(s)) for s in targets)}")
    print(f"Reps per variant: {args.reps}")
    print()

    report: dict = {"trained": {}, "validation": {}}

    if not args.validate_only:
        for space in targets:
            if args.adaptive:
                r = sim.train_space_adaptive(
                    space,
                    base_reps=args.reps,
                    max_reps=args.max_reps,
                    target_accuracy=args.target_acc,
                )
            else:
                r = sim.train_space(space, repetitions=args.reps)
            report["trained"][space] = r
            print(f"-> {space}: {r['samples']} samples in {r['duration_sec']}s")
            print()

    if args.validate_only or args.validate_after:
        print("\n== Validation ==")
        for space in targets:
            v = sim.validate_space(space, samples_per_event=3)
            report["validation"][space] = v
            weak = v["weak_events"]
            total = len(v["events"])
            good = total - len(weak)
            print(f"  {space}: {good}/{total} events ok, weak: {weak or '-'}")

    stats = sim.brain_stats()
    report["brain_stats"] = stats

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {args.report}")
    else:
        print(f"\nTotal samples sent: {sum(r['samples'] for r in report['trained'].values())}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
