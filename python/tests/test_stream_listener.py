"""
Test: StreamListener — alle 8 Listener parallel evaluieren.

Testet jeden Listener mit einer domänenspezifischen Anfrage
und zeigt die komplette Confidence-Verteilung.
"""

import asyncio
import os
import sys
import time

# Add project root to path
python_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(python_dir)
sys.path.insert(0, python_dir)

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from swarm.stream_listener.models import EvalContext, StreamListenerConfig
from swarm.stream_listener.dispatcher import StreamListenerDispatcher
from swarm.stream_listener.listeners.ideas_listener import IdeasStreamListener
from swarm.stream_listener.listeners.coding_listener import CodingStreamListener
from swarm.stream_listener.listeners.desktop_listener import DesktopStreamListener
from swarm.stream_listener.listeners.roarboot_listener import RoarbootStreamListener
from swarm.stream_listener.listeners.research_listener import ResearchStreamListener
from swarm.stream_listener.listeners.minibook_listener import MinibookStreamListener
from swarm.stream_listener.listeners.shuttles_listener import ShuttlesStreamListener
from swarm.stream_listener.listeners.conversational_listener import ConversationalStreamListener


# Test cases: (description, input, expected_winner)
TEST_CASES = [
    ("Ideas: Bubble auflisten", "Welche Bubbles hab ich?", "ideas"),
    ("Ideas: Bubble erstellen", "Erstelle eine Bubble Marketing", "ideas"),
    ("Ideas: Idee notieren", "Notiere: API Design Pattern fuer REST", "ideas"),
    ("Coding: App bauen", "Erstelle eine React App fuer ein Dashboard", "coding"),
    ("Desktop: App oeffnen", "Oeffne Chrome", "desktop"),
    ("Desktop: Nachricht senden", "Schreib meiner Mutter dass ich spaeter komme", "desktop"),
    ("Roarboot: Wissen abfragen", "Was weiss ich ueber das Projekt Alpha?", "roarboot"),
    ("Research: Web-Recherche", "Recherchiere ueber die neuesten AI Trends 2024", "research"),
    ("Conversational: Begruessung", "Hallo Rachel, wie geht es dir?", "conversational"),
    ("Conversational: Hilfe", "Was kannst du alles?", "conversational"),
]


async def test_single_listener(listener, text: str, context: EvalContext, model: str):
    """Test a single listener."""
    result = await listener.evaluate(text, context, model=model)
    return result


async def test_full_distribution(dispatcher, text: str, context: EvalContext):
    """Run full parallel evaluation and return distribution."""
    return await dispatcher.evaluate_all(text, context)


async def main():
    model = os.getenv("STREAM_LISTENER_MODEL", "openai/gpt-4o-mini")
    print(f"\n{'='*70}")
    print(f"  StreamListener Test — Model: {model}")
    print(f"{'='*70}\n")

    # Create dispatcher with all listeners
    config = StreamListenerConfig(model=model)
    dispatcher = StreamListenerDispatcher(config)

    listeners = [
        IdeasStreamListener(),
        CodingStreamListener(),
        DesktopStreamListener(),
        RoarbootStreamListener(),
        ResearchStreamListener(),
        MinibookStreamListener(),
        ShuttlesStreamListener(),
        ConversationalStreamListener(),
    ]
    for l in listeners:
        dispatcher.register_listener(l)

    context = EvalContext(
        conversation_history=[],
        current_bubble=None,
        idea_count=0,
    )

    passed = 0
    failed = 0

    for desc, text, expected_winner in TEST_CASES:
        print(f"\n--- {desc} ---")
        print(f"  Input: \"{text}\"")
        print(f"  Expected: {expected_winner}")

        start = time.perf_counter()
        dist = await test_full_distribution(dispatcher, text, context)
        elapsed = (time.perf_counter() - start) * 1000

        # Show distribution
        for ev in dist.evaluations:
            marker = " <-- WINNER" if dist.winner and ev.space == dist.winner.space else ""
            print(f"    {ev.space:15s} = {ev.confidence:.2f}  ({ev.event_type:30s})  {ev.reasoning[:50]}{marker}")

        if dist.winner:
            actual = dist.winner.space
            status = "PASS" if actual == expected_winner else "FAIL"
            if actual == expected_winner:
                passed += 1
            else:
                failed += 1
            print(f"  Result: {status} — Winner: {actual} ({dist.winner.confidence:.2f}) -> {dist.winner.event_type}  [{elapsed:.0f}ms]")
        else:
            failed += 1
            print(f"  Result: FAIL — No winner  [{elapsed:.0f}ms]")

        if dist.is_ambiguous:
            print(f"  WARNING: Ambiguous (top-2 too close)")

    print(f"\n{'='*70}")
    print(f"  Results: {passed}/{passed+failed} passed, {failed} failed")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
