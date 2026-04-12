"""Debug: test YamlClassifier directly with delete prompts."""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from swarm.orchestrator.yaml_classifier import YamlClassifier

async def test():
    c = YamlClassifier()
    for text in [
        "Lösche die Bubble Realtime Test 1",
        "Loesche Bubble Marketing",
        "Entferne Space Ideen",
        "Delete bubble Research",
    ]:
        try:
            r = await c.classify(text)
            print(f"  {text!r}")
            print(f"  -> {r}")
        except Exception as e:
            print(f"  {text!r} -> ERROR: {e}")

asyncio.run(test())
