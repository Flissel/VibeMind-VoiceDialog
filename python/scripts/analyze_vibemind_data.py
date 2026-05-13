#!/usr/bin/env python3
"""
VibeMind Datenbank Analyse
Zeigt alle relevanten Daten in Bubbles/Ideen an
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from data.repository import IdeasRepository, ProjectsRepository, CanvasRepository, ConversationRepository, ShuttlesRepository
from data.supabase_database import get_database

def analyze_vibemind_data():
    """Analysiere alle Daten in der VibeMind Datenbank"""

    print("=" * 80)
    print("VibeMind Datenbank Analyse")
    print("=" * 80)
    print("Starting analysis...")

    # Repositories initialisieren
    ideas_repo = IdeasRepository()
    projects_repo = ProjectsRepository()
    canvas_repo = CanvasRepository()
    conv_repo = ConversationRepository()
    shuttles_repo = ShuttlesRepository()

    # 1. Alle Bubbles/Ideen analysieren
    print("\n1. BUBBLES/IDEEN ANALYSE")
    print("-" * 40)

    ideas = ideas_repo.list(limit=100)
    print(f"Gesamt: {len(ideas)} Ideen")

    # Nach Typ gruppieren
    top_level = [i for i in ideas if i.parent_id is None]
    nested = [i for i in ideas if i.parent_id is not None]

    print(f"Top-Level Bubbles: {len(top_level)}")
    print(f"Nested Ideen: {len(nested)}")

    # Top-Level Bubbles anzeigen
    print("\nTOP-LEVEL BUBBLES:")
    for idea in top_level[:10]:  # Erste 10
        status = f"[{idea.status}]" if idea.status != "raw" else ""
        score = f"(Score: {idea.score:.1f})" if idea.score > 0 else ""
        print(f"  • {idea.title} {status} {score}")
        if idea.description:
            desc = idea.description[:50] + "..." if len(idea.description) > 50 else idea.description
            print(f"    {desc}")

    # 2. Projekte analysieren
    print("\n\n2. PROJEKTE ANALYSE")
    print("-" * 40)

    projects = projects_repo.list(limit=50)
    print(f"Gesamt: {len(projects)} Projekte")

    active_projects = [p for p in projects if p.status == "active"]
    completed_projects = [p for p in projects if p.status == "completed"]

    print(f"Aktive: {len(active_projects)}")
    print(f"Abgeschlossen: {len(completed_projects)}")

    # Code-Generierung Status
    generating = [p for p in projects if p.generation_status == "generating"]
    completed_gen = [p for p in projects if p.generation_status == "completed"]

    print(f"Code-Generierung aktiv: {len(generating)}")
    print(f"Code-Generierung abgeschlossen: {len(completed_gen)}")

    # 3. Canvas Analyse
    print("\n\n3. CANVAS ANALYSE")
    print("-" * 40)

    nodes = canvas_repo.list_nodes(limit=200)
    edges = canvas_repo.list_edges(limit=500)

    print(f"Canvas Nodes: {len(nodes)}")
    print(f"Canvas Edges: {len(edges)}")

    # Node Types
    node_types = {}
    for node in nodes:
        node_types[node.node_type] = node_types.get(node.node_type, 0) + 1

    print("Node Types:")
    for node_type, count in node_types.items():
        print(f"  • {node_type}: {count}")

    # 4. Konversationen analysieren
    print("\n\n4. KONVERSATIONEN ANALYSE")
    print("-" * 40)

    sessions = conv_repo.list_sessions(limit=20)
    total_messages = conv_repo.count_messages()

    print(f"Sessions: {len(sessions)}")
    print(f"Total Messages: {total_messages}")

    if sessions:
        latest_session = sessions[0]
        session_messages = conv_repo.get_session_messages(latest_session.id)
        print(f"Letzte Session: {len(session_messages)} Nachrichten")

    # 5. Shuttles analysieren
    print("\n\n5. SHUTTLES ANALYSE")
    print("-" * 40)

    shuttles = shuttles_repo.list(limit=50)
    print(f"Gesamt: {len(shuttles)} Shuttles")

    # Status gruppieren
    shuttle_status = {}
    for shuttle in shuttles:
        shuttle_status[shuttle.status] = shuttle_status.get(shuttle.status, 0) + 1

    print("Status:")
    for status, count in shuttle_status.items():
        print(f"  • {status}: {count}")

    # 6. Spezifische Bubbles detailliert analysieren
    print("\n\n6. DETAILLIERTE BUBBLE ANALYSE")
    print("-" * 40)

    for bubble in top_level[:5]:  # Erste 5 Bubbles detailliert
        print(f"\nBUBBLE: {bubble.title}")
        print(f"  ID: {bubble.id}")
        print(f"  Status: {bubble.status}")
        print(f"  Score: {bubble.score:.1f}")
        print(f"  Created: {bubble.created_at}")

        if bubble.tags:
            print(f"  Tags: {', '.join(bubble.tags)}")

        # Verknüpfte Canvas Nodes
        linked_nodes = [n for n in nodes if n.linked_idea_id == bubble.id]
        if linked_nodes:
            print(f"  Canvas Nodes: {len(linked_nodes)}")
            for node in linked_nodes[:3]:
                print(f"    • {node.title} ({node.node_type})")

        # Verknüpfte Projekte
        linked_projects = projects_repo.list_by_idea(bubble.id)
        if linked_projects:
            print(f"  Projekte: {len(linked_projects)}")
            for project in linked_projects:
                print(f"    • {project.name} ({project.status})")

        # Nested Ideen
        nested_ideas = [i for i in ideas if i.parent_id == bubble.id]
        if nested_ideas:
            print(f"  Nested Ideen: {len(nested_ideas)}")
            for idea in nested_ideas[:3]:
                print(f"    • {idea.title}")

    print("\n" + "=" * 80)
    print("Analyse abgeschlossen")
    print("=" * 80)

if __name__ == "__main__":
    analyze_vibemind_data()