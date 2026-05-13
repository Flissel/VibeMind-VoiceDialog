"""Full pipeline test: ContextAssembler -> Brain -> OpenFang -> Reward."""
import asyncio
import os
import sys
from pathlib import Path

_vibemind_root = str(Path(__file__).parent.parent.parent)
if _vibemind_root not in sys.path:
    sys.path.insert(0, _vibemind_root)

try:
    from dotenv import load_dotenv
    _root = Path(__file__).parent.parent.parent.parent / ".env"
    _voice = Path(__file__).parent.parent / ".env"
    if _root.exists():
        load_dotenv(_root)
    if _voice.exists():
        load_dotenv(_voice, override=False)
except ImportError:
    pass

from swarm.routing.context_assembler import ContextAssembler, WorkspaceContext
from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge


async def main():
    openfang_url = os.getenv("OPENFANG_URL", "http://localhost:4200")
    bridge = BrainOpenFangBridge(
        brain_url="http://localhost:5000",
        openfang_url=openfang_url,
        min_confidence=0.0,  # Accept any Brain decision for testing
    )

    test_inputs = [
        ("Erstelle eine Idee fuer API Design", "idea.create"),
        ("Zeig mir alle Bubbles", "bubble.list"),
        ("Schreibe Python Code fuer einen HTTP Server", "code.generate"),
        ("Oeffne Chrome", "desktop.open_app"),
        ("Recherchiere KI Trends 2026", "research.web"),
    ]

    for intent_text, event_type in test_inputs:
        print(f"\n{'='*60}")
        print(f"Input: \"{intent_text}\"")
        print(f"Pre-classification: {event_type}")
        print("-" * 60)

        result = await bridge.execute(
            intent_text=intent_text,
            context=None,
            pre_classification=event_type,
        )

        if result:
            print(f"  Event:    {result.event_type}")
            print(f"  Stream:   {result.stream}")
            print(f"  Response: {result.response_hint[:200]}")
            if result.error:
                print(f"  Error:    {result.error}")
        else:
            print("  Result:   None (fell through to HybridRouter)")

    print(f"\n{'='*60}")
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
