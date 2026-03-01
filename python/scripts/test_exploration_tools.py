"""
Test für Exploration Tools - Voice Commands testen

Dieser Test überprüft die Integration der Exploration Tools in das VibeMind Voice-System.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from spaces.ideas.tools.exploration_tools import (
    start_exploration,
    stop_exploration,
    get_exploration_status,
    accept_connection,
    reject_connection,
    explore_deeper,
    visualize_exploration,
    respond_to_exploration_question,
    set_exploration_direction,
    EXPLORATION_TOOLS
)


def test_exploration_tools_registration():
    """Test 1: Überprüfe, ob alle Exploration Tools registriert sind."""
    print("\n=== Test 1: Exploration Tools Registration ===")
    
    expected_tools = [
        "start_exploration",
        "stop_exploration",
        "get_exploration_status",
        "accept_connection",
        "reject_connection",
        "explore_deeper",
        "visualize_exploration",
        "respond_to_exploration_question",
        "set_exploration_direction",
        "parse_bubble_content_for_paper",
        "generate_requirements_from_sections",
        "optimize_paper_coherence",
        "generate_complete_research_paper",
    ]
    
    registered_tools = [tool["name"] for tool in EXPLORATION_TOOLS]
    
    print(f"Erwartete Tools: {len(expected_tools)}")
    print(f"Registrierte Tools: {len(registered_tools)}")
    
    missing_tools = set(expected_tools) - set(registered_tools)
    extra_tools = set(registered_tools) - set(expected_tools)
    
    if missing_tools:
        print(f"[FAIL] Fehlende Tools: {missing_tools}")
        return False
    
    if extra_tools:
        print(f"[INFO] Zusätzliche Tools: {extra_tools}")
    
    print(f"[PASS] Alle erwarteten Tools sind registriert")
    return True


def test_exploration_tool_parameters():
    """Test 2: Überprüfe die Parameter der Exploration Tools."""
    print("\n=== Test 2: Exploration Tools Parameter ===")
    
    tool_params = {
        "start_exploration": ["bubble_id", "depth", "context", "mode"],
        "stop_exploration": [],
        "get_exploration_status": [],
        "accept_connection": ["connection_id"],
        "reject_connection": ["connection_id"],
        "explore_deeper": [],
        "visualize_exploration": [],
        "respond_to_exploration_question": ["question_id", "response_type", "selected_option", "custom_text"],
        "set_exploration_direction": ["bubble_id", "direction"],
    }
    
    all_passed = True
    for tool_name, expected_params in tool_params.items():
        tool = next((t for t in EXPLORATION_TOOLS if t["name"] == tool_name), None)
        if not tool:
            print(f"[FAIL] Tool {tool_name} nicht gefunden")
            all_passed = False
            continue
        
        actual_params = list(tool.get("parameters", {}).keys())
        if set(actual_params) != set(expected_params):
            print(f"[FAIL] {tool_name}: Erwartete {expected_params}, aber hat {actual_params}")
            all_passed = False
        else:
            print(f"[PASS] {tool_name}: Parameter korrekt")
    
    return all_passed


def test_exploration_modes():
    """Test 3: Überprüfe die Explorations-Modi."""
    print("\n=== Test 3: Explorations-Modi ===")
    
    start_tool = next((t for t in EXPLORATION_TOOLS if t["name"] == "start_exploration"), None)
    if not start_tool:
        print("[FAIL] start_exploration Tool nicht gefunden")
        return False
    
    mode_param = start_tool.get("parameters", {}).get("mode", {})
    expected_modes = ["auto", "interactive", "guided"]
    
    if "enum" not in mode_param:
        print("[FAIL] mode Parameter hat kein enum")
        return False
    
    actual_modes = mode_param["enum"]
    if set(actual_modes) != set(expected_modes):
        print(f"[FAIL] Erwartete Modi {expected_modes}, aber hat {actual_modes}")
        return False
    
    print(f"[PASS] Explorations-Modi korrekt: {actual_modes}")
    return True


async def test_exploration_start_stop():
    """Test 4: Teste das Starten und Stoppen einer Exploration."""
    print("\n=== Test 4: Exploration Start/Stop ===")
    
    # Teste Start
    try:
        result = await start_exploration(
            bubble_id=None,
            depth=2,
            context="Test Exploration",
            mode="auto"
        )
        
        if not result.get("success"):
            print(f"[FAIL] Exploration starten fehlgeschlagen: {result.get('message')}")
            return False
        
        print(f"[PASS] Exploration gestartet: {result.get('message')}")
        
        # Warte kurz
        await asyncio.sleep(1)
        
        # Teste Status
        status = await get_exploration_status()
        print(f"[INFO] Exploration Status: {status.get('status')}")
        
        # Teste Stop
        stop_result = await stop_exploration()
        if not stop_result.get("success"):
            print(f"[FAIL] Exploration stoppen fehlgeschlagen: {stop_result.get('message')}")
            return False
        
        print(f"[PASS] Exploration gestoppt: {stop_result.get('message')}")
        return True
        
    except Exception as e:
        print(f"[FAIL] Exception bei Start/Stop Test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_exploration_voice_commands():
    """Test 5: Teste die Voice Commands."""
    print("\n=== Test 5: Voice Commands ===")
    
    voice_commands = [
        ("Finde tiefere Verbindungen", "start_exploration"),
        ("Erforsche Zusammenhänge", "start_exploration"),
        ("Erkunde diese Idee", "start_exploration"),
        ("Finde Verbindungen interaktiv", "start_exploration"),
        ("Finde Verbindungen automatisch", "start_exploration"),
        ("Stopp Exploration", "stop_exploration"),
        ("Beende Suche", "stop_exploration"),
        ("Exploration Status", "get_exploration_status"),
        ("Wie weit bist du?", "get_exploration_status"),
        ("Akzeptiere diese Verbindung", "accept_connection"),
        ("Speichere Verbindung", "accept_connection"),
        ("Lehne ab", "reject_connection"),
        ("Diese Verbindung ist nicht gut", "reject_connection"),
        ("Gehe tiefer", "explore_deeper"),
        ("Erkunde weiter", "explore_deeper"),
        ("Zeige gefundene Verbindungen", "visualize_exploration"),
        ("Was hast du gefunden?", "visualize_exploration"),
    ]
    
    print(f"Voice Commands: {len(voice_commands)}")
    for command, expected_tool in voice_commands:
        print(f"  - '{command}' -> {expected_tool}")
    
    print(f"[PASS] Alle Voice Commands dokumentiert")
    return True


async def test_exploration_integration():
    """Test 6: Teste die Integration mit dem IntentOrchestrator."""
    print("\n=== Test 6: Integration mit IntentOrchestrator ===")
    
    try:
        from swarm.orchestrator.intent_orchestrator import IntentOrchestrator
        
        # Erstelle IntentOrchestrator
        orchestrator = IntentOrchestrator()
        
        # Überprüfe, ob Exploration Tools in den Tool-Executoren sind
        expected_tools = [
            "idea.explore.start",
            "idea.explore.stop",
            "idea.explore.status",
            "idea.explore.accept",
            "idea.explore.reject",
            "idea.explore.depth",
            "idea.explore.visualize",
            "idea.explore.respond",
            "idea.explore.direction",
            "idea.explore.continue",
        ]
        
        tool_executors = orchestrator._tool_executors
        
        missing_tools = []
        for tool_name in expected_tools:
            if tool_name not in tool_executors:
                missing_tools.append(tool_name)
        
        if missing_tools:
            print(f"[FAIL] Fehlende Tools in IntentOrchestrator: {missing_tools}")
            return False
        
        print(f"[PASS] Alle {len(expected_tools)} Exploration Tools sind im IntentOrchestrator registriert")
        return True
        
    except Exception as e:
        print(f"[FAIL] Exception bei Integration Test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Führe alle Tests aus."""
    print("=" * 60)
    print("Exploration Tools - Voice Commands Test")
    print("=" * 60)
    
    results = []
    
    # Synchronisi Tests
    results.append(("Registration", test_exploration_tools_registration()))
    results.append(("Parameter", test_exploration_tool_parameters()))
    results.append(("Modi", test_exploration_modes()))
    results.append(("Voice Commands", await test_exploration_voice_commands()))
    
    # Asynchrone Tests
    results.append(("Start/Stop", await test_exploration_start_stop()))
    results.append(("Integration", await test_exploration_integration()))
    
    # Zusammenfassung
    print("\n" + "=" * 60)
    print("Test-Zusammenfassung")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\nGesamt: {passed}/{len(results)} Tests bestanden")
    
    if failed > 0:
        print(f"\n[WARN] {failed} Tests sind fehlgeschlagen!")
        return False
    else:
        print(f"\n[SUCCESS] Alle Tests bestanden!")
        return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
