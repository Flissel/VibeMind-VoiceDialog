"""
Create a demo bubble with all supported format types to showcase the new UI designs.

Usage:
    cd python
    python -m debug.create_format_demo
"""

import sys
import os
import json
import logging
from datetime import datetime

# Add python dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.database import get_database
from data.repository import IdeasRepository
from data.canvas_repository import CanvasRepository
from data.repository_utils import generate_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_demo_bubble():
    """Create a parent bubble called 'UI Format Demo'"""
    repo = IdeasRepository()

    # Check if demo bubble already exists
    existing = repo.get_by_title("UI Format Demo")
    if existing:
        logger.info(f"Demo bubble already exists: {existing.id}")
        return existing.id

    bubble = repo.create(
        title="UI Format Demo",
        description="Demo aller Canvas-Node-Formate mit neuem UI Design"
    )
    logger.info(f"Created demo bubble: {bubble.id}")
    return bubble.id


def create_demo_nodes(bubble_id: str):
    """Create nodes with all format types inside the demo bubble."""
    canvas_repo = CanvasRepository()
    db = get_database()

    # Grid layout positions
    positions = [
        (-400, -300),  # Note
        (-100, -300),  # Action List / TODO
        (200, -300),   # Whitepaper
        (500, -300),   # Table
        (-400, 50),    # Pros & Cons
        (-100, 50),    # Hierarchy
        (200, 50),     # Kanban
        (500, 50),     # Mindmap
        (-400, 400),   # SWOT
        (-100, 400),   # User Story
        (200, 400),    # Flowchart
        (500, 400),    # Technical Specs
    ]

    demo_formats = [
        # 1. NOTE
        {
            "title": "Meeting Notizen",
            "node_type": "note",
            "content": "Gespräch mit Team über Q3 Roadmap. Fokus auf API-Redesign und neue Kunden-Features. Timeline: 6 Wochen.",
            "format_type": "note",
            "content_json": {
                "type": "note",
                "title": "Meeting Notizen",
                "text": "Gespräch mit Team über Q3 Roadmap.\n\nFokus auf API-Redesign und neue Kunden-Features.\nTimeline: 6 Wochen.\n\nNächste Schritte:\n- Design Review am Freitag\n- Prototyp bis KW 14\n- User Testing in KW 16",
                "tags": ["meeting", "roadmap", "q3"]
            }
        },
        # 2. ACTION LIST / TODO
        {
            "title": "Sprint Aufgaben",
            "node_type": "note",
            "content": "Sprint tasks for current iteration",
            "format_type": "action_list",
            "content_json": {
                "type": "action_list",
                "title": "Sprint Aufgaben",
                "items": [
                    {"task": "Landing Page erstellen", "status": "in_progress", "priority": "high", "due_date": "2026-03-28"},
                    {"task": "API Endpunkte dokumentieren", "status": "pending", "priority": "high"},
                    {"task": "Social Media Plan", "status": "pending", "priority": "medium"},
                    {"task": "Unit Tests schreiben", "status": "pending", "priority": "medium"},
                    {"task": "Logo Design finalisieren", "status": "completed", "priority": "low"},
                    {"task": "CI/CD Pipeline einrichten", "status": "completed", "priority": "high"}
                ]
            }
        },
        # 3. WHITEPAPER
        {
            "title": "Microservices Architecture",
            "node_type": "whitepaper",
            "content": "This document outlines the proposed microservices architecture for the VibeMind platform, focusing on event-driven communication patterns and service decomposition strategies.",
            "format_type": "whitepaper",
            "content_json": None  # Whitepapers use plain text content
        },
        # 4. TABLE
        {
            "title": "Team Übersicht",
            "node_type": "note",
            "content": "Team member overview with roles",
            "format_type": "table",
            "content_json": {
                "type": "table",
                "title": "Team Übersicht",
                "headers": ["Name", "Rolle", "Fokus", "Status"],
                "rows": [
                    ["Anna M.", "Lead Dev", "Backend API", "Aktiv"],
                    ["Ben K.", "Frontend", "React + Three.js", "Aktiv"],
                    ["Clara S.", "DevOps", "CI/CD + Cloud", "Urlaub"],
                    ["David L.", "ML Engineer", "NLP Models", "Aktiv"],
                    ["Eva R.", "Designer", "UI/UX", "Teilzeit"]
                ]
            }
        },
        # 5. PROS & CONS
        {
            "title": "Microservices vs Monolith",
            "node_type": "note",
            "content": "Architectural comparison",
            "format_type": "pros_cons_table",
            "content_json": {
                "type": "pros_cons_table",
                "title": "Microservices vs Monolith",
                "topic": "Architecture Decision",
                "pros": [
                    {"point": "Unabhängige Skalierung einzelner Services"},
                    {"point": "Technologie-Flexibilität pro Service"},
                    {"point": "Isolierte Deployments"},
                    {"point": "Team-Autonomie"}
                ],
                "cons": [
                    {"point": "Höhere Komplexität bei Kommunikation"},
                    {"point": "Verteilte Transaktionen schwierig"},
                    {"point": "Monitoring-Overhead"},
                    {"point": "Initiale Setup-Kosten"}
                ],
                "summary": {
                    "recommendation": "Für VibeMind empfehlen wir einen hybriden Ansatz: Kernlogik als Monolith, spezialisierte Services (Voice, ML) als Microservices."
                }
            }
        },
        # 6. HIERARCHY
        {
            "title": "Projektstruktur",
            "node_type": "note",
            "content": "Project hierarchy overview",
            "format_type": "hierarchy",
            "content_json": {
                "type": "hierarchy",
                "title": "VibeMind Architektur",
                "root_concept": "VibeMind Platform",
                "levels": [
                    {
                        "level": 1,
                        "items": [
                            {"name": "Frontend", "description": "Electron + Three.js"},
                            {"name": "Backend", "description": "Python Swarm"}
                        ]
                    },
                    {
                        "level": 2,
                        "items": [
                            {"name": "Voice Interface", "description": "OpenAI Realtime"},
                            {"name": "Canvas UI", "description": "DOM-based infinite canvas"},
                            {"name": "Orchestrator", "description": "Intent classification + routing"},
                            {"name": "Space Agents", "description": "8 domain-specific agents"}
                        ]
                    },
                    {
                        "level": 3,
                        "items": [
                            {"name": "Ideas Space", "description": "Bubbles + Notes"},
                            {"name": "Coding Space", "description": "Code generation"},
                            {"name": "Desktop Space", "description": "System automation"},
                            {"name": "Research Space", "description": "Web research"}
                        ]
                    }
                ]
            }
        },
        # 7. KANBAN
        {
            "title": "Sprint Board",
            "node_type": "note",
            "content": "Kanban board for sprint",
            "format_type": "kanban",
            "content_json": {
                "type": "kanban",
                "title": "Sprint Board",
                "columns": [
                    {
                        "name": "Backlog",
                        "color": "#6c757d",
                        "cards": [
                            {"title": "Dark Mode", "description": "Theme support", "priority": "low", "labels": ["UI"]},
                            {"title": "API v2 Docs", "description": "OpenAPI spec", "priority": "medium", "labels": ["docs"]}
                        ]
                    },
                    {
                        "name": "In Progress",
                        "color": "#007bff",
                        "cards": [
                            {"title": "Canvas Redesign", "description": "Neue Node-Designs", "priority": "high", "labels": ["UI", "UX"]},
                            {"title": "Voice Bridge V3", "description": "Async notifications", "priority": "high", "labels": ["voice"]}
                        ]
                    },
                    {
                        "name": "Done",
                        "color": "#28a745",
                        "cards": [
                            {"title": "Auth Flow", "description": "JWT + refresh", "priority": "high", "labels": ["security"]},
                            {"title": "CI Pipeline", "description": "GitHub Actions", "priority": "medium", "labels": ["devops"]}
                        ]
                    }
                ]
            }
        },
        # 8. MINDMAP
        {
            "title": "Feature Brainstorm",
            "node_type": "note",
            "content": "Feature brainstorming mindmap",
            "format_type": "mindmap",
            "content_json": {
                "type": "mindmap",
                "title": "Feature Brainstorm",
                "center": "VibeMind 2.0",
                "branches": [
                    {
                        "name": "Voice",
                        "color": "#ff6b6b",
                        "children": [
                            {"name": "Multi-Language"},
                            {"name": "Voice Cloning"},
                            {"name": "Emotion Detection"}
                        ]
                    },
                    {
                        "name": "Canvas",
                        "color": "#4ecdc4",
                        "children": [
                            {"name": "Real-time Collab"},
                            {"name": "Templates"},
                            {"name": "Export PDF"}
                        ]
                    },
                    {
                        "name": "AI",
                        "color": "#a78bfa",
                        "children": [
                            {"name": "Auto-Summarize"},
                            {"name": "Smart Links"},
                            {"name": "Code Review"}
                        ]
                    },
                    {
                        "name": "Integration",
                        "color": "#fbbf24",
                        "children": [
                            {"name": "Slack"},
                            {"name": "GitHub"},
                            {"name": "Notion"}
                        ]
                    }
                ]
            }
        },
        # 9. SWOT
        {
            "title": "Marktanalyse VibeMind",
            "node_type": "note",
            "content": "SWOT analysis for VibeMind",
            "format_type": "swot",
            "content_json": {
                "type": "swot",
                "title": "Marktanalyse VibeMind",
                "strengths": [
                    "Einzigartige Voice-First UX",
                    "Modulares Agent-System",
                    "3D Visualisierung"
                ],
                "weaknesses": [
                    "Kleine Team-Größe",
                    "Komplexe Architektur",
                    "Noch kein Mobile-Client"
                ],
                "opportunities": [
                    "Wachsender AI-Workspace-Markt",
                    "Enterprise-Kunden suchen Innovation",
                    "API-Economy für Integrationen"
                ],
                "threats": [
                    "Große Player (Notion AI, Copilot)",
                    "Schnelle Technologie-Shifts",
                    "Datenschutz-Regulierung"
                ],
                "summary": "Fokus auf Voice-First-Differenzierung und Enterprise-Features um die Nische zu verteidigen."
            }
        },
        # 10. USER STORY
        {
            "title": "User Stories Sprint 4",
            "node_type": "note",
            "content": "User stories for sprint 4",
            "format_type": "user_story",
            "content_json": {
                "type": "user_story",
                "title": "User Stories Sprint 4",
                "stories": [
                    {
                        "role": "Produktmanager",
                        "want": "Ideen per Stimme erfassen und automatisch kategorisieren",
                        "benefit": "schnellere Ideation-Sessions ohne Tippen"
                    },
                    {
                        "role": "Entwickler",
                        "want": "Code-Reviews direkt im Canvas sehen",
                        "benefit": "weniger Context-Switching zwischen Tools"
                    },
                    {
                        "role": "Designer",
                        "want": "Moodboards aus Bildern und Notizen kombinieren",
                        "benefit": "visuelle Inspiration an einem Ort"
                    }
                ],
                "personas": [
                    {"name": "Max (PM)", "description": "Tech-affin, nutzt Sprache bevorzugt"},
                    {"name": "Lisa (Dev)", "description": "Backend-fokussiert, will Effizienz"}
                ]
            }
        },
        # 11. FLOWCHART
        {
            "title": "Deployment Prozess",
            "node_type": "note",
            "content": "Deployment process flowchart",
            "format_type": "flowchart",
            "content_json": {
                "type": "flowchart",
                "title": "Deployment Prozess",
                "description": "CI/CD Pipeline für VibeMind",
                "nodes": [
                    {"id": "start", "label": "Push to Main", "type": "start"},
                    {"id": "build", "label": "Docker Build", "type": "process"},
                    {"id": "test", "label": "Tests bestanden?", "type": "decision"},
                    {"id": "staging", "label": "Deploy Staging", "type": "process"},
                    {"id": "review", "label": "Code Review OK?", "type": "decision"},
                    {"id": "prod", "label": "Deploy Production", "type": "process"},
                    {"id": "rollback", "label": "Rollback", "type": "subprocess"},
                    {"id": "end", "label": "Live!", "type": "end"}
                ],
                "edges": [
                    {"from": "start", "to": "build"},
                    {"from": "build", "to": "test"},
                    {"from": "test", "to": "staging", "label": "Ja"},
                    {"from": "test", "to": "rollback", "label": "Nein"},
                    {"from": "staging", "to": "review"},
                    {"from": "review", "to": "prod", "label": "Ja"},
                    {"from": "review", "to": "rollback", "label": "Nein"},
                    {"from": "prod", "to": "end"},
                    {"from": "rollback", "to": "build"}
                ]
            }
        },
        # 12. TECHNICAL SPECS
        {
            "title": "API Spezifikation",
            "node_type": "note",
            "content": "Technical specifications for API",
            "format_type": "technical_specs",
            "content_json": {
                "type": "technical_specs",
                "title": "API Spezifikation v2",
                "categories": [
                    {
                        "name": "Performance",
                        "specs": [
                            {"name": "Response Time", "value": "< 200ms p95", "priority": "high"},
                            {"name": "Throughput", "value": "1000 req/s", "priority": "high"},
                            {"name": "Uptime", "value": "99.9%", "priority": "critical"}
                        ]
                    },
                    {
                        "name": "Security",
                        "specs": [
                            {"name": "Authentication", "value": "JWT + Refresh Tokens", "priority": "critical"},
                            {"name": "Encryption", "value": "TLS 1.3, AES-256 at rest", "priority": "high"},
                            {"name": "Rate Limiting", "value": "100 req/min per user", "priority": "medium"}
                        ]
                    }
                ],
                "architecture_decisions": [
                    {"decision": "REST über GraphQL", "rationale": "Einfacherer Client-Code, besseres Caching"}
                ]
            }
        },
    ]

    created_nodes = []

    for i, fmt in enumerate(demo_formats):
        x, y = positions[i] if i < len(positions) else (i * 350 - 600, 700)

        node_id = generate_id()
        content_json_str = json.dumps(fmt["content_json"], ensure_ascii=False) if fmt["content_json"] else None
        format_schema_str = json.dumps({"type": fmt["format_type"]}, ensure_ascii=False)

        db.execute(
            """
            INSERT INTO canvas_nodes (id, node_type, title, content, x, y, linked_idea_id, format_schema, content_json, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                fmt["node_type"],
                fmt["title"],
                fmt["content"],
                x,
                y,
                bubble_id,
                format_schema_str,
                content_json_str,
                json.dumps({})
            )
        )

        created_nodes.append({
            "id": node_id,
            "title": fmt["title"],
            "format_type": fmt["format_type"],
            "node_type": fmt["node_type"]
        })

        logger.info(f"  Created [{fmt['format_type']:18s}] {fmt['title']}")

    return created_nodes


def main():
    print("=" * 60)
    print("  VibeMind Format Demo — Creating Demo Bubble")
    print("=" * 60)
    print()

    bubble_id = create_demo_bubble()
    print(f"Bubble ID: {bubble_id}")
    print()

    nodes = create_demo_nodes(bubble_id)
    print()
    print(f"Created {len(nodes)} demo nodes in bubble 'UI Format Demo'")
    print()
    print("To see the demo:")
    print("  1. Start the Electron app: cd electron-app && npm start")
    print("  2. Navigate to the 'UI Format Demo' bubble")
    print("  3. All format types will be visible on the canvas")
    print()
    print(f"Bubble ID for voice: 'Geh in UI Format Demo'")


if __name__ == "__main__":
    main()
