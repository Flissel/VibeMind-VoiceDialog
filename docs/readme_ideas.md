# Ideas.Space

**Kreative Ideenverwaltung mit Bubbles-Hierarchie, Auto-Linking, AI-Exploration und Voice-gesteuertem Workflow-Design.**

## Overview

Ideas.Space ist der primäre kreative Arbeitsbereich in Vibemind. Er verwaltet zwei Kernkonzepte: **Bubbles** (Container/Workspaces) und **Ideas** (Inhalte innerhalb von Bubbles). Nutzer können per Sprache oder Text Bubbles erstellen, darin Ideen sammeln, diese automatisch verlinken, in 11 verschiedene Formate exportieren und AI-gesteuerte Explorations-Sessions starten.

Der Space hat **zwei dedizierte Backend-Agents** (51 Events total):

| Agent | Datei | Stream | Event-Count |
|-------|-------|--------|-------------|
| BubblesAgent | `agents/bubbles_agent.py` | `events:tasks:bubbles` | 14 Events |
| IdeasAgent | `agents/ideas_agent.py` | `events:tasks:ideas` | 37 Events |

> **Hinweis:** Rachel ist KEIN Ideas-spezifischer Agent, sondern das zentrale Voice-Interface der gesamten Vibemind-Plattform. Siehe Abschnitt "Rachel Voice-Agent" unten.

## Backend-Agent: BubblesAgent (14 Events)

| Event | Tool-Funktion | Beschreibung |
|-------|--------------|-------------|
| `bubble.list` | `list_bubbles` | Alle Bubbles auflisten |
| `bubble.create` | `create_bubble` | Neue Bubble erstellen |
| `bubble.enter` | `enter_bubble` | In Bubble navigieren |
| `bubble.exit` | `exit_bubble` | Bubble verlassen |
| `bubble.back` | `exit_bubble` | Alias für exit |
| `bubble.delete` | `delete_bubble` | Bubble löschen |
| `bubble.delete_all_except` | `delete_all_bubbles_except` | Alle außer einer löschen |
| `bubble.update` | `update_bubble` | Bubble-Metadaten ändern |
| `bubble.find` | `find_bubble` | Bubble suchen |
| `bubble.stats` | `get_bubble_stats` | Statistiken |
| `bubble.score` | `score_bubble` | Bubble bewerten |
| `bubble.evaluate` | `evaluate_bubble_evolution` | Shuttle-Pipeline: Evaluation |
| `bubble.promote` | `promote_bubble` | Shuttle-Pipeline: Promotion zu Projekt |
| `bubble.current` | `get_current_space` | Aktuelle Position |

## Backend-Agent: IdeasAgent (37 Events)

### Core Idea Events (9)

| Event | Tool-Funktion |
|-------|--------------|
| `idea.list` | `list_ideas` |
| `idea.count` | `count_ideas` |
| `idea.create` | `create_idea` |
| `idea.find` | `find_idea` |
| `idea.update` | `update_idea` |
| `idea.delete` | `delete_idea` |
| `idea.move` | `move_idea` |
| `idea.current_space` | `get_current_space` |

### Connection Events (6)

| Event | Tool-Funktion |
|-------|--------------|
| `idea.connect` | `connect_ideas` |
| `idea.disconnect` | `disconnect_ideas` |
| `idea.connect_multi` | `connect_ideas_multi` |
| `idea.link_to_root` | `link_idea_to_root` |
| `idea.auto_link` | `auto_link_ideas` |
| `idea.analyze_links` | `analyze_and_suggest_links` |

### Format-Conversion Events (11)

Alle dispatchen zu `convert_format` mit verschiedenen Format-Typen:

`idea.format_note`, `idea.format_action_list`, `idea.format_pros_cons`, `idea.format_hierarchy`, `idea.format_specs`, `idea.convert_format`, `idea.format_kanban`, `idea.format_mindmap`, `idea.format_swot`, `idea.format_user_story`, `idea.format_flowchart`

### Advanced AI Events (5)

| Event | Tool-Funktion |
|-------|--------------|
| `idea.summarize` | `summarize_idea` |
| `idea.whitepaper` / `idea.white_paper` | `generate_white_paper` |
| `idea.expand` | `expand_ideas` |
| `idea.explain` | `explain_idea` |
| `idea.classify` | `classify_idea` |

### Exploration Events (10)

| Event | Tool-Funktion |
|-------|--------------|
| `idea.explore.start` | `start_exploration` |
| `idea.explore.stop` | `stop_exploration` |
| `idea.explore.status` | `get_exploration_status` |
| `idea.explore.accept` | `accept_connection` |
| `idea.explore.reject` | `reject_connection` |
| `idea.explore.depth` | `explore_deeper` |
| `idea.explore.visualize` | `visualize_exploration` |
| `idea.explore.respond` | `respond_to_exploration_question` |
| `idea.explore.direction` | `set_exploration_direction` |
| `idea.explore.continue` | `continue_exploration` |

### Weitere Events

| Event | Tool-Funktion |
|-------|--------------|
| `idea.add_image` | `add_image` |
| `idea.format_table` | `format_idea_as_table` |
| `idea.generate_doc` | `generate_project_doc` |

## Explorer-Subsystem

AI-Scientist-inspirierte Exploration von Ideen-Verbindungen (1883 Zeilen Exploration-Code + 6 Explorer-Module):

| Modul | Datei | Zweck |
|-------|-------|-------|
| Connection Evaluator | `explorer/connection_evaluator.py` (14.8KB) | Bewertung von Ideen-Verbindungen |
| Exploration Clarification | `explorer/exploration_clarification.py` (24.2KB) | Klärungsdialog bei Exploration |
| Exploration Repository | `explorer/exploration_repository.py` (18.1KB) | DB-Persistenz für Explorations |
| Idea Journal | `explorer/idea_journal.py` (12.8KB) | Explorations-Protokoll |
| Idea Node | `explorer/idea_node.py` (8.6KB) | Knoten im Explorations-Baum |
| Idea Tree Search | `explorer/idea_tree_search.py` (24.2KB) | AI-Scientist Tree-Search |

## Tools

Space-spezifische Tools in `python/spaces/ideas/tools/`:

| Tool-Modul | Zweck |
|-----------|-------|
| `idea_tools.py` | Ideen CRUD, Verlinken, Auto-Link, Whitepaper, Expand |
| `bubble_tools.py` (60.2KB) | Bubbles CRUD, Navigation, Scoring, Shuttle-Pipeline |
| `exploration_tools.py` (1883 Zeilen) | 10 async Exploration-Funktionen |
| `summary_tools.py` | LLM-Zusammenfassungen |
| `format_dispatcher.py` | Format-Routing (11 Formate) |

## Rachel Voice-Agent (Plattform-weit)

Rachel (`agents/rachel_agent.py`) ist das zentrale Voice-Interface der gesamten Vibemind-Plattform — nicht nur für Ideas.Space. Ihre Hauptaufgabe: **Menschen helfen, Dinge zu organisieren und sortiert zu bekommen.**

- **1 Tool:** `send_intent(user_request: str)` — leitet User-Anfrage an IntentOrchestrator, der an alle Spaces routen kann
- Empfängt Ergebnisse async über NotificationQueue / StatusListener
- Führt KEINE Backend-Tools direkt aus — orchestriert über den IntentOrchestrator
- **Mehrsprachig:** Aktuell hauptsächlich in Deutsch genutzt; geplant für alle EU-Sprachen

## Current Status

- Bubble-Hierarchie und Navigation voll funktional (14 Events)
- Ideen-CRUD mit Auto-Link, Classify, Whitepaper, Expand (37 Events)
- Auto-Linking implementiert (`auto_link_ideas(threshold=0.5, max_links=10)`)
- 11 Format-Typen verfügbar (Kanban, Mindmap, SWOT, User Story, etc.)
- Exploration-Engine voll implementiert (10 async Events, AI-Scientist Tree-Search)
- Explorer-Subsystem mit 6 Modulen (~100KB Code)
- Rachel Voice-Interface operativ (1 Tool: send_intent)
- Shuttle-Pipeline (Evaluate/Promote) über BubblesAgent
- Rowboat-Sync für Business-Kontext in Entwicklung

## Roadmap

- Complete Rowboat sync for rich business context (Q1-Q2 2026)
- Implement advanced auto-linking with The Brain.Space insights
- Add collaborative multi-user spaces and shared design sessions
- Develop specialized templates for common use cases
- Create idea evolution and version tracking system
- Build visualization of idea-to-execution flow
- Implement chat mode alongside conversation mode

## Ecosystem-Fit

Ideas.Space ist das Gateway zu Vibemind. Nutzer drücken hier ihre Absicht aus, und der Space übersetzt sie in Arbeit für andere Spaces: Coding.Space für Entwicklung, Desktop.Space für Browser-, Messaging- und Desktop-Automation, AgentFarm.Space für Orchestrierung. The Brain.Space liefert Muster und Möglichkeiten aus den Nutzerdaten. Ideas.Space ist die UX-Schicht, die die gesamte Plattform zugänglich macht.
