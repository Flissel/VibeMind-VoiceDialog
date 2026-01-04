# VibeMind Multi-Agent System

## Architektur

Das System verwendet 4 spezialisierte Agenten die über Client-Tools kommunizieren:

```
┌─────────────────────────────────────────────────────────────┐
│                     MULTIVERSE                              │
│                                                             │
│   ┌─────────┐                           ┌─────────────┐    │
│   │ Rachel  │◄─────────────────────────►│   Bubbles   │    │
│   │  Entry  │      enter/exit           │  (Spaces)   │    │
│   └────┬────┘                           └─────────────┘    │
│        │                                                    │
│        │ transfer_to_alice                                  │
│        ▼                                                    │
│   ┌─────────┐                                              │
│   │  Alice  │  Hub/Coordinator                             │
│   └────┬────┘                                              │
│        │                                                    │
│   ┌────┴────────────┐                                      │
│   │                 │                                      │
│   ▼                 ▼                                      │
│ ┌─────┐         ┌─────────┐                               │
│ │Adam │         │ Antoni  │                               │
│ │Desk │         │ Coding  │                               │
│ └─────┘         └─────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

## Agenten

| Agent | Rolle | Voice | Transfers zu |
|-------|-------|-------|--------------|
| **Rachel** | Multiverse Navigator (Entry) | Rachel | Alice |
| **Alice** | Coordinator Hub | Alice | Adam, Antoni, Rachel |
| **Adam** | Desktop Worker | Adam | Alice |
| **Antoni** | Coding/Writing | Antoni | Alice |

## Verzeichnisstruktur

```
python/agents/
├── __init__.py          # AgentRegistry - lädt und verwaltet Agenten
├── setup.py             # Auto-Setup beim App-Start
├── README.md            # Diese Datei
│
├── rachel/              # Multiverse Navigator (Entry Agent)
│   ├── __init__.py
│   ├── config.py        # AGENT_CONFIG, voice_id, etc.
│   ├── prompts.py       # SYSTEM_PROMPT, FIRST_MESSAGE
│   └── tools.py         # Bubble-Tools + transfer_to_alice
│
├── alice/               # Coordinator Hub
│   ├── __init__.py
│   ├── config.py
│   ├── prompts.py
│   └── tools.py         # transfer_to_adam, transfer_to_antoni, transfer_to_rachel
│
├── adam/                # Desktop Worker
│   ├── __init__.py
│   ├── config.py
│   ├── prompts.py
│   └── tools.py         # Desktop-Tools + transfer_to_alice
│
└── antoni/              # Coding/Writing Worker
    ├── __init__.py
    ├── config.py
    ├── prompts.py
    └── tools.py         # Code/File-Tools + transfer_to_alice
```

## Verwendung

### Agent-Registry

```python
from agents import get_registry, get_agent, get_entry_agent

# Registry holen
registry = get_registry()

# Entry-Agent (Rachel) holen
entry = get_entry_agent()
print(entry.name)  # "Rachel"

# Agent nach Slug holen
alice = get_agent("alice")

# Agent-ID für ElevenLabs
agent_id = registry.get_agent_id("rachel")

# Tools eines Agenten
tools = registry.get_tools("rachel")
```

### Setup beim App-Start

```python
from agents.setup import setup_agents

# Erstellt feste Spaces und prüft Konfiguration
setup_agents()
```

### Client-Tools registrieren

```python
from elevenlabs.conversational_ai.conversation import ClientTools
from agents import get_registry

client_tools = ClientTools()
registry = get_registry()

# Rachel-Tools registrieren
registry.register_agent_tools("rachel", client_tools)
```

## .env Konfiguration

```env
# ElevenLabs Agent IDs
RACHEL_AGENT_ID=agent_xxx
ALICE_AGENT_ID=agent_xxx
ADAM_AGENT_ID=agent_xxx
ANTONI_AGENT_ID=agent_xxx

# Alternativ (Legacy)
AGENT_MULTIVERSE=agent_xxx
AGENT_PROJECT_MANAGER=agent_xxx
AGENT_DESKTOP_WORKER=agent_xxx
AGENT_PROJECT_WRITER=agent_xxx
```

## Deployment

### Client-Tools deployen

```bash
# Zeige aktuelle Tool-Konfiguration
python deploy_client_tools.py --show

# Deploye neue Client-Tools (entfernt System-Tools)
python deploy_client_tools.py --deploy
```

### Agent-Setup

```bash
# Erstelle feste Spaces und prüfe Konfiguration
python -m agents.setup
```

## Transfer-Flow

1. User startet mit **Rachel** (Entry Agent)
2. Rachel navigiert durch Bubbles oder transferiert zu Alice
3. Alice delegiert an Adam (Desktop) oder Antoni (Coding)
4. Spezialisten berichten zurück an Alice
5. Alice kann zurück zu Rachel transferieren

### Wichtig: Client-Tools vs System-Tools

- **System-Tools** (alt): Werden serverseitig ausgeführt → kein Callback zu Python
- **Client-Tools** (neu): Werden in Python ausgeführt → volle Kontrolle

Mit Client-Tools kann Python:
- Die Session beenden und neu starten
- Das UI aktualisieren (via Electron IPC)
- Den Transfer-Kontext speichern