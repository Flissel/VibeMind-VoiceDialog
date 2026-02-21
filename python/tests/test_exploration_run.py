"""
Test the exploration algorithm with real bubbles.
This demonstrates what the exploration system does.
"""
import sys
import os
import asyncio

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add python folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def run_exploration_demo():
    """Run a demo of the exploration algorithm."""
    print("=" * 70)
    print("EXPLORATION ALGORITHM DEMO")
    print("=" * 70)

    # Step 1: Get existing bubbles
    print("\n📦 Step 1: Loading existing bubbles...")
    from data import IdeasRepository
    repo = IdeasRepository()
    ideas = repo.list(limit=50)

    # Get top-level bubbles
    bubbles = [i for i in ideas if not i.parent_id]
    print(f"   Found {len(bubbles)} bubbles:")
    for b in bubbles:
        desc = (b.description or "keine Beschreibung")[:60]
        print(f"   • {b.title}: {desc}")

    if len(bubbles) < 2:
        print("\n⚠️  Mindestens 2 Bubbles werden für Exploration benötigt!")
        print("   Erstelle Test-Bubbles...")

        # Create some test bubbles
        test_bubbles = [
            ("Marketing", "Strategien für Kundengewinnung und Markenaufbau"),
            ("Produktentwicklung", "Neue Features und Produktideen"),
            ("KI-Integration", "Machine Learning und AI-Anwendungen im Produkt"),
            ("Social Media", "Instagram, TikTok, LinkedIn Kampagnen"),
        ]

        for title, desc in test_bubbles:
            existing = repo.get_by_title(title)
            if not existing:
                repo.create(title=title, description=desc)
                print(f"   ✓ Erstellt: {title}")

        ideas = repo.list(limit=50)
        bubbles = [i for i in ideas if not i.parent_id]

    # Step 2: Initialize the exploration module
    print("\n🔬 Step 2: Initializing exploration components...")
    try:
        from spaces.ideas.explorer.idea_tree_search import IdeaTreeSearch
        from spaces.ideas.explorer.idea_node import IdeaNode
        from spaces.ideas.explorer.idea_journal import IdeaJournal
        from spaces.ideas.explorer.connection_evaluator import ConnectionEvaluator
        print("   ✓ IdeaTreeSearch loaded")
        print("   ✓ IdeaNode loaded")
        print("   ✓ IdeaJournal loaded")
        print("   ✓ ConnectionEvaluator loaded")
    except ImportError as e:
        print(f"   ✗ Import error: {e}")
        return

    # Step 3: Create a journal for exploration
    print("\n📓 Step 3: Creating exploration journal...")
    journal = IdeaJournal()
    session_id = getattr(journal, 'session_id', getattr(journal, 'session', 'unknown'))
    print(f"   Session: {session_id}")

    # Step 4: Prepare bubble data for exploration
    print("\n🎯 Step 4: Preparing bubble data...")
    bubble_data = []
    for b in bubbles:
        data = {
            "id": b.id,
            "title": b.title,
            "description": b.description or "",
        }
        bubble_data.append(data)
        print(f"   • {b.title} (id: {b.id[:8]}...)")

    # Step 5: Run exploration
    print("\n🚀 Step 5: Running BFTS exploration...")
    print("   (Best-First Tree Search with 4 stages)")
    print("   Stages: DIRECT → INDIRECT → ABSTRACT → CREATIVE")
    print()

    try:
        # Initialize the tree search
        root_bubble = bubbles[0]
        print(f"   Starting from: {root_bubble.title}")

        # Create evaluator
        evaluator = ConnectionEvaluator()

        # Create simple mock connections for demo
        # In real use, this would call the LLM
        print("\n   🔍 Searching for connections...")

        connections_found = []
        for i, b1 in enumerate(bubbles):
            for b2 in bubbles[i+1:]:
                # Simple semantic similarity simulation
                # Real implementation uses embeddings + LLM
                shared_words = set(b1.title.lower().split()) & set(b2.title.lower().split())
                shared_desc = set((b1.description or "").lower().split()) & set((b2.description or "").lower().split())

                if shared_words or len(shared_desc) > 3:
                    connection = {
                        "source": b1.title,
                        "target": b2.title,
                        "shared": list(shared_words | shared_desc)[:5],
                        "stage": "DIRECT",
                    }
                    connections_found.append(connection)
                    print(f"   ✓ DIRECT: {b1.title} ←→ {b2.title}")

        # Check for abstract connections (theme-based)
        print("\n   🔍 Checking abstract connections (themes)...")
        themes = {
            "business": ["Marketing", "Vertrieb", "Kunden", "Strategie"],
            "tech": ["KI", "AI", "Technologie", "Software", "App"],
            "social": ["Social", "Media", "Instagram", "TikTok"],
        }

        for theme, keywords in themes.items():
            matching = [b for b in bubbles if any(kw.lower() in b.title.lower() or kw.lower() in (b.description or "").lower() for kw in keywords)]
            if len(matching) >= 2:
                print(f"   ✓ ABSTRACT ({theme}): {[m.title for m in matching]}")
                connections_found.append({
                    "source": matching[0].title,
                    "target": matching[1].title,
                    "theme": theme,
                    "stage": "ABSTRACT",
                })

        print(f"\n   📊 Found {len(connections_found)} potential connections")

    except Exception as e:
        print(f"   ✗ Exploration error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 6: Show what the real exploration would do
    print("\n" + "=" * 70)
    print("WAS DIE ECHTE EXPLORATION TUT:")
    print("=" * 70)

    print("""
    1. USER SAGT: "Finde tiefere Verbindungen"

    2. INTENT CLASSIFIER erkennt:
       → event_type: idea.explore.start
       → payload: {mode: "auto", depth: 4}

    3. BFTS ALGORITHMUS startet:

       Stage 1 - DIRECT:
       ├── Findet Bubbles mit gemeinsamen Wörtern
       └── Beispiel: "Marketing" ↔ "Produktentwicklung" (beide: "Kunden")

       Stage 2 - INDIRECT:
       ├── Findet Verbindungen über geteilte Ideen
       └── Beispiel: "A" ↔ "C" weil beide mit "B" verbunden

       Stage 3 - ABSTRACT:
       ├── Findet thematische Verbindungen via LLM
       └── Beispiel: "KI-Integration" ↔ "Produktentwicklung" (Thema: Innovation)

       Stage 4 - CREATIVE:
       ├── Generiert neue Verbindungsideen via LLM
       └── Beispiel: "Was wäre wenn Marketing KI nutzt?"

    4. INTERACTIVE MODE (wenn aktiviert):
       ┌─────────────────────────────────────────────────────────┐
       │  Gefunden: "Marketing" ─── Zielgruppe ─── "Social"      │
       │                                                         │
       │  [✓ Behalten]  [✗ Ablehnen]  [🔍 Tiefer]              │
       └─────────────────────────────────────────────────────────┘

       User sagt "Ja behalten" → Verbindung wird gespeichert
       User sagt "Tiefer" → Exploration folgt diesem Pfad

    5. ERGEBNIS:
       → Neue Edges in canvas_edges gespeichert
       → UI zeigt Verbindungen als Linien zwischen Bubbles
    """)

    # Step 7: Check what's missing for full integration
    print("\n" + "=" * 70)
    print("WAS NOCH FEHLT FÜR VOLLE INTEGRATION:")
    print("=" * 70)

    checks = [
        ("IdeasAgent EVENT_TO_TOOL Mappings", False, "idea.explore.* → tools"),
        ("Datenbank-Tabellen", False, "exploration_sessions, exploration_nodes"),
        ("electron_backend.py Handler", False, "exploration_start, exploration_respond"),
    ]

    for name, ok, detail in checks:
        status = "✓" if ok else "✗"
        print(f"   {status} {name}: {detail}")

    print("\n   Nach der Integration:")
    print("   → Voice: 'Finde tiefere Verbindungen' → Exploration startet")
    print("   → UI: Dialog erscheint bei gefundenen Verbindungen")
    print("   → Voice: 'Ja behalten' → Verbindung wird gespeichert")


if __name__ == "__main__":
    asyncio.run(run_exploration_demo())
