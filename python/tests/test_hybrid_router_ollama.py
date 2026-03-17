#!/usr/bin/env python
"""
Full-stack HybridRouter test using Ollama (zero API credits).

Tests the complete flow: User Input → IntentClassifier (Ollama) → HybridRouter → Result

Usage:
    cd python
    python tests/test_hybrid_router_ollama.py

Requirements:
    - Ollama running locally (http://localhost:11434)
    - Model: llama3.1:8b or qwen2.5-coder:7b
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Override env BEFORE any imports ──
os.environ["OPENROUTER_API_KEY"] = "ollama"  # Dummy key, Ollama doesn't need one
os.environ["CLASSIFIER_MODEL"] = "qwen2.5:3b"
os.environ["USE_HYBRID_ROUTER"] = "true"
os.environ["HYBRID_ROUTER_DEBUG"] = "true"

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from swarm.routing.hybrid_router import HybridRouter
from swarm.orchestrator.intent_classifier import IntentClassifier


# ── Ollama-backed classifier ──
class OllamaClassifier(IntentClassifier):
    """IntentClassifier that talks to local Ollama instead of OpenRouter."""

    def __init__(self, model: str = "llama3.1:8b"):
        super().__init__(model=model)

    @property
    def client(self):
        if self._own_client is None:
            self._own_client = OpenAI(
                api_key="ollama",
                base_url="http://localhost:11434/v1"
            )
            print(f"  [Ollama] Connected, model={self._model}")
        return self._own_client


# ── Test Cases ──
TEST_CASES = [
    # (user_input, expected_prefix, expected_space)
    # One per space — keeps test fast with local LLM
    ("Zeig mir meine Bubbles", "bubble.", "ideas"),
    ("Notiere: API Design", "idea.", "ideas"),
    ("Erstelle eine App fuer Zeiterfassung", "code.", "coding"),
    ("Mach einen Screenshot", "desktop.", "desktop"),
    ("Setze einen Termin fuer morgen", "schedule.", "schedule"),
    ("Erstelle einen Workflow fuer Emails", "n8n.", "n8n"),
]


def colorize(text, color):
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
              "cyan": "\033[96m", "gray": "\033[90m", "reset": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['reset']}"


async def run_full_stack_test():
    print(colorize("\n  HybridRouter Full-Stack Test (Ollama)", "cyan"))
    print(colorize("  ======================================\n", "cyan"))

    # Check Ollama
    try:
        client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
        models = client.models.list()
        model_names = [m.id for m in models.data]
        print(f"  Ollama models: {', '.join(model_names[:5])}")
    except Exception as e:
        print(colorize(f"  ERROR: Ollama not available: {e}", "red"))
        print("  Start Ollama: ollama serve")
        return

    # Pick best available model
    # Smaller model = faster inference for testing
    preferred = ["qwen2.5:3b", "qwen2.5-coder:7b", "llama3.1:8b"]
    model = next((m for m in preferred if m in model_names), model_names[0])
    print(f"  Using model: {model}\n")

    classifier = OllamaClassifier(model=model)
    router = HybridRouter(use_llm=False)  # No SpaceRouter LLM needed — Tier 1 should handle

    passed = 0
    failed = 0
    total_classify_ms = 0
    total_route_ms = 0

    for user_input, expected_prefix, expected_space in TEST_CASES:
        # ── Step 1: Classify with Ollama ──
        t0 = time.perf_counter()
        try:
            classification = await classifier.classify(user_input)
            event_type = classification.get("event_type", "unknown") if classification else "unknown"
            # Ollama sometimes returns list or dict instead of string
            if not isinstance(event_type, str):
                event_type = str(event_type) if event_type else "unknown"
            params = classification.get("parameters", {}) if classification else {}
            if not isinstance(params, dict):
                params = {}
        except Exception as e:
            event_type = "error"
            params = {}
            print(colorize(f"  Classification error: {e}", "red"))
        classify_ms = (time.perf_counter() - t0) * 1000
        total_classify_ms += classify_ms

        # ── Step 2: Route with HybridRouter ──
        t0 = time.perf_counter()
        result = router.resolve_sync(event_type=event_type, user_input=user_input)
        route_ms = (time.perf_counter() - t0) * 1000
        total_route_ms += route_ms

        # ── Check Results ──
        prefix_ok = event_type.startswith(expected_prefix) if expected_prefix else True
        space_ok = (result.space == expected_space) if expected_space else True
        tier = result.tier

        if prefix_ok and space_ok:
            status = colorize("PASS", "green")
            passed += 1
        elif not prefix_ok:
            status = colorize("FAIL", "red")
            failed += 1
        else:
            status = colorize("FAIL", "red")
            failed += 1

        # Format output
        tier_color = "green" if tier == 1 else ("yellow" if tier == 2 else "gray")
        print(f"  {status} \"{user_input}\"")
        print(f"    Classify: {event_type} ({classify_ms:.0f}ms) | "
              f"Route: {result.space} Tier {colorize(str(tier), tier_color)} ({route_ms:.1f}ms) | "
              f"Params: {params if params else '-'}")
        if not prefix_ok:
            print(colorize(f"    Expected prefix: {expected_prefix}, got: {event_type}", "red"))
        if not space_ok and expected_space:
            print(colorize(f"    Expected space: {expected_space}, got: {result.space}", "red"))
        print()

    # ── Summary ──
    total = passed + failed
    avg_classify = total_classify_ms / total if total else 0
    avg_route = total_route_ms / total if total else 0

    print("=" * 60)
    if failed == 0:
        print(colorize(f"  ALL {total} TESTS PASSED", "green"))
    else:
        print(colorize(f"  {passed}/{total} passed, {failed} failed", "red"))
    print(f"  Avg classify: {avg_classify:.0f}ms | Avg route: {avg_route:.1f}ms")
    print(f"  Total: {total_classify_ms:.0f}ms classify + {total_route_ms:.1f}ms route")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_full_stack_test())
