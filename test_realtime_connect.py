"""Quick test: Can we connect to OpenAI Realtime API?"""
import asyncio
import os
import sys

# Load .env
with open('.env') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

async def test():
    from openai import AsyncOpenAI

    api_key = os.getenv('OPENAI_API_KEY')
    print(f"API key: {api_key[:20]}...{api_key[-10:]}")

    client = AsyncOpenAI(api_key=api_key)
    print("Client created")
    print(f"realtime type: {type(client.realtime)}")

    try:
        print("Calling client.realtime.connect()...")
        conn_ctx = client.realtime.connect(model="gpt-4o-realtime-preview")
        print(f"Context type: {type(conn_ctx)}")

        print("Calling __aenter__()...")
        conn = await conn_ctx.__aenter__()
        print(f"Connected! type: {type(conn)}")

        await conn.__aexit__(None, None, None)
        print("Disconnected OK")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
