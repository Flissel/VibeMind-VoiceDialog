"""Debug pipeline: find why bridge returns None."""
import asyncio
import aiohttp
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge, SPACE_AGENT_MAP

OPENFANG_PORT = 4200

async def main():
    print("=== Step 1: Brain Route ===")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as s:
        async with s.post("http://localhost:5000/api/cortex/route", json={
            "user_text": "Erstelle eine Idee", "event_type": "idea.create"
        }) as r:
            data = await r.json()
            print(json.dumps(data, indent=2))
            space = data.get("primary_space", "")

    print(f"\n=== Step 2: Space Mapping ===")
    agent_name = SPACE_AGENT_MAP.get(space, "?")
    print(f"  Space '{space}' -> Agent '{agent_name}'")

    print(f"\n=== Step 3: OpenFang Agents ===")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as s:
        async with s.get(f"http://localhost:{OPENFANG_PORT}/api/agents") as r:
            agents = await r.json()
            brain_agents = [a for a in agents if "brain" in a.get("name", "") or a.get("name") == "vibemind"]
            for a in brain_agents:
                print(f"  {a['name']:25s} {a['id'][:12]}...")

            match = [a for a in agents if a.get("name") == agent_name]
            if match:
                print(f"\n  MATCH: '{agent_name}' found -> {match[0]['id']}")
            else:
                print(f"\n  NO MATCH: '{agent_name}' not in OpenFang!")
                print(f"  Available: {[a['name'] for a in agents]}")

    print(f"\n=== Step 4: Direct Bridge Test ===")
    bridge = BrainOpenFangBridge(
        brain_url="http://localhost:5000",
        openfang_url=f"http://localhost:{OPENFANG_PORT}",
        min_confidence=0.0,
    )
    # Test _ensure_agent directly
    agent_id = await bridge._ensure_agent(agent_name)
    print(f"  _ensure_agent('{agent_name}') -> {agent_id}")

    if agent_id:
        print(f"\n=== Step 5: Send Message ===")
        try:
            response = await asyncio.wait_for(
                bridge._send_to_openfang(agent_id, "Test: Erstelle eine Idee"),
                timeout=15.0
            )
            print(f"  Response: {str(response)[:200]}")
        except Exception as e:
            print(f"  Error: {e}")

asyncio.run(main())
