"""
Test script for MoireTracker IPC bridge
Run with: python test_moire_bridge.py
"""

import sys
import time
from tools.moire_client import MoireTrackerClient

def test_connection():
    """Test 1: Basic connection"""
    print("\n" + "="*60)
    print("TEST 1: Connection")
    print("="*60)

    client = MoireTrackerClient()
    result = client.connect()

    if result:
        print("✓ Connection test PASSED")
        return client
    else:
        print("✗ Connection test FAILED")
        print("\nTroubleshooting:")
        print("1. Is MoireTracker.exe running?")
        print("2. Check: tasklist | findstr MoireTracker")
        print("3. Start it: cd C:\\Users\\User\\Desktop\\Moire\\build\\Release && MoireTracker.exe")
        sys.exit(1)

def test_mouse_position(client):
    """Test 2: Get mouse position"""
    print("\n" + "="*60)
    print("TEST 2: Get Mouse Position")
    print("="*60)

    pos = client.get_mouse_position()

    if pos:
        print(f"✓ Mouse position test PASSED")
        print(f"  Position: ({pos.x:.1f}, {pos.y:.1f})")
        print(f"  Confidence: {pos.confidence:.2f}")
        print(f"  Timestamp: {pos.timestamp_ms}")
    else:
        print("✗ Mouse position test FAILED")
        return False

    return True

def test_scan_desktop(client):
    """Test 3: Scan desktop elements"""
    print("\n" + "="*60)
    print("TEST 3: Scan Desktop Elements")
    print("="*60)

    print("Scanning... (this may take a few seconds)")
    elements = client.scan_desktop()

    if len(elements) > 0:
        print(f"✓ Desktop scan test PASSED")
        print(f"  Found {len(elements)} elements")
        print("\nFirst 5 elements:")
        for i, elem in enumerate(elements[:5]):
            print(f"  {i+1}. {elem.text:30s} ({elem.app_name:20s}) at ({elem.x:.0f}, {elem.y:.0f})")
        return True
    else:
        print("✗ Desktop scan test FAILED (0 elements)")
        return False

def test_find_element(client):
    """Test 4: Find specific element"""
    print("\n" + "="*60)
    print("TEST 4: Find Element")
    print("="*60)

    # Try to find common applications
    search_terms = ["Chrome", "VSCode", "Discord", "Notepad"]

    for term in search_terms:
        print(f"\nSearching for '{term}'...")
        elem = client.find_element(term, exact_match=False)

        if elem:
            print(f"  ✓ Found: {elem.text} at ({elem.x:.0f}, {elem.y:.0f})")
            print(f"    App: {elem.app_name}")
            print(f"    Confidence: {elem.confidence:.2f}")
            return True

    print("  ⚠ None of the test applications found")
    print("    (This is OK if you don't have them installed)")
    return True

def test_overlay_toggle(client):
    """Test 5: Visual feedback (overlay toggle)"""
    print("\n" + "="*60)
    print("TEST 5: Visual Feedback (Overlay Toggle)")
    print("="*60)

    print("Activating overlay... (watch for moiré pattern)")
    result1 = client.set_active()
    time.sleep(2)

    print("Deactivating overlay...")
    result2 = client.set_standby()

    if result1 and result2:
        print("✓ Overlay toggle test PASSED")
    else:
        print("✗ Overlay toggle test FAILED")

    return result1 and result2

def main():
    print("╔" + "═"*58 + "╗")
    print("║" + " "*10 + "MoireTracker IPC Bridge Test Suite" + " "*14 + "║")
    print("╚" + "═"*58 + "╝")

    # Run tests
    client = test_connection()

    test_results = []
    test_results.append(("Mouse Position", test_mouse_position(client)))
    test_results.append(("Desktop Scan", test_scan_desktop(client)))
    test_results.append(("Find Element", test_find_element(client)))
    test_results.append(("Overlay Toggle", test_overlay_toggle(client)))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)

    for name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:20s}: {status}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Ready for Phase 2.")
    else:
        print("\n⚠ Some tests failed. Please fix before continuing.")

    # Cleanup
    client.disconnect()

if __name__ == "__main__":
    main()
