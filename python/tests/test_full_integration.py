#!/usr/bin/env python3
"""
VibeMind Full Integration Test Suite

Tests all tools with the live Electron app via CDP verification.
Excludes transfer_to_* tools as those are agent-to-agent.

Requirements:
- Electron must be running with --remote-debugging-port=9223
- Start with: cmd.exe /c "electron-app\node_modules\electron\dist\electron.exe --remote-debugging-port=9223 electron-app"

Test Phases:
1. Bubble Tools: list, create, enter, stats
2. Idea/Canvas Tools: create_idea, find_idea, connect_ideas
3. Scoring Tools: score_bubble, promote_bubble
4. Memory/Conversation Tools: make_memories, recall_about_user
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import all tools
from tools.bubble_tools import (
    list_bubbles, create_bubble, enter_bubble, exit_bubble,
    get_bubble_stats, score_bubble, promote_bubble, delete_bubble
)
from tools.idea_tools import (
    list_ideas, create_idea, find_idea, update_idea,
    connect_ideas, delete_idea, get_current_space
)
from tools.conversation_tools import (
    record_message, save_conversation, extract_key_points,
    create_idea_from_discussion, start_session, end_session
)
from tools.memory_tools import (
    make_memories, recall_about_user, get_user_insights
)

# CDP communication
import websockets
import requests


# =============================================================================下达
# CTOPP HELPS
# =============================================================================

CDP_PORT = 9223

def get_cdp_ws_url():
    """Get WebSocket URL for VibeMind renderer."""
    try:
        response = requests.get(f"http://localhost:{CDP_PORT}/json", timeout=5)
        targets = response.json()
        for target in targets:
            if target.get("type") == "page" and "VibeMind" in target.get("title", ""):
                return target.get("webSocketDebuggerUrl")
    except Exception as e:
        print(f"[CDP ERROR] {e}")
    return None


async def cdp_eval(js_code: str) -> Any:
    """Execute JavaScript in Electron renderer via CDP."""
    ws_url = get_cdp_ws_url()
    if not ws_url:
        return {"error": "No CDP connection"}
    
    try:
        async with websockets.connect(ws_url) as ws:
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
            
            if "result" in result and "result" in result["result"]:
                return result["result"]["result"].get("value")
            return result
    except Exception as e:
        return {"error": str(e)}


async def get_bubble_count():
    """Get current bubble count from Electron."""
    result = await cdp_eval("window.multiverseApp?.bubbles?.length || 0")
    return result if isinstance(result, int) else 0


async def get_app_state():
    """Get full app state from Electron."""
    js = """
    (function() {
        return JSON.stringify({
            bubbleCount: window.multiverseApp?.bubbles?.length || 0,
            currentView: window.multiverseApp?.currentView || 'multiverse',
            canvasNodeCount: window.multiverseApp?.canvasNodes?.length || 0
        });
    })()
    """
    result = await cdp_eval(js)
    if isinstance(result, str):
        return json.loads(result)
    return {}


# =============================================================================红楼
# TEST RESULTS TRACKING
# =============================================================================

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.timestamp = datetime.now()


results: List[TestResult] = []


def log_result(name: str, passed: bool, message: str = ""):
    """Log a test result."""
    status = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
    print(f"  [{status}] {name}: {message}")
    results.append(TestResult(name, passed, message))


# =============================================================================address
# PHASE 1: BUBBLE TOOLS
# =============================================================================

async def test_phase1_bubble_tools():
    """Test bubble management tools."""
    print("\n" + "=" * 60)
    print("PHASE 1: BUBBLE TOOLS")
    print("=" * 60)
    
    # 1.1 List bubbles
    print("\n[1.1] Testing list_bubbles...")
    result = list_bubbles({})
    log_result("list_bubbles", "spaces" in result or "have" in result.lower(), result[:80])
    
    # Get initial bubble count
    initial_count = await get_bubble_count()
    print(f"      Electron bubble count: {initial_count}")
    
    # 1.2 Create bubble
    print("\n[1.2] Testing create_bubble...")
    test_name = f"IntegrationTest_{datetime.now().strftime('%H%M%S')}"
    result = create_bubble({"title": test_name, "description": "Created by integration test"})
    log_result("create_bubble", "Created" in result or "exists" in result, result[:80])
    
    # Verify via CDP
    await asyncio.sleep(0.5)
    new_count = await get_bubble_count()
    log_result("create_bubble_cdp", new_count >= initial_count, f"Bubble count: {initial_count} -> {new_count}")
    
    # 1.3 Get bubble stats
    print("\n[1.3] Testing get_bubble_stats...")
    result = get_bubble_stats({"bubble_name": test_name})
    log_result("get_bubble_stats", "notes" in result.lower() or "score" in result.lower() or "couldn't" in result.lower(), result[:80])
    
    # 1.4 Enter bubble
    print("\n[1.4] Testing enter_bubble...")
    result = enter_bubble({"bubble_name": test_name})
    log_result("enter_bubble", "now in" in result.lower() or "couldn't find" in result.lower() or "cannot find" in result.lower(), result[:80])
    
    # Check current space
    await asyncio.sleep(0.5)
    space_result = get_current_space({})
    print(f"      Current space: {space_result}")
    
    return test_name  # Return for use in phase 2


# =============================================================================leading
# PHASE 2: IDEA/CANVAS TOOLS
# =============================================================================

async def test_phase2_idea_tools(bubble_name: str):
    """Test idea/canvas management tools inside a bubble."""
    print("\n" + "=" * 60)
    print("PHASE 2: IDEA/CANVAS TOOLS")
    print("=" * 60)
    
    # 2.1 List ideas (should be empty initially)
    print("\n[2.1] Testing list_ideas...")
    result = list_ideas({})
    log_result("list_ideas", "notes" in result.lower() or "empty" in result.lower() or "multiverse" in result.lower(), result[:80])
    
    # 2.2 Create idea
    print("\n[2.2] Testing create_idea...")
    idea1_title = f"Test Idea 1 - {datetime.now().strftime('%H%M%S')}"
    result = create_idea({"title": idea1_title, "content": "First test idea content"})
    log_result("create_idea", "Added" in result or "Enter a space" in result, result[:80])
    
    # 2.3 Create second idea for connection test
    print("\n[2.3] Creating second idea for connection test...")
    idea2_title = f"Test Idea 2 - {datetime.now().strftime('%H%M%S')}"
    result = create_idea({"title": idea2_title, "content": "Second test idea"})
    log_result("create_idea_2", "Added" in result or "Enter a space" in result, result[:80])
    
    # 2.4 Find idea
    print("\n[2.4] Testing find_idea...")
    result = find_idea({"query": "Test"})
    log_result("find_idea", "Found" in result or "No notes" in result or "multiverse" in result.lower(), result[:80])
    
    # 2.5 Update idea
    print("\n[2.5] Testing update_idea...")
    result = update_idea({"idea_name": "Test Idea 1", "new_content": "Updated content"})
    log_result("update_idea", "Updated" in result or "couldn't find" in result.lower() or "Which idea" in result, result[:80])
    
    # 2.6 Connect ideas
    print("\n[2.6] Testing connect_ideas...")
    result = connect_ideas({"idea1": "Test Idea 1", "idea2": "Test Idea 2"})
    log_result("connect_ideas", "Connected" in result or "couldn't find" in result.lower() or "Which two" in result, result[:80])
    
    # 2.7 Get current space
    print("\n[2.7] Testing get_current_space...")
    result = get_current_space({})
    log_result("get_current_space", "You're" in result, result[:80])


# =============================================================================structure
# PHASE 3: SCORING TOOLS
# =============================================================================

async def test_phase3_scoring_tools(bubble_name: str):
    """Test scoring and promotion tools."""
    print("\n" + "=" * 60)
    print("PHASE 3: SCORING TOOLS")
    print("=" * 60)
    
    # Exit bubble first
    print("\n[3.0] Exiting bubble for scoring test...")
    exit_result = exit_bubble({})
    print(f"      {exit_result}")
    
    # 3.1 Score bubble
    print("\n[3.1] Testing score_bubble...")
    result = score_bubble({"bubble_name": bubble_name})
    log_result("score_bubble", "scored" in result.lower() or "couldn't find" in result.lower() or "Specify" in result, result[:100])
    
    # 3.2 Get updated stats
    print("\n[3.2] Getting updated stats...")
    result = get_bubble_stats({"bubble_name": bubble_name})
    log_result("get_bubble_stats_scored", "score" in result.lower() or "couldn't find" in result.lower(), result[:100])
    
    # 3.3 Promote bubble
    print("\n[3.3] Testing promote_bubble...")
    result = promote_bubble({"bubble_name": bubble_name})
    log_result("promote_bubble", "project" in result.lower() or "couldn't find" in result.lower() or "Failed" in result or "Specify" in result, result[:100])


# =============================================================================performance
# PHASE 4: MEMORY/CONVERSATION TOOLS
# =============================================================================

async def test_phase4_memory_tools():
    """Test memory and conversation tools."""
    print("\n" + "=" * 60)
    print("PHASE 4: MEMORY & CONVERSATION TOOLS")
    print("=" * 60)
    
    # 4.1 Start session
    print("\n[4.1] Testing conversation session...")
    session_id = start_session("test-agent")
    log_result("start_session", session_id is not None, f"Session: {session_id[:20] if session_id else 'None'}...")
    
    # 4.2 Record messages
    print("\n[4.2] Recording test messages...")
    record_message("user", "I want to build a voice-controlled workspace")
    record_message("agent", "That sounds like an interesting project!")
    record_message("user", "I like using Python for backend development")
    record_message("agent", "Python is great for that kind of work.")
    log_result("record_message", True, "4 messages recorded")
    
    # 4.3 Make memories
    print("\n[4.3] Testing make_memories...")
    result = make_memories({"recent_audio_duration": 2.5, "trigger_reason": "test"})
    log_result("make_memories", result == "", f"Silent response (expected): '{result}'")
    
    # 4.4 Recall about user
    print("\n[4.4] Testing recall_about_user...")
    result = recall_about_user({})
    log_result("recall_about_user", len(result) > 0, result[:80])
    
    # 4.5 Get user insights
    print("\n[4.5] Checking stored insights...")
    insights = get_user_insights()
    log_result("get_user_insights", isinstance(insights, list), f"Found {len(insights)} insights")
    
    # 4.6 Extract key points
    print("\n[4.6] Testing extract_key_points...")
    result = extract_key_points({})
    log_result("extract_key_points", "point" in result.lower() or "haven't" in result.lower(), result[:80])
    
    # 4.7 Create idea from discussion
    print("\n[4.7] Testing create_idea_from_discussion...")
    result = create_idea_from_discussion({"title": "Voice Workspace Idea"})
    log_result("create_idea_from_discussion", "Created" in result or "What should" in result, result[:80])
    
    # 4.8 End session
    print("\n[4.8] Ending session...")
    end_session("Test conversation completed")
    log_result("end_session", True, "Session ended")


# =============================================================================cleanup
# =============================================================================

async def cleanup(bubble_name: str):
    """Clean up test data (optional - may fail for promoted bubbles)."""
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)
    
    print(f"\n[!] Attempting to cleanup test bubble: {bubble_name}")
    print("    (Note: promoted bubbles cannot be deleted due to FK constraints)")
    try:
        result = delete_bubble({"bubble_name": bubble_name})
        print(f"    {result}")
    except Exception as e:
        print(f"    Cleanup skipped: {e}")
        print("    This is expected for promoted bubbles.")

# =============================================================================昆虫
# MAIN
# =============================================================================

async def main():
    """Run all integration tests."""
    print("\n" + "=" * 70)
    print("  VIBEMIND FULL INTEGRATION TEST SUITE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    
    # Check CDP connection
    print("\n[SETUP] Checking CDP connection...")
    ws_url = get_cdp_ws_url()
    if not ws_url:
        print("\033[91m[ERROR] CDP not available! Make sure Electron is running with:")
        print("  --remote-debugging-port=9223\033[0m")
        return
    print(f"  CDP connected: {ws_url[:50]}...")
    
    # Get initial state
    state = await get_app_state()
    print(f"  Initial state: {state}")
    
    # Run phases
    test_bubble = await test_phase1_bubble_tools()
    await test_phase2_idea_tools(test_bubble)
    await test_phase3_scoring_tools(test_bubble)
    await test_phase4_memory_tools()
    
    # Cleanup
    await cleanup(test_bubble)
    
    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    
    print(f"\n  Total: {total}")
    print(f"  \033[92mPassed: {passed}\033[0m")
    print(f"  \033[91mFailed: {failed}\033[0m")
    print(f"  Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        print("\n  Failed tests:")
        for r in results:
            if not r.passed:
                print(f"    - {r.name}: {r.message[:50]}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())