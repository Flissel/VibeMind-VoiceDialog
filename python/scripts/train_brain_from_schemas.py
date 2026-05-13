"""
Train Brain from tool_schemas.yml

Reads config/tool_schemas.yml, generates training pairs (user_text → event_type)
from the `examples` and `triggers` fields, and pushes them to the Brain's
supervised training endpoint at POST /api/cortex/classify/train.

Usage:
    python scripts/train_brain_from_schemas.py
    python scripts/train_brain_from_schemas.py --dry-run       # show what would be sent
    python scripts/train_brain_from_schemas.py --epochs 3      # multiple passes
    python scripts/train_brain_from_schemas.py --brain-url http://localhost:5000
"""

import argparse
import asyncio
import sys
from pathlib import Path

import aiohttp
import yaml


DEFAULT_BRAIN_URL = "http://localhost:5000"
DEFAULT_SCHEMA_PATH = Path(__file__).parent.parent / "config" / "tool_schemas.yml"


def load_schemas(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_training_pairs(schemas: dict) -> list[tuple[str, str]]:
    """Extract (user_text, event_type) pairs from schema examples."""
    pairs: list[tuple[str, str]] = []
    for event_type, schema in schemas.items():
        if not isinstance(schema, dict):
            continue
        examples = schema.get("examples", []) or []
        for ex in examples:
            if not isinstance(ex, dict):
                continue
            user_text = ex.get("input", "").strip()
            if user_text:
                pairs.append((user_text, event_type))
    return pairs


async def train_pair(
    session: aiohttp.ClientSession,
    brain_url: str,
    user_text: str,
    event_type: str,
) -> bool:
    """Send one training pair to the Brain. Returns True on HTTP 200."""
    try:
        async with session.post(
            f"{brain_url}/api/cortex/classify/train",
            json={"user_text": user_text, "correct_event_type": event_type},
            timeout=aiohttp.ClientTimeout(total=5.0),
        ) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  ERROR {user_text!r} -> {event_type}: {e}")
        return False


async def verify_brain(session: aiohttp.ClientSession, brain_url: str) -> bool:
    try:
        async with session.get(
            f"{brain_url}/api/cortex/classify",
            timeout=aiohttp.ClientTimeout(total=3.0),
        ) as resp:
            return resp.status in (200, 405)
    except Exception:
        return False


async def run(brain_url: str, schema_path: Path, epochs: int, dry_run: bool) -> int:
    schemas = load_schemas(schema_path)
    pairs = build_training_pairs(schemas)

    print(f"Loaded {len(schemas)} events from {schema_path.name}")
    print(f"Built {len(pairs)} training pairs")

    if dry_run:
        print("\n--- DRY RUN ---")
        for text, evt in pairs:
            print(f"  {evt:30s}  <-  {text!r}")
        return 0

    async with aiohttp.ClientSession() as session:
        if not await verify_brain(session, brain_url):
            print(f"Brain unreachable at {brain_url} — is it running on port 5000?")
            return 1

        total_ok = 0
        total_fail = 0
        for epoch in range(1, epochs + 1):
            print(f"\n=== Epoch {epoch}/{epochs} ===")
            for text, evt in pairs:
                ok = await train_pair(session, brain_url, text, evt)
                if ok:
                    total_ok += 1
                else:
                    total_fail += 1
            print(f"  epoch done: ok={total_ok}  fail={total_fail}")

        print(f"\nDone. {total_ok} pairs sent successfully, {total_fail} failed.")
        return 0 if total_fail == 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain-url", default=DEFAULT_BRAIN_URL)
    ap.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.schema.exists():
        print(f"Schema file not found: {args.schema}")
        return 1

    return asyncio.run(run(args.brain_url, args.schema, args.epochs, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
