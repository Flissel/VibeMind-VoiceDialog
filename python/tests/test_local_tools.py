#!/usr/bin/env python3
"""
Test Local Tools - Testet Python-Tools direkt
Zeigt was bei Electron IPC ankommen würde.

Verwendung:
    python test_local_tools.py
"""

import os
import sys
import json
from pathlib import Path

# Import tools after loading env
def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()

# Mock electron sender to capture IPC messages
_ipc_messages = []


def mock_electron_sender(message: dict):
    """Capture IPC messages that would go to Electron."""
    _ipc_messages.append(message)
    print(f"[IPC >>> Electron] {json.dumps(message, ensure_ascii=False)}")


# Set up mock sender BEFORE importing tools
try:
    from tools.workspace_tools import set_electron_sender
    set_electron_sender(mock_electron_sender)
    print("[OK] Mock Electron sender registered")
except ImportError as e:
    print(f"[WARN] Could not import workspace_tools: {e}")

# Import tool modules
try:
    from tools.bubble_tools import (
        list_bubbles, create_bubble, enter_bubble, exit_bubble,
        get_bubble_stats, delete_bubble, 
        transfer_to_alice, transfer_to_adam, transfer_to_antoni, transfer_to_rachel
    )
    print("[OK] Bubble tools imported")
except ImportError as e:
    print(f"[WARN] Could not import bubble_tools: {e}")

try:
    from tools.idea_tools import (
        list_ideas, create_idea, find_idea, update_idea, delete_idea,
        get_current_space
    )
    print("[OK] Idea tools imported")
except ImportError as e:
    print(f"[WARN] Could not import idea_tools: {e}")

try:
    from tools.memory_tools import make_memories, recall_about_user
    print("[OK] Memory tools imported")
except ImportError as e:
    print(f"[WARN] Could not import memory_tools: {e}")

# Import navigation tools
try:
    from tools.navigation_tools import (
        navigate_to_space, select_item, select_by_name,
        enter_selection, exit_view, get_current_view,
        set_electron_sender as set_nav_sender
    )
    # Connect navigation tools to mock sender
    set_nav_sender(mock_electron_sender)
    print("[OK] Navigation tools imported")
except ImportError as e:
    print(f"[WARN] Could not import navigation_tools: {e}")
    navigate_to_space = None
    select_item = None
    select_by_name = None
    enter_selection = None
    exit_view = None
    get_current_view = None


def test_tool(name: str, func, params: dict = None):
    """Test a single tool and show results."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    _ipc_messages.clear()
    
    try:
        if params:
            result = func(params)
        else:
            result = func({})
        
        print(f"\n[RESULT] {json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else result}")
        
        if _ipc_messages:
            print(f"\n[IPC MESSAGES SENT]: {len(_ipc_messages)}")
        else:
            print("\n[NO IPC MESSAGES]")
            
        return True, result
        
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def main():
    print("=" * 70)
    print("VibeMind Local Tools Test")
    print("=" * 70)
    print("\nDieses Script testet die Python-Tools direkt (ohne ElevenLabs API).")
    print("IPC-Nachrichten die an Electron gehen wuerden werden angezeigt.\n")
    
    results = []
    
    # Test bubble tools
    print("\n" + "="*70)
    print("BUBBLE TOOLS")
    print("="*70)
    
    # list_bubbles
    success, result = test_tool("list_bubbles", list_bubbles)
    results.append(("list_bubbles", success))
    
    # create_bubble
    success, result = test_tool(
        "create_bubble", 
        create_bubble, 
        {"title": "Test-Space", "description": "Ein Test-Space"}
    )
    results.append(("create_bubble", success))
    
    # enter_bubble
    success, result = test_tool(
        "enter_bubble",
        enter_bubble,
        {"bubble_name": "Test-Space"}
    )
    results.append(("enter_bubble", success))
    
    # exit_bubble
    success, result = test_tool("exit_bubble", exit_bubble)
    results.append(("exit_bubble", success))
    
    # Test idea tools
    print("\n" + "="*70)
    print("IDEA TOOLS")
    print("="*70)
    
    # list_ideas
    success, result = test_tool("list_ideas", list_ideas)
    results.append(("list_ideas", success))
    
    # create_idea
    success, result = test_tool(
        "create_idea",
        create_idea,
        {"title": "Test-Idee", "content": "Das ist eine Test-Idee", "type": "idea"}
    )
    results.append(("create_idea", success))
    
    # get_current_space
    success, result = test_tool("get_current_space", get_current_space)
    results.append(("get_current_space", success))
    
    # Test transfer tools
    print("\n" + "="*70)
    print("TRANSFER TOOLS")
    print("="*70)
    
    # transfer_to_alice
    success, result = test_tool(
        "transfer_to_alice",
        transfer_to_alice,
        {"reason": "Test transfer"}
    )
    results.append(("transfer_to_alice", success))
    
    # Test navigation tools
    print("\n" + "="*70)
    print("NAVIGATION TOOLS")
    print("="*70)
    
    if navigate_to_space:
        # navigate_to_space - Ideas
        success, result = test_tool(
            "navigate_to_space (ideas)",
            navigate_to_space,
            {"space": "ideas"}
        )
        results.append(("navigate_to_space (ideas)", success))
        
        # navigate_to_space - Projects
        success, result = test_tool(
            "navigate_to_space (projects)",
            navigate_to_space,
            {"space": "projects"}
        )
        results.append(("navigate_to_space (projects)", success))
        
        # navigate_to_space - Desktop
        success, result = test_tool(
            "navigate_to_space (desktop)",
            navigate_to_space,
            {"space": "desktop"}
        )
        results.append(("navigate_to_space (desktop)", success))
        
        # select_item - next
        success, result = test_tool(
            "select_item (next)",
            select_item,
            {"direction": "next"}
        )
        results.append(("select_item (next)", success))
        
        # select_item - previous
        success, result = test_tool(
            "select_item (previous)",
            select_item,
            {"direction": "previous"}
        )
        results.append(("select_item (previous)", success))
        
        # select_by_name
        success, result = test_tool(
            "select_by_name",
            select_by_name,
            {"name": "Test Bubble"}
        )
        results.append(("select_by_name", success))
        
        # enter_selection
        success, result = test_tool(
            "enter_selection",
            enter_selection,
            {}
        )
        results.append(("enter_selection", success))
        
        # exit_view
        success, result = test_tool(
            "exit_view",
            exit_view,
            {}
        )
        results.append(("exit_view", success))
        
        # get_current_view
        success, result = test_tool(
            "get_current_view",
            get_current_view,
            {}
        )
        results.append(("get_current_view", success))
    else:
        print("[SKIP] Navigation tools not available")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, s in results if s)
    failed = len(results) - passed
    
    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed}")
    
    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    if _ipc_messages:
        print(f"\nTotal IPC messages sent: {len(_ipc_messages)}")


if __name__ == "__main__":
    main()