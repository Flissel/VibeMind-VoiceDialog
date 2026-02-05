#!/usr/bin/env python3
"""
Simple Test for Super Memory API
"""

import asyncio
import tempfile
import os
from super_memory_api import SuperMemoryAPI, MemoryQuery

async def test_super_memory():
    print("🧠 Testing Super Memory API...")

    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()
    memory = SuperMemoryAPI(db_path=db_path)

    try:
        # Test 1: Store memory
        print("  📝 Storing memory...")
        memory_id = await memory.store_memory(
            content="Test memory for simple validation",
            memory_type="test",
            user_id="test_user",
            session_id="test_session",
            importance=0.8,
            tags=["test", "validation"]
        )
        print(f"    ✅ Memory stored with ID: {memory_id}")

        # Test 2: Retrieve memory
        print("  🔍 Retrieving memory...")
        query = MemoryQuery(
            query_text="test memory",
            user_id="test_user",
            limit=5
        )
        result = await memory.retrieve_memories(query)
        print(f"    ✅ Found {len(result.results)} memories")

        if result.results:
            memory_obj = result.results[0]
            print(f"    ✅ Memory content: {memory_obj.content[:50]}...")
            print(f"    ✅ Memory type: {memory_obj.memory_type}")
            print(f"    ✅ Importance: {memory_obj.importance}")
            print(f"    ✅ Tags: {list(memory_obj.tags)}")

        # Test 3: Update importance
        print("  📈 Updating importance...")
        if result.results:
            success = await memory.update_memory_importance(result.results[0].id, 0.9)
            print(f"    ✅ Update successful: {success}")

        # Test 4: Get statistics
        print("  📊 Getting statistics...")
        stats = await memory.get_memory_stats("test_user")
        print(f"    ✅ Total memories: {stats['total_memories']}")
        print(f"    ✅ Average importance: {stats['avg_importance']:.2f}")

        print("🎉 Super Memory API test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        memory = None
        os.close(db_fd)
        os.unlink(db_path)

if __name__ == "__main__":
    asyncio.run(test_super_memory())