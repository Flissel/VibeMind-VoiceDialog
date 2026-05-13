"""Test the new Brain+Regex fast-path directly."""
import os, asyncio, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

os.environ["BRAIN_EVENT_FORCE_ACTIVE"] = "true"
os.environ["BRAIN_EVENT_MIN_CONFIDENCE"] = "0.5"

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from swarm.routing.brain_event_shadow import BrainEventShadowObserver

async def main():
    brain = BrainEventShadowObserver()

    tests = [
        "Lösche die Bubble Realtime Test 1",
        "Lösche Bubble Marketing",
        "Entferne Space Ideen",
        "Geh in Bubble VibeMind",
    ]

    _regex_extractable = {
        "bubble.delete": ("bubble_name", [
            r"(?:l[öo]esche|entferne|delete|remove)\s+(?:die\s+|the\s+)?(?:bubble|space)\s+(.+?)(?:\s*$|[,.!?])",
            r"(?:bubble|space)\s+(.+?)\s+(?:l[öo]eschen|entfernen|delete|remove)",
        ]),
        "bubble.enter": ("bubble_name", [
            r"(?:geh|oeffne|open|enter|wechsle|betrete)\s+(?:in\s+|zu\s+|to\s+|die\s+)?(?:bubble|space)\s+(.+?)(?:\s*$|[,.!?])",
        ]),
    }

    for text in tests:
        print(f"\n>>> {text}")
        try:
            cls = await brain.classify_via_brain(text)
            print(f"  Brain: {cls.get('event_type')} ({cls.get('confidence', 0):.0%})")
            evt = cls.get("event_type", "")
            if evt in _regex_extractable:
                pkey, patterns = _regex_extractable[evt]
                for pat in patterns:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip().rstrip(".,!?").strip()
                        print(f"  Regex: {pkey}='{val}' (pattern matched)")
                        break
                else:
                    print(f"  Regex: no match")
        except Exception as e:
            print(f"  ERROR: {e}")

asyncio.run(main())
