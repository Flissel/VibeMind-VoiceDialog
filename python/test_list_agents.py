import asyncio, aiohttp, json

async def main():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as s:
        async with s.get("http://localhost:4200/api/agents") as r:
            agents = await r.json()
            for a in agents:
                print(f"{a.get('name','?'):30s} {a.get('id','?')[:12]}...")

asyncio.run(main())
