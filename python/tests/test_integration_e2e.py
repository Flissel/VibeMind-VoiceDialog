#!/usr/bin/env python3
"""
End-to-End Integration Test für VibeMind

Testet das gesamte System:
1. Transfer-System (Agent-Wechsel)
2. MoireTracker Integration (Desktop Automation)
3. Tool-Registrierung
"""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_status(name, success):
    status = "✓ PASS" if success else "✗ FAIL"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"  {color}{status}{reset}: {name}")


def test_env_variables():
    """Test dass alle notwendigen ENV-Variablen existieren."""
    print_header("Test 1: Environment Variables")
    
    required_vars = [
        "ELEVENLABS_API_KEY",
        "AGENT_RACHEL",
        "AGENT_ALICE",
        "AGENT_ADAM",
        "AGENT_ANTONI",
        "AGENT_MULTIVERSE",
    ]
    
    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        status = "✓" if value else "✗"
        print(f"  {status} {var}: {value[:20] if value else 'NOT SET'}...")
        if not value:
            all_ok = False
    
    return all_ok


def test_transfer_system():
    """Test Transfer-Handler und Signal-Mechanismus."""
    print_header("Test 2: Transfer System")
    
    from tools.bubble_tools import (
        transfer_to_alice,
        transfer_to_adam,
        transfer_to_antoni,
        get_pending_agent_switch,
    )
    import tools.bubble_tools as bubble_tools
    
    tests = [
        ("transfer_to_alice", transfer_to_alice, "AGENT_ALICE"),
        ("transfer_to_adam", transfer_to_adam, "AGENT_ADAM"),
        ("transfer_to_antoni", transfer_to_antoni, "AGENT_ANTONI"),
    ]
    
    all_ok = True
    for name, handler, env_var in tests:
        bubble_tools._pending_agent_switch = None
        handler({"reason": f"Test {name}"})
        pending = get_pending_agent_switch()
        expected = os.getenv(env_var)
        
        if pending and pending.get('agent_id') == expected:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            all_ok = False
    
    return all_ok


def test_tools_registration():
    """Test dass alle Tools registriert werden können."""
    print_header("Test 3: Tools Registration")
    
    from tools.client_tools_manager import ClientToolsManager
    from tools.bubble_tools import register_bubble_tools
    
    try:
        manager = ClientToolsManager(enable_console_logging=False, enable_file_logging=False)
        register_bubble_tools(manager)
        
        registered = manager.list_registered_tools()
        
        required_tools = [
            "transfer_to_alice",
            "transfer_to_adam",
            "transfer_to_antoni",
        ]
        
        all_ok = True
        for tool in required_tools:
            if tool in registered:
                print(f"  ✓ {tool}")
            else:
                print(f"  ✗ {tool}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_desktop_tools_registration():
    """Test dass Desktop Tools registriert werden können."""
    print_header("Test 4: Desktop Tools Registration")
    
    try:
        from tools.client_tools_manager import ClientToolsManager
        from tools.desktop_tools import register_desktop_tools
        
        manager = ClientToolsManager(enable_console_logging=False, enable_file_logging=False)
        register_desktop_tools(manager)
        
        registered = manager.list_registered_tools()
        
        required_tools = [
            "execute_desktop_task",
            "press_key",
            "type_text",
            "take_screenshot",
        ]
        
        all_ok = True
        for tool in required_tools:
            if tool in registered:
                print(f"  ✓ {tool}")
            else:
                print(f"  ✗ {tool}")
                all_ok = False
        
        return all_ok
        
    except ImportError as e:
        print(f"  ⚠ Desktop tools not available: {e}")
        return True  # Optional - not a failure
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def test_moire_external():
    """Test MoireTracker v2 Bridge."""
    print_header("Test 5: MoireTracker v2 External")
    
    try:
        import moire_external as moire
        
        # Initialize
        print("  Initializing MoireTracker v2...")
        success = await moire.initialize()
        if not success:
            print("  ✗ Initialize failed")
            return False
        print("  ✓ Initialize")
        
        # Test press_key
        result = await moire.press_key("escape")
        if result.success:
            print("  ✓ press_key")
        else:
            print(f"  ✗ press_key: {result.error}")
            await moire.shutdown()
            return False
        
        # Test screenshot
        success, screenshot = await moire.take_screenshot()
        if success and screenshot:
            print(f"  ✓ take_screenshot ({len(screenshot)} bytes)")
        else:
            print("  ✗ take_screenshot")
            await moire.shutdown()
            return False
        
        # Shutdown
        await moire.shutdown()
        print("  ✓ shutdown")
        
        return True
        
    except ImportError as e:
        print(f"  ⚠ MoireTracker not available: {e}")
        return True  # Optional
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_voice_dialog_imports():
    """Test dass voice_dialog_main.py importierbar ist."""
    print_header("Test 6: Voice Dialog Imports")
    
    try:
        # Just test that imports work
        from tools.client_tools_manager import ClientToolsManager
        from tools.bubble_tools import register_bubble_tools, get_pending_agent_switch
        from tools.session_tools import register_session_tools
        
        print("  ✓ client_tools_manager")
        print("  ✓ bubble_tools")
        print("  ✓ session_tools")
        
        # Check desktop tools import
        try:
            from tools.desktop_tools import register_desktop_tools
            print("  ✓ desktop_tools")
        except ImportError:
            print("  ⚠ desktop_tools (optional)")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + "  VibeMind End-to-End Integration Test".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    results = []
    
    # Sync tests
    results.append(("Environment Variables", test_env_variables()))
    results.append(("Transfer System", test_transfer_system()))
    results.append(("Tools Registration", test_tools_registration()))
    results.append(("Desktop Tools Registration", test_desktop_tools_registration()))
    results.append(("Voice Dialog Imports", test_voice_dialog_imports()))
    
    # Async tests
    moire_result = await test_moire_external()
    results.append(("MoireTracker v2 External", moire_result))
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        print_status(name, ok)
    
    print()
    print(f"  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  \033[92m[SUCCESS]\033[0m All systems operational!")
        print()
        print("  Next steps:")
        print("  1. Deploy Desktop Tools: python deploy_desktop_tools.py")
        print("  2. Start Voice Dialog: python voice_dialog_main.py")
        print("  3. Test: 'Transfer to Adam' -> 'Open Explorer'")
    else:
        print("\n  \033[91m[WARNING]\033[0m Some tests failed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)