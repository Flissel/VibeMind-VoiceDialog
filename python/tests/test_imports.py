"""Test all imports for VibeMind Voice Interface + Backend Agents Architecture."""
import sys
print('Python:', sys.version)
print()
print('=== New Architecture Test ===')
print()

# Test Orchestrator
print('--- Orchestrator ---')
try:
    from swarm.orchestrator import IntentClassifier, IntentOrchestrator, get_orchestrator
    print('IntentOrchestrator: OK')
    print('IntentClassifier: OK')
except Exception as e:
    print(f'Orchestrator: ERROR - {e}')
    import traceback
    traceback.print_exc()

# Test Backend Agents
print()
print('--- Backend Agents ---')
try:
    from swarm.backend_agents import IdeasAgent, DesktopAgent, CodingAgent
    from swarm.backend_agents import get_ideas_agent, get_desktop_agent, get_coding_agent
    print('IdeasAgent: OK')
    print('DesktopAgent: OK')
    print('CodingAgent: OK')
except Exception as e:
    print(f'Backend Agents: ERROR - {e}')
    import traceback
    traceback.print_exc()

# Test Rachel (Voice Interface)
print()
print('--- Rachel (Voice Interface) ---')
try:
    from swarm.user_agents.rachel import RachelAgent, create_rachel_agent
    agent = RachelAgent()
    tools = agent.get_tools()
    print(f'RachelAgent: OK - {len(tools)} tool(s)')
    for t in tools:
        if callable(t):
            print(f'  - {t.__name__ if hasattr(t, "__name__") else "send_intent"}')
        else:
            print(f'  - {t}')
except Exception as e:
    print(f'RachelAgent: ERROR - {e}')
    import traceback
    traceback.print_exc()

# Test Event Team
print()
print('--- Event Team ---')
try:
    from swarm.event_team import TaskSeeder, JobManager, EventRouter
    print('TaskSeeder: OK')
    print('JobManager: OK')
    print('EventRouter: OK')
except Exception as e:
    print(f'Event Team: ERROR - {e}')

# Test Event Bus
try:
    from swarm.event_bus import EventBus, SwarmEvent
    print('EventBus: OK')
except Exception as e:
    print(f'EventBus: ERROR - {e}')

# Test Listeners
try:
    from swarm.listeners import StatusListener
    print('StatusListener: OK')
except Exception as e:
    print(f'StatusListener: ERROR - {e}')

# Test VoiceBridgeV2
print()
print('--- VoiceBridgeV2 ---')
try:
    from swarm.voice_bridge_v2 import VoiceBridgeV2, create_voice_bridge_v2
    print('VoiceBridgeV2: OK')
except Exception as e:
    print(f'VoiceBridgeV2: ERROR - {e}')

print()
print('=== Tool Categories (Backend Agents) ===')
try:
    from swarm.tools.adapted_bubble_tools import BUBBLE_TOOLS
    from swarm.tools.adapted_idea_tools import IDEA_TOOLS
    from swarm.tools.adapted_desktop_tools import DESKTOP_TOOLS
    from swarm.tools.adapted_coding_tools import CODING_TOOLS
    from swarm.tools.voice_coding_tools import VOICE_CODING_TOOLS

    print(f'Bubble Tools: {len(BUBBLE_TOOLS)}')
    print(f'Idea Tools: {len(IDEA_TOOLS)}')
    print(f'Desktop Tools: {len(DESKTOP_TOOLS)}')
    print(f'Coding Tools: {len(CODING_TOOLS)}')
    print(f'Voice Coding Tools: {len(VOICE_CODING_TOOLS)}')
    total = len(BUBBLE_TOOLS) + len(IDEA_TOOLS) + len(DESKTOP_TOOLS) + len(CODING_TOOLS) + len(VOICE_CODING_TOOLS)
    print(f'TOTAL: {total} tools (executed by Backend Agents)')
except Exception as e:
    print(f'Tools: ERROR - {e}')

print()
print('=== Architecture Summary ===')
print('Rachel: Voice Interface (1 tool: send_intent)')
print('Orchestrator: Intent Classification + Event Seeding')
print('Backend Agents: IdeasAgent, DesktopAgent, CodingAgent')
print('  - Execute the 37 tools based on Redis events')
print('Status Listener: Backend -> Rachel TTS')
