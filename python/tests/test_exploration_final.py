"""Final exploration test with working embeddings."""
import sys
import asyncio
sys.stdout.reconfigure(encoding='utf-8')

async def test_exploration():
    print("=" * 60)
    print("FINAL EXPLORATION TEST")
    print("=" * 60)

    # 1. Check embedding service
    print("\n1. Checking embedding service...")
    from data.embedding_service import get_embedding_service
    service = get_embedding_service()
    print(f"   Available: {service.is_available}")
    print(f"   Fallback: {service.is_using_fallback}")

    # 2. Check bubbles
    print("\n2. Checking bubbles...")
    from data import IdeasRepository
    repo = IdeasRepository()
    ideas = repo.list(limit=50)
    bubbles = [i for i in ideas if not i.parent_id]
    print(f"   Found {len(bubbles)} bubbles")

    # 3. Start exploration
    print("\n3. Starting exploration...")
    from swarm.tools.exploration_tools import start_exploration, get_exploration_status, stop_exploration

    result = await start_exploration(
        bubble_id=None,  # Use first available
        depth=2,
        mode="auto",
        context=None
    )

    print(f"   Success: {result.get('success')}")
    print(f"   Message: {result.get('message')}")

    if result.get('success'):
        print(f"   Session ID: {result.get('session_id', 'N/A')}")
        print(f"   Root bubble: {result.get('root_bubble', 'N/A')}")

        # Wait a bit for exploration to run
        print("\n4. Waiting for exploration (3 seconds)...")
        await asyncio.sleep(3)

        # Check status
        print("\n5. Checking status...")
        status = await get_exploration_status()
        print(f"   Status: {status.get('status')}")
        print(f"   Nodes discovered: {status.get('nodes_discovered', 0)}")
        print(f"   Best score: {status.get('best_score', 0)}")
        print(f"   Message: {status.get('message', 'N/A')}")

        # Stop exploration
        print("\n6. Stopping exploration...")
        stop_result = await stop_exploration()
        print(f"   {stop_result.get('message', 'Stopped')}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(test_exploration())
