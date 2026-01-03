#!/usr/bin/env python3
"""
VibeMind Agent Simulation Tests
================================
Testet alle Agents und ihre Tools via ElevenLabs Simulate-Conversation API.

Verwendet POST /v1/convai/agents/{agent_id}/simulate-conversation um:
- Tool-Aufrufe zu validieren
- Agent-Verhalten zu testen
- Transfer-Flows zu prüfen

Verwendung:
    python test_agent_simulation.py              # Alle Tests
    python test_agent_simulation.py --agent rachel  # Nur Rachel testen
    python test_agent_simulation.py --verbose    # Mit Details
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
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


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class AgentConfig:
    """Agent configuration for testing."""
    name: str
    env_var: str
    role: str
    expected_tools: List[str]
    test_scenarios: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of a single test."""
    agent_name: str
    scenario_name: str
    success: bool
    tool_calls: List[str]
    expected_tools: List[str]
    conversation_turns: int
    error: Optional[str] = None
    analysis: Optional[Dict] = None
    duration_ms: int = 0


# ============================================================================
# AGENT DEFINITIONS
# ============================================================================

AGENTS = {
    "rachel": AgentConfig(
        name="Rachel",
        env_var="AGENT_RACHEL",
        role="Multiverse Navigator - Creative brainstorming, ideas, bubble management",
        expected_tools=[
            "list_bubbles",
            "create_bubble",
            "get_bubble_stats",
            "list_ideas",
            "create_idea",
            "find_idea",
            # Summary Tools
            "generate_white_paper",
            "summarize_idea",
            "get_summary",
            "list_summaries"
        ],
        test_scenarios=[
            {
                "name": "list_bubbles",
                "description": "User fragt nach Spaces/Bubbles",
                "first_message": "Zeig mir meine Spaces",
                "expected_tool": "list_bubbles",
                "mock_result": '{"bubbles": [{"id": 1, "title": "Creative Space"}, {"id": 2, "title": "Research Hub"}]}'
            },
            {
                "name": "create_bubble",
                "description": "User will einen neuen Space erstellen",
                "first_message": "Erstelle einen Space fuer meine Kochrezepte",
                "expected_tool": "create_bubble",
                "mock_result": '{"success": true, "bubble_id": 3, "title": "Kochrezepte"}'
            },
            {
                "name": "create_idea",
                "description": "User will eine Idee speichern",
                "first_message": "Merke dir: Die beste Pizza hat duennen Teig",
                "expected_tool": "create_idea",
                "mock_result": '{"success": true, "idea_id": 1, "title": "Pizza-Idee"}'
            },
            {
                "name": "find_idea",
                "description": "User sucht eine Idee",
                "first_message": "Finde meine Ideen ueber Pizza",
                "expected_tool": "find_idea",
                "mock_result": '{"ideas": [{"id": 1, "title": "Pizza-Idee", "content": "Duenner Teig"}]}'
            },
            {
                "name": "generate_white_paper",
                "description": "User will ein White Paper generieren",
                "first_message": "Erstelle ein White Paper ueber Machine Learning basierend auf meinen Ideen",
                "expected_tool": "generate_white_paper",
                "mock_result": '{"success": true, "title": "White Paper: Machine Learning", "content": "# Machine Learning\\n\\n## Introduction..."}'
            },
            {
                "name": "summarize_idea",
                "description": "User will eine Idee zusammenfassen",
                "first_message": "Fasse meine Idee ueber Machine Learning zusammen",
                "expected_tool": "summarize_idea",
                "mock_result": '{"success": true, "summary": "Machine Learning ist ein Teilgebiet der KI..."}'
            },
            {
                "name": "list_summaries",
                "description": "User fragt nach existierenden Zusammenfassungen",
                "first_message": "Zeig mir alle meine Zusammenfassungen",
                "expected_tool": "list_summaries",
                "mock_result": '{"summaries": [{"id": 1, "title": "ML Summary"}]}'
            }
        ]
    ),
    "alice": AgentConfig(
        name="Alice",
        env_var="AGENT_ALICE",
        role="Coordinator Hub - Delegiert zu Adam (Desktop) und Antoni (Coding)",
        expected_tools=[],
        test_scenarios=[]  # Keine Tests - Alice ist nur Vermittler
    ),
    "adam": AgentConfig(
        name="Adam",
        env_var="AGENT_ADAM",
        role="Desktop Worker - Desktop operations with Moire OCR",
        expected_tools=[
            "moire_scan",
            "moire_find_element",
            "moire_get_ui_context",
            "click_element",
            "type_text",
            "open_application",
            "get_window_info",
            "scan_desktop",
            "transfer_to_alice"
        ],
        test_scenarios=[
            {
                "name": "moire_scan",
                "description": "User wants to scan desktop",
                "first_message": "Scan my desktop",
                "expected_tool": "moire_scan",
                "mock_result": '{"success": true, "texts": ["Start", "Chrome", "VSCode"], "element_count": 15}'
            },
            {
                "name": "moire_find_element",
                "description": "User wants to find a button",
                "first_message": "Find the Start button",
                "expected_tool": "moire_find_element",
                "mock_result": '{"success": true, "found": true, "x": 50, "y": 1050, "text": "Start"}'
            },
            {
                "name": "moire_get_ui_context",
                "description": "User wants to see all UI elements",
                "first_message": "What UI elements are on the screen?",
                "expected_tool": "moire_get_ui_context",
                "mock_result": '{"success": true, "total_elements": 25, "by_category": {"button": 5, "text": 15}}'
            },
            {
                "name": "click_element",
                "description": "User wants to click at coordinates",
                "first_message": "Click at position 100, 200",
                "expected_tool": "click_element",
                "mock_result": '{"success": true, "clicked_at": {"x": 100, "y": 200}}'
            },
            {
                "name": "open_application",
                "description": "User wants to open an app",
                "first_message": "Open Chrome",
                "expected_tool": "open_application",
                "mock_result": '{"success": true, "app": "Chrome", "status": "opened"}'
            }
        ]
    ),
    "antoni": AgentConfig(
        name="Antoni",
        env_var="AGENT_ANTONI",
        role="Code/Writer Worker - Programmierung und Textkomposition",
        expected_tools=[
            "write_hello_writer"
        ],
        test_scenarios=[
            {
                "name": "write_hello_writer",
                "description": "User will Code schreiben",
                "first_message": "Schreib mir ein Hello World Programm",
                "expected_tool": "write_hello_writer",
                "mock_result": '{"success": true, "code": "print(hello world)"}'
            }
        ]
    )
}


# ============================================================================
# API FUNCTIONS
# ============================================================================

def simulate_conversation(
    api_key: str,
    agent_id: str,
    first_message: str,
    tool_mock_config: Optional[Dict[str, str]] = None,
    new_turns_limit: int = 5,
    language: str = "en",
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
                "language": language
            },
            "new_turns_limit": new_turns_limit
        }
    }
    
    # Add tool mocks if provided
    if tool_mocks:
        payload["simulation_specification"]["tool_mock_config"] = tool_mocks
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries + 1):
        try:
            timeout = 120 + (attempt * 30)  # Increase timeout with each retry
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            
            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "simulated_conversation": [],
                    "analysis": {}
                }
            
            return response.json()
            
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait_time = 5 * (attempt + 1)
                print(f"      Timeout, retry {attempt + 1}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
                continue
            return {
                "error": f"Timeout after {max_retries + 1} attempts",
                "simulated_conversation": [],
                "analysis": {}
            }
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Request error: {str(e)}",
                "simulated_conversation": [],
                "analysis": {}
            }
    
    return {
        "error": "Unknown error",
        "simulated_conversation": [],
        "analysis": {}
    }


def extract_tool_calls(response: Dict[str, Any]) -> List[str]:
    """Extract tool names from simulation response."""
    tool_names = []
    
    conversation = response.get("simulated_conversation", [])
    for turn in conversation:
        tool_calls = turn.get("tool_calls", [])
        for call in tool_calls:
            tool_name = call.get("tool_name")
            if tool_name:
                tool_names.append(tool_name)
    
    return tool_names


# ============================================================================

# ============================================================================

def run_agent_test(
    api_key: str,
    agent_config: AgentConfig,
    scenario: Dict[str, Any],
    verbose: bool = False
) -> TestResult:
    """Run a single test scenario for an agent."""
    
    agent_id = os.getenv(agent_config.env_var)
    if not agent_id:
        return TestResult(
            agent_name=agent_config.name,
            scenario_name=scenario["name"],
            success=False,
            tool_calls=[],
            expected_tools=[scenario["expected_tool"]],
            conversation_turns=0,
            error=f"Agent ID not found: {agent_config.env_var}"
        )
    
    # Prepare tool mocks
    tool_mocks = {scenario["expected_tool"]: scenario["mock_result"]}
    
    # Also mock other expected tools to avoid errors
    for tool in agent_config.expected_tools:
        if tool not in tool_mocks:
            tool_mocks[tool] = '{"mocked": true}'
    
    start_time = time.time()
    
    try:
        response = simulate_conversation(
            api_key=api_key,
            agent_id=agent_id,
            first_message=scenario["first_message"],
            tool_mock_config=tool_mocks,
            new_turns_limit=5
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if "error" in response and response.get("simulated_conversation") == []:
            return TestResult(
                agent_name=agent_config.name,
                scenario_name=scenario["name"],
                success=False,
                tool_calls=[],
                expected_tools=[scenario["expected_tool"]],
                conversation_turns=0,
                error=response["error"],
                duration_ms=duration_ms
            )
        
        tool_calls = extract_tool_calls(response)
        conversation_turns = len(response.get("simulated_conversation", []))
        analysis = response.get("analysis", {})
        
        # Check if expected tool was called
        expected_tool = scenario["expected_tool"]
        success = expected_tool in tool_calls
        
        if verbose:
            print(f"\n    Response conversation ({conversation_turns} turns):")
            for turn in response.get("simulated_conversation", [])[:3]:
                role = turn.get("role", "?")
                msg = turn.get("message", "")[:80]
                print(f"      [{role}] {msg}...")
            print(f"    Tool calls: {tool_calls}")
        
        return TestResult(
            agent_name=agent_config.name,
            scenario_name=scenario["name"],
            success=success,
            tool_calls=tool_calls,
            expected_tools=[expected_tool],
            conversation_turns=conversation_turns,
            analysis=analysis,
            duration_ms=duration_ms
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return TestResult(
            agent_name=agent_config.name,
            scenario_name=scenario["name"],
            success=False,
            tool_calls=[],
            expected_tools=[scenario["expected_tool"]],
            conversation_turns=0,
            error=str(e),
            duration_ms=duration_ms
        )


def run_all_tests(
    api_key: str,
    agents_to_test: Optional[List[str]] = None,
    verbose: bool = False
) -> List[TestResult]:
    """Run all test scenarios for specified agents."""
    
    results = []
    
    agents = AGENTS
    if agents_to_test:
        agents = {k: v for k, v in AGENTS.items() if k in agents_to_test}
    
    for agent_key, agent_config in agents.items():
        print(f"\n{'='*60}")
        print(f"Testing: {agent_config.name} ({agent_config.role})")
        print(f"{'='*60}")
        
        agent_id = os.getenv(agent_config.env_var)
        if not agent_id:
            print(f"  [SKIP] {agent_config.env_var} not set")
            continue
        
        print(f"  Agent ID: {agent_id}")
        print(f"  Expected tools: {', '.join(agent_config.expected_tools)}")
        
        for scenario in agent_config.test_scenarios:
            print(f"\n  Test: {scenario['name']}")
            print(f"    Description: {scenario['description']}")
            print(f"    Message: \"{scenario['first_message']}\"")
            
            result = run_agent_test(api_key, agent_config, scenario, verbose)
            results.append(result)
            
            if result.success:
                print(f"    [PASS] Tool '{scenario['expected_tool']}' wurde aufgerufen ({result.duration_ms}ms)")
            else:
                print(f"    [FAIL] Tool '{scenario['expected_tool']}' nicht aufgerufen")
                if result.error:
                    print(f"    Error: {result.error}")
                if result.tool_calls:
                    print(f"    Actual calls: {result.tool_calls}")
            
            # Small delay between tests to avoid rate limiting
            time.sleep(0.5)
    
    return results


def print_summary(results: List[TestResult]):
    """Print test summary."""
    
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed
    
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    
    if failed > 0:
        print(f"\nFailed tests:")
        for r in results:
            if not r.success:
                print(f"  - {r.agent_name}/{r.scenario_name}: {r.error or 'Tool not called'}")
    
    # Group by agent
    print(f"\nBy Agent:")
    agents_tested = set(r.agent_name for r in results)
    for agent in sorted(agents_tested):
        agent_results = [r for r in results if r.agent_name == agent]
        agent_passed = sum(1 for r in agent_results if r.success)
        status = "PASS" if agent_passed == len(agent_results) else "FAIL"
        print(f"  {agent}: {agent_passed}/{len(agent_results)} [{status}]")
    
    return failed == 0


# ============================================================================

# ============================================================================

def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="VibeMind Agent Simulation Tests"
    )
    parser.add_argument(
        "--agent", "-a",
        choices=list(AGENTS.keys()),
        help="Test only specific agent"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all agents and scenarios"
    )
    
    args = parser.parse_args()
    
    # Load environment
    load_env()
    
    # List mode
    if args.list:
        print("VibeMind Agents and Test Scenarios")
        print("=" * 60)
        for key, agent in AGENTS.items():
            print(f"\n{agent.name} ({key})")
            print(f"  Role: {agent.role}")
            print(f"  Tools: {', '.join(agent.expected_tools)}")
            print(f"  Scenarios:")
            for s in agent.test_scenarios:
                print(f"    - {s['name']}: {s['description']}")
        return
    
    # Get API key
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("VibeMind Agent Simulation Tests")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"API Key: {api_key[:10]}...")
    
    # Determine which agents to test
    agents_to_test = None
    if args.agent:
        agents_to_test = [args.agent]
    
    # Run tests
    results = run_all_tests(api_key, agents_to_test, args.verbose)
    
    # Print summary
    all_passed = print_summary(results)
    
    # Exit code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()