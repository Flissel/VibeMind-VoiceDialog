#!/usr/bin/env python3
"""
Test Bubble Layout and Numbering
Tests collision detection and numbered title generation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from electron_backend import ElectronBackend

def test_collision_detection():
    """Test collision detection between bubbles."""
    backend = ElectronBackend()

    # Add some test bubbles
    bubble1 = backend.add_bubble("Test Bubble 1", {"x": 0, "y": 0, "z": 0}, 0x4488ff, 0.7)
    bubble2 = backend.add_bubble("Test Bubble 2", {"x": 2.5, "y": 0, "z": 0}, 0xff66aa, 0.7)  # Moved further apart

    # Test collision detection
    collision_close = backend._check_collision({"x": 0.5, "y": 0, "z": 0})  # Should collide with bubble1
    collision_far = backend._check_collision({"x": 5.0, "y": 0, "z": 0})   # Should not collide

    print("Collision Detection Test:")
    print(f"  Bubble1 at (0, 0, 0), Bubble2 at (2.5, 0, 0)")
    print(f"  Close position (0.5, 0, 0): {'COLLIDES' if collision_close else 'FREE'}")
    print(f"  Far position (5.0, 0, 0): {'COLLIDES' if collision_far else 'FREE'}")

    return collision_close and not collision_far

def test_numbered_titles():
    """Test numbered title generation."""
    backend = ElectronBackend()

    # Add test bubbles
    backend.add_bubble("Universe A", {"x": 0, "y": 0, "z": 0})
    backend.add_bubble("Universe B", {"x": 2, "y": 0, "z": 0})
    backend.add_bubble("Universe C", {"x": -2, "y": 0, "z": 0})

    # Get all bubbles
    bubbles = backend.get_all_bubbles()

    print("\nNumbered Titles Test:")
    for bubble in bubbles:
        print(f"  {bubble['numbered_title']}")

    # Check if titles are properly numbered
    expected_titles = ["1. Universe A", "2. Universe B", "3. Universe C"]
    actual_titles = [b['numbered_title'] for b in bubbles]

    success = actual_titles == expected_titles
    print(f"  Expected: {expected_titles}")
    print(f"  Actual: {actual_titles}")
    print(f"  Result: {'PASS' if success else 'FAIL'}")

    return success

def test_position_finding():
    """Test the _find_free_position method."""
    backend = ElectronBackend()

    # Add a bubble at origin
    backend.add_bubble("Center Bubble", {"x": 0, "y": 0, "z": 0})

    # Try to find a free position near the center
    free_pos = backend._find_free_position(0, 1.0)

    print("\nPosition Finding Test:")
    print(f"  Center bubble at (0, 0, 0)")
    print(f"  Found free position: ({free_pos['x']:.2f}, {free_pos['y']:.2f}, {free_pos['z']:.2f})")

    # Check if the found position is actually free
    is_free = not backend._check_collision(free_pos)
    print(f"  Position is free: {'YES' if is_free else 'NO'}")

    return is_free

def main():
    """Run all tests."""
    print("=" * 50)
    print("BUBBLE LAYOUT AND NUMBERING TESTS")
    print("=" * 50)

    tests = [
        ("Collision Detection", test_collision_detection),
        ("Numbered Titles", test_numbered_titles),
        ("Position Finding", test_position_finding),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            result = test_func()
            status = "PASS" if result else "FAIL"
            print(f"\n{status}: {test_name}")
            if result:
                passed += 1
        except Exception as e:
            print(f"\nERROR: {test_name} - {e}")

    print("\n" + "=" * 50)
    print(f"SUMMARY: {passed}/{total} tests passed")

    if passed == total:
        print("All bubble layout tests PASSED!")
        return True
    else:
        print("Some bubble layout tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)