#!/usr/bin/env python3
"""
Test Script für das Agent-Transfer-System

Testet ob die Transfer-Handler korrekt funktionieren und
ob der pending_agent_switch korrekt gesetzt wird.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def test_env_variables():
    """Test dass alle Agent-IDs konfiguriert sind."""
    print("\n=== Test 1: Environment Variables ===")
    
    agents = {
        "AGENT_RACHEL": os.getenv("AGENT_RACHEL"),
        "AGENT_ALICE": os.getenv("AGENT_ALICE"),
        "AGENT_ADAM": os.getenv("AGENT_ADAM"),
        "AGENT_ANTONI": os.getenv("AGENT_ANTONI"),
        "AGENT_MULTIVERSE": os.getenv("AGENT_MULTIVERSE"),
    }
    
    all_ok = True
    for name, value in agents.items():
        status = "✓" if value else "✗"
        print(f"  {status} {name}: {value or 'NOT SET'}")
        if not value:
            all_ok = False
    
    return all_ok


def test_transfer_handlers():
    """Test dass alle Transfer-Handler existieren und aufrufbar sind."""
    print("\n=== Test 2: Transfer Handlers ===")
    
    from tools.bubble_tools import (
        transfer_to_alice,
        transfer_to_adam,
        transfer_to_antoni,
        transfer_to_rachel,
        transfer_to_multiverse,
        get_pending_agent_switch,
        _pending_agent_switch
    )
    
    handlers = {
        "transfer_to_alice": transfer_to_alice,
        "transfer_to_adam": transfer_to_adam,
        "transfer_to_antoni": transfer_to_antoni,
        "transfer_to_rachel": transfer_to_rachel,
        "transfer_to_multiverse": transfer_to_multiverse,
    }
    
    all_ok = True
    for name, handler in handlers.items():
        exists = callable(handler)
        status = "✓" if exists else "✗"
        print(f"  {status} {name}: {'callable' if exists else 'NOT CALLABLE'}")
        if not exists:
            all_ok = False
    
    return all_ok


def test_transfer_signal():
    """Test dass Transfer korrekt den pending_agent_switch setzt."""
    print("\n=== Test 3: Transfer Signal Mechanism ===")
    
    from tools.bubble_tools import (
        transfer_to_alice,
        get_pending_agent_switch,
    )
    import tools.bubble_tools as bubble_tools
    
    # Clear any pending switch
    bubble_tools._pending_agent_switch = None
    
    # Call transfer_to_alice
    print("  Calling transfer_to_alice...")
    result = transfer_to_alice({"reason": "Test transfer"})
    print(f"  Result: {result}")
    
    # Check pending switch
    pending = get_pending_agent_switch()
    
    if pending:
        print(f"  ✓ Pending switch detected:")
        print(f"    - agent_id: {pending.get('agent_id', 'N/A')}")
        print(f"    - bubble_id: {pending.get('bubble_id', 'N/A')}")
        print(f"    - bubble_title: {pending.get('bubble_title', 'N/A')}")
        
        expected_agent = os.getenv("AGENT_ALICE")
        if pending.get('agent_id') == expected_agent:
            print(f"  ✓ Agent ID matches AGENT_ALICE")
            return True
        else:
            print(f"  ✗ Agent ID mismatch! Expected: {expected_agent}")
            return False
    else:
        print("  ✗ No pending switch detected!")
        return False


def test_all_transfers():
    """Test alle Transfer-Handler und deren Signale."""
    print("\n=== Test 4: All Transfer Signals ===")
    
    from tools.bubble_tools import (
        transfer_to_alice,
        transfer_to_adam,
        transfer_to_antoni,
        transfer_to_rachel,
        transfer_to_multiverse,
        get_pending_agent_switch,
    )
    import tools.bubble_tools as bubble_tools
    
    tests = [
        ("transfer_to_alice", transfer_to_alice, "AGENT_ALICE"),
        ("transfer_to_adam", transfer_to_adam, "AGENT_ADAM"),
        ("transfer_to_antoni", transfer_to_antoni, "AGENT_ANTONI"),
        ("transfer_to_rachel", transfer_to_rachel, "AGENT_RACHEL"),
        ("transfer_to_multiverse", transfer_to_multiverse, "AGENT_MULTIVERSE"),
    ]
    
    all_ok = True
    for name, handler, env_var in tests:
        # Clear pending
        bubble_tools._pending_agent_switch = None
        
        # Call handler
        handler({"reason": f"Test {name}"})
        
        # Check signal
        pending = get_pending_agent_switch()
        expected_agent = os.getenv(env_var)
        
        if pending and pending.get('agent_id') == expected_agent:
            print(f"  ✓ {name} -> {pending.get('bubble_title')}")
        else:
            print(f"  ✗ {name} FAILED")
            all_ok = False
    
    return all_ok


def test_tools_registration():
    """Test dass Transfer-Tools korrekt registriert werden."""
    print("\n=== Test 5: Tools Registration ===")
    
    from tools.client_tools_manager import ClientToolsManager
    from tools.bubble_tools import register_bubble_tools
    
    # Create manager
    manager = ClientToolsManager(enable_console_logging=False, enable_file_logging=False)
    
    # Register bubble tools
    register_bubble_tools(manager)
    
    # Check registered tools
    registered = manager.list_registered_tools()
    
    transfer_tools = [
        "transfer_to_alice",
        "transfer_to_adam", 
        "transfer_to_antoni",
        "transfer_to_rachel",
        "transfer_to_multiverse",
    ]
    
    all_ok = True
    for tool in transfer_tools:
        if tool in registered:
            print(f"  ✓ {tool} registered")
        else:
            print(f"  ✗ {tool} NOT registered")
            all_ok = False
    
    return all_ok


def main():
    """Run all tests."""
    print("=" * 60)
    print("Agent Transfer System Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("ENV Variables", test_env_variables()))
    results.append(("Transfer Handlers", test_transfer_handlers()))
    results.append(("Transfer Signal", test_transfer_signal()))
    results.append(("All Transfers", test_all_transfers()))
    results.append(("Tools Registration", test_tools_registration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  [SUCCESS] Transfer system is correctly configured!")
    else:
        print("\n  [WARNING] Some tests failed - check configuration")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)