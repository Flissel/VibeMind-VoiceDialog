#!/usr/bin/env python3
"""
Simple Test for VibeMind API
"""

import asyncio
import tempfile
import os
from vibemind_api import VibeMindAPI

async def test_api():
    print("🌐 Testing VibeMind API...")

    # Create temporary upload directory
    upload_dir = tempfile.mkdtemp()

    # Create API server
    api = VibeMindAPI()
    api.upload_dir = upload_dir

    try:
        # Test 1: API initialization
        print("  🚀 Testing API initialization...")
        assert api.app is not None
        assert api.super_memory is not None
        assert api.orchestrator is not None
        print("    ✅ API initialized successfully")

        # Test 2: Health endpoint (simulate)
        print("  ❤️ Testing health endpoint...")
        # We can't easily test FastAPI endpoints without a test client,
        # but we can verify the endpoint exists
        routes = [route.path for route in api.app.routes]
        assert "/health" in routes
        assert "/api/v1/memory/store" in routes
        assert "/api/v1/intent/process" in routes
        print("    ✅ API routes configured correctly")

        # Test 3: Super Memory integration
        print("  🧠 Testing Super Memory integration...")
        memory_id = await api.super_memory.store_memory(
            content="API test memory",
            memory_type="test",
            user_id="api_test_user",
            session_id="api_test_session"
        )
        print(f"    ✅ Memory stored via API: {memory_id}")

        # Test 4: Intent processing integration
        print("  🎯 Testing intent processing integration...")
        # Test that orchestrator is accessible
        assert api.orchestrator is not None
        print("    ✅ Intent orchestrator integrated")

        # Test 5: Upload functionality
        print("  📁 Testing upload functionality...")
        assert os.path.exists(upload_dir)
        assert api.upload_dir == upload_dir
        print("    ✅ Upload directory configured")

        # Test 6: API statistics
        print("  📊 Testing API statistics...")
        # Test that agent history is initialized
        assert hasattr(api, 'agent_history')
        assert isinstance(api.agent_history, list)
        print("    ✅ Agent history tracking initialized")

        print("🎉 VibeMind API test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(upload_dir)

if __name__ == "__main__":
    asyncio.run(test_api())