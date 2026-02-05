# Multi-Agenten-System Entwickler-Guide

## Architektur

Das Multi-Agenten-System basiert auf AutoGen 0.10.4 und verwendet GraphFlow für die Workflow-Orchestrierung.

### Komponenten

#### 1. Agents

- **Orchestrator Agent**: Koordiniert den gesamten Workflow
- **Vision Agent**: Analysiert Bilder und visuelle Daten
- **Swarming Agent**: Koordiniert mehrere Agents
- **Summary Agent**: Fasst Ergebnisse zusammen
- **Alignment Agent**: Validiert und richtet Ergebnisse aus

#### 2. Tools

- **Vision Tools**: recognize_image, detect_objects, analyze_image
- **Swarming Tools**: distribute_task, synchronize_agents, balance_load
- **Simple Tools**: simple_task, review_task, summarize_results

#### 3. Workflow

- **DiGraphBuilder**: Erstellt Workflow-Graphen
- **GraphFlow**: Führt Workflow-Graphen aus
- **MessageFilterAgent**: Filtert Nachrichten für spezifische Agents

## Installation

### 1. Abhängigkeiten installieren

```bash
pip install autogen-agentchat autogen-ext.models.openai autogen-ext.tools.mcp python-dotenv
```

### 2. Umgebungsvariablen konfigurieren

Erstelle eine `.env` Datei im Projekt-Root:

```env
OPENROUTER_API_KEY=your_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

## Entwicklung

### 1. Neuen Agent erstellen

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.model_context import BufferedChatCompletionContext

# Model Client erstellen
model_client = OpenAIChatCompletionClient(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Agent erstellen
agent = AssistantAgent(
    name="My_Agent",
    model_client=model_client,
    tools=[my_tool],
    system_message="Du bist ein hilfreicher Assistent.",
    model_context=BufferedChatCompletionContext(buffer_size=10)
)
```

### 2. Neues Tool erstellen

```python
async def my_tool(param: str) -> str:
    """Beschreibung des Tools."""
    print(f"[Tool] Fuehre Tool aus: {param}")
    
    result = {
        "param": param,
        "status": "completed",
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"[OK] Tool abgeschlossen: {result}")
    return str(result)
```

### 3. GraphFlow Workflow erstellen

```python
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_agentchat.conditions import MaxMessageTermination

# DiGraphBuilder erstellen
builder = DiGraphBuilder()

# Nodes hinzufügen
builder.add_node(agent1)
builder.add_node(agent2)
builder.add_node(agent3)

# Kanten mit Bedingungen hinzufügen
builder.add_edge(agent1, agent2)
builder.add_edge(agent2, agent3, condition=lambda msg: "APPROVE" in msg.to_model_text())

# Entry Point setzen
builder.set_entry_point(agent1)

# Graph bauen
graph = builder.build()

# Terminierungsbedingung erstellen
termination_condition = MaxMessageTermination(20)

# GraphFlow erstellen
flow = GraphFlow(
    participants=builder.get_participants(),
    graph=graph,
    termination_condition=termination_condition
)

# Workflow ausführen
result = await flow.run(task="Deine Aufgabe hier")
```

## Testing

### 1. Unit Tests

```python
import pytest

async def test_agent():
    agent = AssistantAgent(...)
    result = await agent.run(task="Test")
    assert "TASK_COMPLETE" in str(result)
```

### 2. Integration Tests

```python
async def test_workflow():
    flow = GraphFlow(...)
    result = await flow.run(task="Test")
    assert result is not None
```

## Deployment

### 1. Vorbereitung

- Alle Tests durchführen
- Dokumentation aktualisieren
- Release-Notes erstellen

### 2. Deployment

```bash
# Build erstellen
python -m build

# Tests ausführen
python -m pytest

# Deployen
python deploy.py
```

## Best Practices

### 1. Code-Organisation

- Halte Code modular und wiederverwendbar
- Verwende klare Benennungen für Funktionen und Variablen
- Dokumentiere komplexe Logik

### 2. Fehlerbehandlung

- Implementiere robuste Fehlerbehandlung
- Logge alle Fehler detailliert
- Biete klare Fehlermeldungen

### 3. Performance

- Verwende asynchrone Operationen
- Cache Ergebnisse, wenn möglich
- Optimiere Datenbank-Abfragen

### 4. Sicherheit

- Validiere alle Eingaben
- Verwende Umgebungsvariablen für sensible Daten
- Implementiere Rate-Limiting

## Troubleshooting

### Häufige Probleme

#### 1. Agent antwortet nicht

**Problem**: Der Agent antwortet nicht auf die Aufgabe.

**Lösung**:
- Überprüfe den System-Prompt
- Erhöhe die `buffer_size` im `BufferedChatCompletionContext`
- Reduziere die Komplexität der Aufgabe

#### 2. Workflow hängt sich auf

**Problem**: Der Workflow wird nicht beendet.

**Lösung**:
- Überprüfe die Terminierungsbedingung
- Erhöhe die maximale Nachrichtenanzahl
- Füge Timeout-Logik hinzu

#### 3. Speicherprobleme

**Problem**: Das System verbraucht zu viel Speicher.

**Lösung**:
- Reduziere die `buffer_size`
- Verwende Streaming für große Ergebnisse
- Implementiere Pagination

## Ressourcen

### Dokumentation

- [API-Dokumentation](#api-dokumentation)
- [Benutzerhandbuch](#benutzerhandbuch)
- [GitHub Repository](https://github.com/vibemind/multi-agent-system)

### Community

- [AutoGen Dokumentation](https://microsoft.github.io/microsoft/autogen)
- [AutoGen Examples](https://github.com/microsoft/autogen/tree/main/python/packages/autogen-agentchat/examples)

## Support

Für Fragen oder Probleme kontaktiere:
- Email: dev@vibemind.com
- Slack: #dev-support
- GitHub Issues: https://github.com/vibemind/multi-agent-system/issues
