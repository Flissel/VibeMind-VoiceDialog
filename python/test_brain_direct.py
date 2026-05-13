"""Direct Brain + OpenFang API test."""
import asyncio
import aiohttp
import json

async def main():
    timeout = aiohttp.ClientTimeout(total=3.0)

    # 1. Test Brain route
    print("=== Brain Route ===")
    async with aiohttp.ClientSession(timeout=timeout) as session:
        payload = {
            "user_text": "[space:coding bubble:Backend ideas:7] Erstelle eine Idee fuer API Design",
            "event_type": "idea.create",
            "context": {"current_space": "coding", "current_bubble": "Backend", "idea_count": 7}
        }
        async with session.post("http://localhost:5000/api/cortex/route", json=payload) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))
            space = data.get("primary_space", "")
            confidence = data.get("confidence", 0)
            routing_id = data.get("routing_id", "")
            print(f"\n  -> Space: {space}, Confidence: {confidence:.2f}")

    # 2. Test OpenFang agents list
    print("\n=== OpenFang Agents ===")
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get("http://localhost:4200/api/agents") as resp:
            agents = await resp.json()
            print(f"  {len(agents)} agents found:")
            for a in agents[:10]:
                name = a.get("name", "?")
                aid = a.get("id", "?")[:8]
                print(f"    {name} ({aid}...)")

    # 3. Test OpenFang message (send to first agent)
    if agents:
        print(f"\n=== OpenFang Message (to '{agents[0].get('name')}') ===")
        agent_id = agents[0].get("id", "")
        message = "[VibeMind Context]\nSpace: Backend (coding)\nIdeas: API Design, Auth Flow\n[End Context]\n\nErstelle eine Idee fuer API Design"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15.0)) as session:
            async with session.post(
                f"http://localhost:4200/api/agents/{agent_id}/message",
                json={"message": message}
            ) as resp:
                data = await resp.json()
                response_text = str(data)[:300]
                print(f"  Status: {resp.status}")
                print(f"  Response: {response_text}")

asyncio.run(main())
