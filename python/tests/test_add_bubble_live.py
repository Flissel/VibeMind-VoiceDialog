#!/usr/bin/env python3
"""
Test: Add a bubble to the live Electron app via CDP

This script connects to the running Electron app's DevTools
and executes JavaScript to add a new bubble.

Requirements:
- Electron must be running with --inspect=9222
- Start with: cd electron-app && node_modules\electron\dist\electron.exe --inspect=9222 .
"""

import asyncio
import json
import websockets
import requests
from datetime import datetime


def get_all_cdp_targets(port=9223):
    """Get all available CDP targets."""
    try:
        response = requests.get(f"http://localhost:{port}/json", timeout=5)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Could not get CDP targets: {e}")
        return []


def get_cdp_websocket_url(port=9223):
    """Get the WebSocket URL from Chrome DevTools endpoint."""
    targets = get_all_cdp_targets(port)
    
    print(f"[CDP] Found {len(targets)} targets:")
    for i, target in enumerate(targets):
        print(f"  [{i}] type={target.get('type')}, title={target.get('title', '')[:40]}")
    
    # Find a page target with actual content (not about:blank)
    for target in targets:
        if target.get("type") == "page":
            title = target.get("title", "")
            url = target.get("url", "")
            if "VibeMind" in title or "index.html" in url:
                print(f"[CDP] Selected: {title}")
                return target.get("webSocketDebuggerUrl")
    
    # Fallback: first page type
    for target in targets:
        if target.get("type") == "page":
            print(f"[CDP] Selected (fallback): {target.get('title', 'Unknown')}")
            return target.get("webSocketDebuggerUrl")
            
    return None


async def check_multiverse_app():
    """Check if multiverseApp is available in the renderer."""
    ws_url = get_cdp_websocket_url()
    
    if not ws_url:
        print("[ERROR] No renderer target found")
        return
    
    print(f"[CDP] Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Check what's available
            js_code = """
            (function() {
                const result = {
                    hasMultiverseApp: !!window.multiverseApp,
                    hasAddBubble: !!window.multiverseApp?.addBubble,
                    bubbleCount: window.multiverseApp?.bubbles?.length || 0,
                    methods: window.multiverseApp ? Object.keys(window.multiverseApp).filter(k => typeof window.multiverseApp[k] === 'function') : []
                };
                return JSON.stringify(result, null, 2);
            })()
            """
            
            message = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True
                }
            }
            
            await ws.send(json.dumps(message))
            response = await ws.recv()
            result = json.loads(response)
            
            print("[CDP] multiverseApp status:")
            if "result" in result and "result" in result["result"]:
                value = result["result"]["result"].get("value", "")
                print(value)
                return value
            else:
                print(f"  Error: {result}")
                
    except Exception as e:
        print(f"[ERROR] CDP check failed: {e}")


async def add_bubble_via_cdp(title: str = None):
    """Add a new bubble to the running Electron app via CDP."""
    
    if title is None:
        title = f"Test Bubble {datetime.now().strftime('%H:%M:%S')}"
    
    ws_url = get_cdp_websocket_url()
    
    if not ws_url:
        print("[ERROR] Could not connect to Electron DevTools")
        print("Make sure Electron is running with --inspect=9222")
        return False
    
    print(f"[CDP] Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            # JavaScript to add a bubble - with detailed error handling
            js_code = f"""
            (function() {{
                try {{
                    if (!window.multiverseApp) {{
                        return "ERROR: window.multiverseApp is undefined";
                    }}
                    if (!window.multiverseApp.addBubble) {{
                        return "ERROR: addBubble method not found. Available: " + Object.keys(window.multiverseApp).join(", ");
                    }}
                    
                    const angle = Math.random() * Math.PI * 2;
                    const radius = 2 + Math.random() * 2;
                    const bubbleData = {{
                        id: Date.now(),
                        title: "{title}",
                        color: {{
                            
                            r: 0.3 + Math.random() * 0.4, 
                            g: 0.5 + Math.random() * 0.3, 
                            b: 0.8 + Math.random() * 0.2 
                        }},
                        position: {{
                            
                            x: Math.cos(angle) * radius,
                            y: -0.5 + Math.random() * 1,
                            z: Math.sin(angle) * radius
                        }},
                        radius: 0.6 + Math.random() * 0.3
                    }};
                    
                    window.multiverseApp.addBubble(bubbleData);
                    return "SUCCESS: Added bubble '" + bubbleData.title + "' at position (" + bubbleData.position.x.toFixed(2) + ", " + bubbleData.position.y.toFixed(2) + ", " + bubbleData.position.z.toFixed(2) + ")";
                }} catch (e) {{
                    return "EXCEPTION: " + e.message;
                }}
            }})()
            """
            
            # Send CDP command to evaluate JavaScript
            message = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True
                }
            }
            
            await ws.send(json.dumps(message))
            response = await ws.recv()
            result = json.loads(response)
            
            # Check result
            if "result" in result and "result" in result["result"]:
                value = result["result"]["result"].get("value", "")
                print(f"[CDP] Result: {value}")
                return "SUCCESS" in str(value)
            elif "error" in result:
                print(f"[CDP] Error: {result['error']}")
            else:
                print(f"[CDP] Unexpected response: {json.dumps(result, indent=2)}")
            return False
                
    except Exception as e:
        print(f"[ERROR] CDP communication failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def simulate_python_message(message: dict):
    """
    Simulate a message from Python backend to Electron renderer.
    
    This is what happens when Python tools call _broadcast_to_electron()
    """
    ws_url = get_cdp_websocket_url()
    
    if not ws_url:
        print("[ERROR] Could not connect to Electron DevTools")
        return False
    
    print(f"[CDP] Simulating Python message: {message['type']}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            # JavaScript to handle the message as if it came from Python
            js_code = f"""
            (function() {{
                try {{
                    const message = {json.dumps(message)});
                    
                    if (message.type === 'bubble_created' && message.bubble) {{
                        if (!window.multiverseApp) {{
                            return "ERROR: window.multiverseApp not available";
                        }}
                        if (!window.multiverseApp.addBubble) {{
                            return "ERROR: addBubble method not found";
                        }}
                        
                        const b = message.bubble;
                        const angle = Math.random() * Math.PI * 2;
                        const radius = 2 + Math.random() * 2;
                        const bubbleData = {{
                            id: b.id,
                            title: b.title,
                            color: {{ r: 0.3 + Math.random() * 0.4, g: 0.5 + Math.random() * 0.3, b: 0.8 + Math.random() * 0.2 }},
                            position: {{
                                x: Math.cos(angle) * radius,
                                y: -0.5 + Math.random() * 1,
                                z: Math.sin(angle) * radius
                            }},
                            radius: 0.6 + Math.random() * 0.3
                        }};
                        window.multiverseApp.addBubble(bubbleData);
                        return "SUCCESS: Simulated bubble_created for '" + b.title + "'";
                    }}
                    
                    return "Message type not handled: " + message.type;
                }} catch (e) {{
                    return "EXCEPTION: " + e.message;
                }}
            }})()
            """
            
            message_cdp = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True
                }
            }
            
            await ws.send(json.dumps(message_cdp))
            response = await ws.recv()
            result = json.loads(response)
            
            if "result" in result and "result" in result["result"]:
                value = result["result"]["result"].get("value", "")
                print(f"[CDP] Result: {value}")
                return "SUCCESS" in str(value)
            
            return False
            
    except Exception as e:
        print(f"[ERROR] CDP communication failed: {e}")
        return False


async def main():
    """Run the test."""
    print("=" * 60)
    print("VibeMind Live Bubble Test")
    print("=" * 60)
    print()
    
    # First check what's available
    print("[CHECK] Inspecting multiverseApp...")
    await check_multiverse_app()
    print()
    
    # Test 1: Add bubble directly via JS
    print("[TEST 1] Adding bubble via direct JavaScript...")
    success1 = await add_bubble_via_cdp("Direct JS Bubble")
    print(f"Result: {'PASS' if success1 else 'FAIL'}")
    print()
    
    # Wait a bit
    await asyncio.sleep(1)
    
    # Test 2: Simulate Python message
    print("[TEST 2] Simulating Python bubble_created message...")
    success2 = await simulate_python_message({
        "type": "bubble_created",
        "bubble": {
            "id": int(datetime.now().timestamp() * 1000),
            "title": "Simulated Python Bubble",
            "score": 0,
            "description": "Created via simulated IPC"
        }
    })
    print(f"Result: {'PASS' if success2 else 'FAIL'}")
    print()
    
    print("=" * 60)
    if success1 or success2:
        print("Check the Electron window - you should see new bubbles!")
    else:
        print("Tests failed - check the error messages above.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())