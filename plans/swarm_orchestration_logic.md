# Swarm-Agent Orchestrierungslogik

## Wie Agenten die Tool-Reihenfolge bestimmen

### 1. Intent-Klassifikation
```
User Input → IntentAnalysisTeam → Event Type + Payload
Beispiel: "erstelle eine neue idee" → idea.create + {"title": "..."}
```

### 2. Context-Analyse
```
Aktuelle Session + Historie → Abhängigkeiten erkennen
Beispiel: Nach idea.create → idea.connect automatisch vorschlagen
```

### 3. Agent-Routing (Handoffs)
```
Event Type → Zuständiger Agent
- idea.* → IdeasAgent
- code.* → CodingAgent  
- desktop.* → DesktopAgent
```

### 4. Tool-Sequenzierung
```
Agent + Context → Tool-Kette
Beispiel: idea.create → idea.connect → canvas.update
```

### 5. Parallelverarbeitung
```
Unabhängige Tasks → Gleichzeitig ausführen
Backend Agents verarbeiten parallel via Redis/Event Bus
```

## Beispiel aus der Konversation:

```
"erstelle eine neue idee mit dem titel test projekt"
↓
Intent: idea.create
↓  
IdeasAgent: create_idea_tool()
↓
Canvas: node_added
↓
Context: Neue Idee erstellt
↓
Automatisch: idea.connect vorschlagen
```

**Die Reihenfolge emergiert aus Intent + Context + Agent-Expertise!**