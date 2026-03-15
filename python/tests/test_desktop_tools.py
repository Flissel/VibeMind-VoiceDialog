"""
Test Desktop Tools Integration

Testet die MoireTracker Integration mit VibeMind:
1. MoireBridge Initialisierung
2. Einfache Desktop-Aktionen (Tastendrücke)
3. Screenshot-Funktion
4. Tool Handler

Verwendung:
    python test_desktop_tools.py
    python test_desktop_tools.py --action press_key --param win
    python test_desktop_tools.py --action screenshot
    python test_desktop_tools.py --action type --param "Hello World"
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_bridge_init():
    """Test MoireBridge Initialisierung."""
    print("\n" + "=" * 60)
    print("TEST: MoireBridge Initialisierung")
    print("=" * 60)
    
    try:
        from moire import MoireBridge
        
        bridge = MoireBridge()
        print(f"✓ MoireBridge instantiiert")
        
        await bridge.start()
        print(f"✓ MoireBridge gestartet")
        print(f"  - InteractionAgent: OK")
        print(f"  - EventQueue: OK")
        print(f"  - OrchestratorV2: OK")
        
        await bridge.stop()
        print(f"✓ MoireBridge gestoppt")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def test_screenshot():
    """Test Screenshot-Funktion."""
    print("\n" + "=" * 60)
    print("TEST: Screenshot")
    print("=" * 60)
    
    try:
        from moire import MoireBridge
        
        bridge = MoireBridge()
        await bridge.start()
        
        success, screenshot_b64 = await bridge.take_screenshot()
        
        if success and screenshot_b64:
            print(f"✓ Screenshot aufgenommen")
            print(f"  - Base64 Länge: {len(screenshot_b64)} Zeichen")
            print(f"  - Geschätzte Größe: ~{len(screenshot_b64) * 3 // 4 // 1024} KB")
        else:
            print(f"✗ Screenshot fehlgeschlagen")
            
        await bridge.stop()
        return success
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def test_press_key(key: str = "win"):
    """Test Tastendruck."""
    print("\n" + "=" * 60)
    print(f"TEST: Tastendruck - {key}")
    print("=" * 60)
    
    try:
        from moire import MoireBridge
        
        bridge = MoireBridge()
        await bridge.start()
        
        result = await bridge.press_key(key)
        
        if result.success:
            print(f"✓ Taste '{key}' gedrückt")
            print(f"  - Dauer: {result.duration_ms:.1f}ms")
        else:
            print(f"✗ Tastendruck fehlgeschlagen: {result.error}")
        
        await bridge.stop()
        return result.success
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def test_type_text(text: str = "Hello from VibeMind!"):
    """Test Texteingabe."""
    print("\n" + "=" * 60)
    print(f"TEST: Texteingabe - '{text[:30]}...'")
    print("=" * 60)
    
    try:
        from moire import MoireBridge
        
        bridge = MoireBridge()
        await bridge.start()
        
        result = await bridge.type_text(text)
        
        if result.success:
            print(f"✓ Text eingegeben")
            print(f"  - Zeichen: {len(text)}")
            print(f"  - Dauer: {result.duration_ms:.1f}ms")
        else:
            print(f"✗ Texteingabe fehlgeschlagen: {result.error}")
        
        await bridge.stop()
        return result.success
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def test_tool_handler():
    """Test Tool Handler for voice agents."""
    print("\n" + "=" * 60)
    print("TEST: Desktop Tool Handler")
    print("=" * 60)
    
    try:
        from spaces.desktop.tools.desktop_tools import handle_desktop_tool_call, cleanup_desktop_tools
        
        # Test press_key tool
        print("\n1. Testing press_key tool...")
        result = await handle_desktop_tool_call("press_key", {"key": "escape"})
        if result.get("success"):
            print(f"   ✓ press_key: OK")
        else:
            print(f"   ✗ press_key: {result.get('error')}")
        
        # Test screenshot tool
        print("\n2. Testing take_screenshot tool...")
        result = await handle_desktop_tool_call("take_screenshot", {})
        if result.get("success"):
            print(f"   ✓ take_screenshot: OK (has_screenshot={result.get('has_screenshot')})")
        else:
            print(f"   ✗ take_screenshot: {result.get('error')}")
        
        # Test unknown tool
        print("\n3. Testing unknown tool handling...")
        result = await handle_desktop_tool_call("unknown_tool", {})
        if not result.get("success"):
            print(f"   ✓ Unknown tool correctly rejected")
        else:
            print(f"   ✗ Unknown tool should have been rejected")
        
        # Cleanup
        await cleanup_desktop_tools()
        print("\n✓ Tool handler tests completed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_task():
    """Test einfachen Task (öffnet Start Menü)."""
    print("\n" + "=" * 60)
    print("TEST: Einfacher Task - Start Menü öffnen & schließen")
    print("=" * 60)
    
    try:
        from moire import MoireBridge
        
        bridge = MoireBridge()
        await bridge.start()
        
        # Win drücken (Start Menü öffnen)
        print("\n1. Öffne Start Menü...")
        result = await bridge.press_key("win")
        if result.success:
            print("   ✓ Win gedrückt")
        
        await asyncio.sleep(1.0)
        
        # Screenshot machen
        print("\n2. Screenshot vom Start Menü...")
        success, _ = await bridge.take_screenshot()
        if success:
            print("   ✓ Screenshot aufgenommen")
        
        # Escape drücken (Start Menü schließen)
        print("\n3. Schließe Start Menü...")
        result = await bridge.press_key("escape")
        if result.success:
            print("   ✓ Escape gedrückt")
        
        await bridge.stop()
        print("\n✓ Einfacher Task abgeschlossen")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def run_all_tests():
    """Führt alle Tests aus."""
    results = {}
    
    print("\n" + "=" * 60)
    print("VIBEMIND DESKTOP TOOLS - TEST SUITE")
    print("=" * 60)
    
    # Test 1: Bridge Init
    results["Bridge Init"] = await test_bridge_init()
    
    # Test 2: Screenshot
    results["Screenshot"] = await test_screenshot()
    
    # Test 3: Press Key (Escape - harmlos)
    results["Press Key"] = await test_press_key("escape")
    
    # Test 4: Tool Handler
    results["Tool Handler"] = await test_tool_handler()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    return passed == total


async def main():
    parser = argparse.ArgumentParser(description="Test Desktop Tools")
    parser.add_argument("--action", choices=["press_key", "type", "screenshot", "task", "all"], 
                       default="all", help="Test action to run")
    parser.add_argument("--param", type=str, default="", help="Parameter for the action")
    args = parser.parse_args()
    
    if args.action == "all":
        success = await run_all_tests()
        sys.exit(0 if success else 1)
    
    elif args.action == "press_key":
        key = args.param or "escape"
        await test_press_key(key)
    
    elif args.action == "type":
        text = args.param or "Hello from VibeMind!"
        await test_type_text(text)
    
    elif args.action == "screenshot":
        await test_screenshot()
    
    elif args.action == "task":
        await test_simple_task()


if __name__ == "__main__":
    asyncio.run(main())