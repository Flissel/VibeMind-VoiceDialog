#!/usr/bin/env python3
"""Test State Sync between enter_bubble and create_idea"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.bubble_tools import get_current_bubble_db_id, enter_bubble, exit_bubble, list_bubbles, create_bubble
from tools.idea_tools import create_idea, _get_current_bubble_id

def test_state_sync():
    print("=== Test State Sync ===\n")
    
    # Test initial state
    db_id = get_current_bubble_db_id()
    print(f"1. Initial state: get_current_bubble_db_id() = {db_id}")
    assert db_id is None, "Should be None initially"
    print("   PASS: Initial state is None")
    
    # List existing bubbles
    bubbles = list_bubbles({})
    print(f"\n2. Existing bubbles: {bubbles}")
    
    # Create a test bubble if none exist
    if "no spaces" in bubbles.lower():
        print("\n3. Creating test bubble 'StateTest'...")
        result = create_bubble({"title": "StateTest", "description": "For testing"})
        print(f"   Result: {result}")
    
    # Try to enter a bubble - use existing one
    print("\n4. Entering 'Alice Workspace' bubble...")
    result = enter_bubble({"bubble_name": "Alice Workspace"})
    print(f"   Result: {result}")
    
    # Check state after enter
    db_id = get_current_bubble_db_id()
    idea_db_id = _get_current_bubble_id()
    print(f"\n5. After enter_bubble:")
    print(f"   - bubble_tools.get_current_bubble_db_id() = {db_id}")
    print(f"   - idea_tools._get_current_bubble_id() = {idea_db_id}")
    
    if db_id:
        print("   PASS: State was set correctly!")
        
        # Now test create_idea
        print("\n6. Testing create_idea...")
        result = create_idea({"title": "Test Note", "content": "Created via state sync test"})
        print(f"   Result: {result}")
        
        if "Enter a space first" in result:
            print("   FAIL: create_idea still thinks we're not in a bubble!")
        else:
            print("   PASS: create_idea worked correctly!")
    else:
        print("   FAIL: State was not set!")
    
    # Exit bubble
    print("\n7. Exiting bubble...")
    result = exit_bubble({})
    print(f"   Result: {result}")
    
    # Check state after exit
    db_id = get_current_bubble_db_id()
    print(f"\n8. After exit_bubble:")
    print(f"   - get_current_bubble_db_id() = {db_id}")
    
    if db_id is None:
        print("   PASS: State was cleared correctly!")
    else:
        print("   FAIL: State was not cleared!")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_state_sync()