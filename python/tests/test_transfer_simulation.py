#!/usr/bin/env python3
"""
VibeMind Agent Transfer Simulation Tests
=========================================

Simulates all 5 agents to test their Client Transfer Tools via ElevenLabs API.

Tests each agent's ability to:
1. Recognize transfer requests
2. Call the correct transfer_to_* tool
3. Pass correct parameters

Usage:
    python test_transfer_simulation.py           # All agents
    python test_transfer_simulation.py --quick   # One test per agent
    python test_transfer_simulation.py --agent rachel  # Single agent
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE = "https://api.elevenlabs.io/v1/convai"


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


def get_api_key() -> str:
    """Get ElevenLabs API key from environment."""
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set in .env")
    return key


def get_agent_ids() -> Dict[str, str]:
    """Get all agent IDs from environment."""
    return {
        "Rachel": os.getenv("AGENT_CONVERSATIONAL_MEMORY") or os.getenv("AGENT_RACHEL"),
        "Alice": os.getenv("AGENT_PROJECT_MANAGER") or os.getenv("AGENT_ALICE"),
        "Adam": os.getenv("AGENT_DESKTOP_WORKER") or os.getenv("AGENT_ADAM"),
        "Antoni": os.getenv("AGENT_PROJECT_WRITER") or os.getenv("AGENT_ANTONI"),
        "Multiverse": os.getenv("AGENT_MULTIVERSE"),
    }


# ============================================================================
# TRANSFER TEST SCENARIOS
# ============================================================================

# Each agent has transfer tools to specific targets
TRANSFER_TESTS = {
    "Rachel": {
        "agent_env": "AGENT_CONVERSATIONAL_MEMORY",
        "role": "Creative/Bubbles - Transfers to Alice or Multiverse",
        "tests": [
            {
                "name": "transfer_to_alice",
                "message": "Ich muss eine Aufgabe erledigen, verbinde mich mit Alice",
                "expected_tool": "transfer_to_alice"
            },
            {
                "name": "transfer_to_multiverse",  
                "message": "Bring mich zurueck zum Multiverse Navigator",
                "expected_tool": "transfer_to_multiverse"
            }
        ]
    },
    "Alice": {
        "agent_env": "AGENT_PROJECT_MANAGER",
        "role": "Coordinator Hub - Delegates to Adam, Antoni, Rachel",
        "tests": [
            {
                "name": "transfer_to_adam",
                "message": "Ich brauche Hilfe mit Desktop-Aufgaben, verbinde mich mit Adam",
                "expected_tool": "transfer_to_adam"
            },
            {
                "name": "transfer_to_antoni",
                "message": "Ich moechte Code schreiben, leite mich zu Antoni weiter",
                "expected_tool": "transfer_to_antoni"
            },
            {
                "name": "transfer_to_rachel",
                "message": "Ich will kreativ brainstormen, verbinde mich mit Rachel",
                "expected_tool": "transfer_to_rachel"
            }
        ]
    },
    "Adam": {
        "agent_env": "AGENT_DESKTOP_WORKER",
        "role": "Desktop Worker - Returns to Alice",
        "tests": [
            {
                "name": "transfer_to_alice",
                "message": "Ich bin fertig hier, verbinde mich wieder mit Alice",
                "expected_tool": "transfer_to_alice"
            }
        ]
    },
    "Antoni": {
        "agent_env": "AGENT_PROJECT_WRITER",
        "role": "Coding Worker - Returns to Alice",
        "tests": [
            {
                "name": "transfer_to_alice",
                "message": "Die Aufgabe ist erledigt, zurueck zu Alice bitte",
                "expected_tool": "transfer_to_alice"
            }
        ]
    },
    "Multiverse": {
        "agent_env": "AGENT_MULTIVERSE",
        "role": "Navigation - Transfers to Rachel or Alice",
        "tests": [
            {
                "name": "transfer_to_rachel",
                "message": "Ich moechte mit Rachel sprechen",
                "expected_tool": "transfer_to_rachel"
            },
            {
                "name": "transfer_to_alice",
                "message": "Ich brauche Alice fuer eine Aufgabe",
                "expected_tool": "transfer_to_alice"
            }
        ]
    }
}


# ============================================================================
# API FUNCTIONS
# ============================================================================

def simulate_conversation(
    api_key: str,
    agent_id: str,
    first_message: str,
    tool_mock_config: Optional[Dict[str, str]] = None,
    new_turns_limit: int = 3,
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Run a simulated conversation with an agent.
    
    POST /v1/convai/agents/{agent_id}/simulate-conversation
    """
    url = f"{API_BASE}/agents/{agent_id}/simulate-conversation"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Build tool mock config
    tool_mocks = {}
    if tool_mock_config:
        for tool_name, result in tool_mock_config.items():
            tool_mocks[tool_name] = {"result_value": result}
    
    payload = {
        "simulation_specification": {
            "simulated_user_config": {
                "first_message": first_message,
                "language": "de"
            },
            "new_turns_limit": new_turns_limit
        }
    }
    
    # Add tool mocks if provided
    if tool_mocks:
        payload["simulation_specification"]["tool_mock_config"] = tool_mocks
    
    # Retry logic
    for attempt in range(max_retries + 1):
        try:
            timeout = 90 + (attempt * 30)
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            
            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "simulated_conversation": [],
                    "analysis": {}
                }
            
            return response.json()
            
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                print(f"        Timeout, retry {attempt + 1}/{max_retries}...")
                time.sleep(3)
                continue
            return {
                "error": f"Timeout after {max_retries + 1} attempts",
                "simulated_conversation": [],
                "analysis": {}
            }
        except Exception as e:
            return {
                "error": str(e),
                "simulated_conversation": [],
                "analysis": {}
            }
    
    return {"error": "Unknown", "simulated_conversation": [], "analysis": {}}


def extract_tool_calls(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool calls from simulation response."""
    tool_calls = []
    
    conversation = response.get("simulated_conversation", [])
    for turn in conversation:
        calls = turn.get("tool_calls", [])
        for call in calls:
            tool_calls.append({
                "name": call.get("tool_name"),
                "params": call.get("params", {})
            })
    
    return tool_calls


# ============================================================================
# TEST RUNNER
# ============================================================================

@dataclass
class TestResult:
    agent: str
    test_name: str
    expected_tool: str
    success: bool
    tool_calls: List[Dict]
    error: Optional[str] = None
    duration_ms: int = 0


def run_single_test(
    api_key: str,
    agent_name: str,
    agent_id: str,
    test_config: Dict
) -> TestResult:
    """Run a single transfer test."""
    
    test_name = test_config["name"]
    expected_tool = test_config["expected_tool"]
    message = test_config["message"]
    
    # Mock the expected tool to succeed
    tool_mocks = {
        expected_tool: json.dumps({
            "success": True,
            "message": f"Transfer initiated to {expected_tool.replace('transfer_to_', '')}"
        })
    }
    
    start = time.time()
    
    response = simulate_conversation(
        api_key=api_key,
        agent_id=agent_id,
        first_message=message,
        tool_mock_config=tool_mocks,
        new_turns_limit=3
    )
    
    duration = int((time.time() - start) * 1000)
    
    if "error" in response and response.get("simulated_conversation") == []:
        return TestResult(
            agent=agent_name,
            test_name=test_name,
            expected_tool=expected_tool,
            success=False,
            tool_calls=[],
            error=response["error"],
            duration_ms=duration
        )
    
    tool_calls = extract_tool_calls(response)
    tool_names = [tc["name"] for tc in tool_calls]
    
    success = expected_tool in tool_names
    
    return TestResult(
        agent=agent_name,
        test_name=test_name,
        expected_tool=expected_tool,
        success=success,
        tool_calls=tool_calls,
        duration_ms=duration
    )


def run_all_tests(
    api_key: str,
    agents: Dict[str, str],
    agent_filter: Optional[str] = None,
    quick_mode: bool = False
) -> List[TestResult]:
    """Run all transfer tests."""
    
    results = []
    
    for agent_name, config in TRANSFER_TESTS.items():
        # Filter by agent if specified
        if agent_filter and agent_name.lower() != agent_filter.lower():
            continue
        
        agent_id = agents.get(agent_name)
        if not agent_id:
            print(f"\n[SKIP] {agent_name}: No agent ID configured")
            continue
        
        print(f"\n{'='*60}")
        print(f"{agent_name}")
        print(f"  Role: {config['role']}")
        print(f"  Agent ID: {agent_id[:25]}...")
        print('='*60)
        
        tests = config["tests"]
        if quick_mode:
            tests = tests[:1]  # Only first test per agent
        
        for test in tests:
            print(f"\n  Testing: {test['name']}")
            print(f"    Message: \"{test['message'][:50]}...\"")
            
            result = run_single_test(api_key, agent_name, agent_id, test)
            results.append(result)
            
            if result.success:
                print(f"    ✅ PASS - Tool '{result.expected_tool}' called ({result.duration_ms}ms)")
            else:
                print(f"    ❌ FAIL - Expected '{result.expected_tool}'")
                if result.error:
                    print(f"       Error: {result.error[:80]}")
                if result.tool_calls:
                    actual = [tc["name"] for tc in result.tool_calls]
                    print(f"       Actual calls: {actual}")
                else:
                    print("       No tool calls made")
            
            # Rate limiting
            time.sleep(1)
    
    return results


def print_summary(results: List[TestResult]):
    """Print test summary."""
    
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed
    
    print(f"\n{'='*60}")
    print("TRANSFER TESTS SUMMARY")
    print('='*60)
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
    
    # Group by agent
    print("\nBy Agent:")
    agents = {}
    for r in results:
        if r.agent not in agents:
            agents[r.agent] = {"passed": 0, "failed": 0}
        if r.success:
            agents[r.agent]["passed"] += 1
        else:
            agents[r.agent]["failed"] += 1
    
    for agent, stats in agents.items():
        total_agent = stats["passed"] + stats["failed"]
        status = "✅" if stats["failed"] == 0 else "❌"
        print(f"  {status} {agent}: {stats['passed']}/{total_agent}")
    
    # List failures
    if failed > 0:
        print("\nFailed Tests:")
        for r in results:
            if not r.success:
                print(f"  - {r.agent}/{r.test_name}: {r.error or 'Tool not called'}")
    
    print()
    return failed == 0


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="VibeMind Transfer Tools Simulation")
    parser.add_argument("--agent", "-a", help="Test only specific agent")
    parser.add_argument("--quick", "-q", action="store_true", help="One test per agent")
    parser.add_argument("--list", "-l", action="store_true", help="List all tests")
    args = parser.parse_args()
    
    # Load env
    load_env()
    
    # List mode
    if args.list:
        print("VibeMind Transfer Tests")
        print("=" * 60)
        for agent, config in TRANSFER_TESTS.items():
            print(f"\n{agent} ({config['role']})")
            for test in config["tests"]:
                print(f"  - {test['name']}: \"{test['message'][:40]}...\"")
        return
    
    # Get config
    try:
        api_key = get_api_key()
        agents = get_agent_ids()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("=" * 60)
    print("VibeMind Agent Transfer Simulation Tests")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Key: {api_key[:15]}...")
    print(f"Mode: {'Quick' if args.quick else 'Full'}")
    
    # Run tests
    results = run_all_tests(
        api_key=api_key,
        agents=agents,
        agent_filter=args.agent,
        quick_mode=args.quick
    )
    
    # Summary
    all_passed = print_summary(results)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()