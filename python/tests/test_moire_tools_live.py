#!/usr/bin/env python3
"""
Test Moire Tools Live
Tests moire_scan, moire_find_element, moire_get_ui_context against real MoireServer.

Prerequisites:
- MoireServer running on ws://localhost:8766
- Start with: cd MoireTracker_v2 && npm start

Usage:
    python test_moire_tools_live.py
"""

import asyncio
import sys
from tools.moire_tools import (
    get_moire_client,
    moire_scan,
    moire_find_element,
    moire_get_ui_context,
    HAS_WEBSOCKETS
)


async def test_connection():
    """Test 1: WebSocket connection to MoireServer."""
    print("\n" + "="*60)
    print("TEST 1: MoireServer Connection")
    print("="*60)

    client = get_moire_client()
    connected = await client.connect()

    if connected:
        print(f"  Connected to {client.uri}")
        return True
    else:
        print(f"  Failed to connect to {client.uri}")
        print("  Is MoireServer running? Start with: npm start")
        return False


async def test_moire_scan():
    """Test 2: Full desktop OCR scan."""
    print("\n" + "="*60)
    print("TEST 2: moire_scan()")
    print("="*60)

    result = await moire_scan(timeout=30.0)

    if result.get("success"):
        print(f"  Scan successful")
        print(f"  Texts found: {result.get('text_count', 0)}")
        print(f"  Elements: {result.get('element_count', 0)}")
        print(f"  Processing time: {result.get('processing_time_ms', 0):.0f}ms")
        texts = result.get("texts", [])[:5]
        if texts:
            print(f"  Sample texts: {texts}")
        return True
    else:
        print(f"  Scan failed: {result.get('error')}")
        return False


async def test_moire_find_element():
    """Test 3: Find specific UI element."""
    print("\n" + "="*60)
    print("TEST 3: moire_find_element('Start')")
    print("="*60)

    result = await moire_find_element("Start")

    if result.get("success"):
        if result.get("found"):
            x, y = result.get("x"), result.get("y")
            print(f"  Found 'Start' at ({x}, {y})")
            return True
        else:
            print(f"  Element not found (this may be OK)")
            print(f"  Available: {result.get('message', '')[:100]}")
            return True  # Not a failure, just not visible
    else:
        print(f"  Search failed: {result.get('error')}")
        return False


async def test_moire_get_ui_context():
    """Test 4: Get full UI context."""
    print("\n" + "="*60)
    print("TEST 4: moire_get_ui_context()")
    print("="*60)

    result = await moire_get_ui_context()

    if result.get("success"):
        print(f"  UI context retrieved")
        print(f"  Total elements: {result.get('total_elements', 0)}")
        print(f"  With text: {result.get('with_text', 0)}")
        categories = result.get("by_category", {})
        if categories:
            print(f"  Categories: {list(categories.keys())}")
        return True
    else:
        print(f"  Context failed: {result.get('error')}")
        return False


async def run_all_tests():
    """Run all Moire tool tests."""
    print("="*60)
    print("MOIRE TOOLS LIVE TEST")
    print("="*60)
    print(f"websockets available: {HAS_WEBSOCKETS}")

    if not HAS_WEBSOCKETS:
        print("ERROR: websockets package not installed")
        return False

    results = []

    # Test 1: Connection
    results.append(await test_connection())
    if not results[-1]:
        print("\n" + "="*60)
        print("ABORTED: Cannot connect to MoireServer")
        return False

    # Test 2-4: Tool functions
    results.append(await test_moire_scan())
    results.append(await test_moire_find_element())
    results.append(await test_moire_get_ui_context())

    # Cleanup
    client = get_moire_client()
    await client.disconnect()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("All tests passed!")
        return True
    else:
        print("Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
