#!/usr/bin/env python3
"""
Schnelle Datenbank-Überprüfung für VibeMind
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data.repository import IdeasRepository, ProjectsRepository

def main():
    print("VibeMind Datenbank - Schnellübersicht")
    print("=" * 50)

    # Ideas
    ideas_repo = IdeasRepository()
    ideas = ideas_repo.list(limit=50)

    print(f"Ideen gesamt: {len(ideas)}")

    top_level = [i for i in ideas if i.parent_id is None]
    nested = [i for i in ideas if i.parent_id is not None]

    print(f"Top-Level Bubbles: {len(top_level)}")
    print(f"Nested Ideen: {len(nested)}")

    print("\nTop-Level Bubbles:")
    for idea in top_level[:10]:
        status = f"[{idea.status}]" if idea.status != "raw" else ""
        score = f"(Score: {idea.score:.1f})" if idea.score > 0 else ""
        print(f"  • {idea.title} {status} {score}")

    # Projects
    projects_repo = ProjectsRepository()
    projects = projects_repo.list(limit=20)

    print(f"\nProjekte gesamt: {len(projects)}")

    active = [p for p in projects if p.status == "active"]
    completed = [p for p in projects if p.status == "completed"]

    print(f"Aktive: {len(active)}")
    print(f"Abgeschlossen: {len(completed)}")

    # Generation status
    generating = [p for p in projects if p.generation_status == "generating"]
    print(f"Code-Generierung aktiv: {len(generating)}")

if __name__ == "__main__":
    main()