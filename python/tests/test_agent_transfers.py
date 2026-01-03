#!/usr/bin/env python3
"""
Test Agent Transfer System

This script tests:
1. Environment variables for agent IDs
2. Transfer function execution
3. Agent switch signaling
4. ElevenLabs agent configuration verification
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env
def load_env():
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
        print(f"✓ Loaded .env from {env_path}")
    else:
        print(f"✗ .env not found at {env_path}")

load_env()

print("\n" + "=" * 60)
print("AGENT TRANSFER SYSTEM TEST")
print("=" * 60)

# =============================================================================
# TEST 1: Environment Variables
# =============================================================================
print("\n--- TEST 1: Environment Variables ---")

AGENT_IDS = {
    "AGENT_RACHEL": os.getenv("AGENT_RACHEL") or os.getenv("AGENT_CONVERSATIONAL_MEMORY"),
    "AGENT_ALICE": os.getenv("AGENT_ALICE") or os.getenv("AGENT_PROJECT_MANAGER"),
    "AGENT_ADAM": os.getenv("AGENT_ADAM") or os.getenv("AGENT_DESKTOP_WORKER"),
    "AGENT_ANTONI": os.getenv("AGENT_ANTONI") or os.getenv("AGENT_PROJECT_WRITER"),
    "AGENT_MULTIVERSE": os.getenv("AGENT_MULTIVERSE"),
}

all_present = True
for name, agent_id in AGENT_IDS.items():
    if agent_id:
        print(f"  ✓ {name}: {agent_id[:20]}...")
    else:
        print(f"  ✗ {name}: NOT SET")
        all_present = False

if all_present:
    print("\n  ✓ All agent IDs configured")
else:
    print("\n  ⚠ Some agent IDs missing - transfers may fail")

# =============================================================================
# TEST 2: Transfer Functions Import
# =============================================================================
print("\n--- TEST 2: Transfer Functions Import ---")

try:
    from tools.bubble_tools import (
        transfer_to_alice,
        transfer_to_adam,
        transfer_to_antoni,
        transfer_to_rachel,
        transfer_to_multiverse,
        get_pending_agent_switch,
        _signal_agent_switch,
    )
    print("  ✓ All transfer functions imported")
except ImportError as e:
    print(f"  ✗ Import failed: {e}")
    sys.exit(1)

# =============================================================================
# TEST 3: Transfer Function Execution (simulated)
# =============================================================================
print("\n--- TEST 3: Transfer Function Execution ---")

# Reset pending switch
from tools import bubble_tools
bubble_tools._pending_agent_switch = None

# Test transfer_to_alice
print("\n  Testing transfer_to_alice()...")
result = transfer_to_alice({"reason": "Test transfer"})
print(f"    Result: {result}")

switch_info = get_pending_agent_switch()
if switch_info:
    print(f"    ✓ Switch signal received: {switch_info['bubble_title']}")
    print(f"      Agent ID: {switch_info['agent_id'][:20]}...")
else:
    print("    ✗ No switch signal received")

# Test transfer_to_adam
print("\n  Testing transfer_to_adam()...")
result = transfer_to_adam({"reason": "Desktop task"})
print(f"    Result: {result}")

switch_info = get_pending_agent_switch()
if switch_info:
    print(f"    ✓ Switch signal received: {switch_info['bubble_title']}")
else:
    print("    ✗ No switch signal received")

# Test transfer_to_antoni
print("\n  Testing transfer_to_antoni()...")
result = transfer_to_antoni({"reason": "Coding task"})
print(f"    Result: {result}")

switch_info = get_pending_agent_switch()
if switch_info:
    print(f"    ✓ Switch signal received: {switch_info['bubble_title']}")
else:
    print("    ✗ No switch signal received")

# Test transfer_to_rachel
print("\n  Testing transfer_to_rachel()...")
result = transfer_to_rachel({"reason": "Creative task"})
print(f"    Result: {result}")

switch_info = get_pending_agent_switch()
if switch_info:
    print(f"    ✓ Switch signal received: {switch_info['bubble_title']}")
else:
    print("    ✗ No switch signal received")

# Test transfer_to_multiverse
print("\n  Testing transfer_to_multiverse()...")
result = transfer_to_multiverse({"reason": "Navigation"})
print(f"    Result: {result}")

switch_info = get_pending_agent_switch()
if switch_info:
    print(f"    ✓ Switch signal received: {switch_info['bubble_title']}")
else:
    print("    ✗ No switch signal received")

# =============================================================================
# TEST 4: ElevenLabs Agent Verification
# =============================================================================
print("\n--- TEST 4: ElevenLabs Agent Configuration ---")

import requests

API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not API_KEY:
    print("  ✗ ELEVENLABS_API_KEY not set - skipping verification")
else:
    print(f"  API Key: {API_KEY[:10]}...")
    
    # Check each agent
    for name, agent_id in AGENT_IDS.items():
        if not agent_id:
            continue
            
        try:
            url = f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}"
            headers = {"xi-api-key": API_KEY}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                agent_data = response.json()
                agent_name = agent_data.get("name", "Unknown")
                
                # Check for transfer tools
                prompt = agent_data.get("conversation_config", {}).get("agent", {}).get("prompt", {})
                tool_ids = prompt.get("tool_ids", [])
                tools = prompt.get("tools", [])
                
                # Count system transfer tools
                system_transfers = [t for t in tools if t.get("name") == "transfer_to_agent"]
                
                print(f"\n  {name}: {agent_name}")
                print(f"    Tool IDs: {len(tool_ids)}")
                print(f"    System transfers: {len(system_transfers)}")
                
                if system_transfers:
                    print(f"    ⚠ Has system transfer tools (should be 0)")
                else:
                    print(f"    ✓ No system transfer tools")
                    
            else:
                print(f"\n  {name}: ✗ API Error {response.status_code}")
                
        except Exception as e:
            print(f"\n  {name}: ✗ Error: {e}")

# =============================================================================
# TEST 5: List Client Transfer Tools at ElevenLabs
# =============================================================================
print("\n--- TEST 5: Client Transfer Tools at ElevenLabs ---")

if API_KEY:
    try:
        url = "https://api.elevenlabs.io/v1/convai/tools"
        headers = {"xi-api-key": API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            tools = response.json().get("tools", [])
            transfer_names = ["transfer_to_alice", "transfer_to_adam", "transfer_to_antoni", 
                             "transfer_to_rachel", "transfer_to_multiverse"]
            
            transfer_tools = []
            for tool in tools:
                config = tool.get("tool_config", {})
                name = config.get("name", "")
                if name in transfer_names:
                    transfer_tools.append({
                        "name": name,
                        "id": tool.get("id") or tool.get("tool_id"),
                        "type": config.get("type"),
                        "expects_response": config.get("expects_response")
                    })
            
            print(f"  Found {len(transfer_tools)} transfer tools:")
            for t in transfer_tools:
                expects = "✓" if t["expects_response"] else "✗"
                print(f"    - {t['name']} (type: {t['type']}, expects_response: {expects})")
                print(f"      ID: {t['id']}")
                
            if len(transfer_tools) < 5:
                print(f"\n  ⚠ Expected 5 transfer tools, found {len(transfer_tools)}")
                print("  Run: python deploy_client_transfers.py")
            else:
                print(f"\n  ✓ All transfer tools deployed")
                
    except Exception as e:
        print(f"  ✗ Error: {e}")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("""
Transfer Flow:
  1. Agent calls transfer_to_X client tool
  2. Python executes transfer_to_X() in bubble_tools.py
  3. _signal_agent_switch() sets _pending_agent_switch
  4. Watcher thread in voice_dialog_main.py detects switch
  5. Current session ends, new session starts with target agent
  6. UI receives 'agent_switching' event

Agent Network:
  Rachel (Ideas) ←→ Alice (Hub) ←→ Adam (Desktop)
          ↕              ↕
      Multiverse    Antoni (Coding)
""")

print("To test with voice:")
print("  1. Start Electron app: npm start (in electron-app/)")
print("  2. Click 'Start Voice'")
print("  3. Say: 'Transfer me to Alice'")
print("  4. Observe agent switch in transcript")
print("=" * 60)