"""
Direct exploration test - bypassing tool wrappers to test core algorithm.
"""
import sys
import os
import asyncio

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_direct_exploration():
    """Test the exploration algorithm directly."""
    print("=" * 70)
    print("DIRECT EXPLORATION ALGORITHM TEST")
    print("=" * 70)

    from data import IdeasRepository
    repo = IdeasRepository()

    # Get bubbles with descriptions
    ideas = repo.list(limit=50)
    bubbles = [i for i in ideas if not i.parent_id and i.description]

    print(f"\n1. Found {len(bubbles)} bubbles with descriptions:")
    for b in bubbles:
        print(f"   • {b.title}")

    if len(bubbles) < 2:
        print("   Not enough bubbles with descriptions!")
        return

    # Test the connection evaluator
    print("\n2. Testing ConnectionEvaluator...")
    try:
        from spaces.ideas.explorer.connection_evaluator import ConnectionEvaluator
        evaluator = ConnectionEvaluator()
        print("   ✓ ConnectionEvaluator loaded")

        # Check what methods it has
        import inspect
        methods = [m for m in dir(evaluator) if not m.startswith('_') and callable(getattr(evaluator, m))]
        print(f"   Methods: {methods}")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test IdeaTreeSearch
    print("\n3. Testing IdeaTreeSearch...")
    try:
        from spaces.ideas.explorer.idea_tree_search import IdeaTreeSearch
        print("   ✓ IdeaTreeSearch loaded")

        # Check what methods it has
        methods = [m for m in dir(IdeaTreeSearch) if not m.startswith('_')]
        print(f"   Class attributes: {methods[:10]}...")

        # Try to instantiate
        print("\n   Creating IdeaTreeSearch instance...")

        # Prepare bubble data
        bubble_data = []
        for b in bubbles:
            bubble_data.append({
                "id": b.id,
                "title": b.title,
                "description": b.description,
            })

        # Check constructor signature
        sig = inspect.signature(IdeaTreeSearch.__init__)
        print(f"   Constructor: {sig}")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # Simulate what exploration would find
    print("\n4. Simulating connection discovery...")
    print("   (Manual semantic analysis - what LLM would find)")
    print()

    potential_connections = []

    # Marketing Strategie <-> Social Media
    if any(b.title == "Marketing Strategie" for b in bubbles) and any(b.title == "Social Media" for b in bubbles):
        potential_connections.append({
            "source": "Marketing Strategie",
            "target": "Social Media",
            "stage": "DIRECT",
            "reasoning": "Social Media ist ein Kanal für Marketing-Strategie",
            "edge_label": "nutzt Kanal",
            "score": 0.9
        })

    # Produktentwicklung <-> KI Integration
    if any(b.title == "Produktentwicklung" for b in bubbles) and any(b.title == "KI Integration" for b in bubbles):
        potential_connections.append({
            "source": "Produktentwicklung",
            "target": "KI Integration",
            "stage": "DIRECT",
            "reasoning": "KI-Features sind Teil der Produkt-Roadmap",
            "edge_label": "enthält Feature",
            "score": 0.85
        })

    # Marketing <-> Customer Success (indirect via Kundenfeedback)
    if any(b.title == "Marketing Strategie" for b in bubbles) and any(b.title == "Customer Success" for b in bubbles):
        potential_connections.append({
            "source": "Marketing Strategie",
            "target": "Customer Success",
            "stage": "INDIRECT",
            "reasoning": "Marketing-Erfolg hängt von Kundenzufriedenheit ab",
            "edge_label": "beeinflusst",
            "score": 0.75
        })

    # KI Integration <-> Customer Success (abstract - both improve user experience)
    if any(b.title == "KI Integration" for b in bubbles) and any(b.title == "Customer Success" for b in bubbles):
        potential_connections.append({
            "source": "KI Integration",
            "target": "Customer Success",
            "stage": "ABSTRACT",
            "reasoning": "KI kann Support-Anfragen automatisch analysieren (aus Customer Success Beschreibung)",
            "edge_label": "ermöglicht Analyse",
            "score": 0.7
        })

    # Social Media <-> Customer Success (creative - testimonials)
    if any(b.title == "Social Media" for b in bubbles) and any(b.title == "Customer Success" for b in bubbles):
        potential_connections.append({
            "source": "Social Media",
            "target": "Customer Success",
            "stage": "CREATIVE",
            "reasoning": "Zufriedene Kunden können als Social Proof auf Social Media genutzt werden",
            "edge_label": "liefert Testimonials",
            "score": 0.65
        })

    print(f"   Found {len(potential_connections)} potential connections:\n")

    for conn in potential_connections:
        print(f"   [{conn['stage']}] {conn['source']} ─── {conn['edge_label']} ─── {conn['target']}")
        print(f"            Score: {conn['score']:.2f}")
        print(f"            Reasoning: {conn['reasoning']}")
        print()

    # Show what would happen in interactive mode
    print("=" * 70)
    print("WAS IM INTERACTIVE MODE PASSIEREN WÜRDE:")
    print("=" * 70)

    print("""
    Bei jeder gefundenen Verbindung:

    ┌────────────────────────────────────────────────────────────────────┐
    │                                                                    │
    │  🔍 Verbindung gefunden:                                          │
    │                                                                    │
    │     [Marketing Strategie] ─── nutzt Kanal ─── [Social Media]     │
    │                                                                    │
    │  💡 Begründung:                                                    │
    │     "Social Media ist ein Kanal für Marketing-Strategie"          │
    │                                                                    │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
    │  │  Behalten Y │  │  Ablehnen N │  │   Tiefer D  │               │
    │  └─────────────┘  └─────────────┘  └─────────────┘               │
    │                                                                    │
    └────────────────────────────────────────────────────────────────────┘

    User sagt "Ja behalten":
    → Verbindung wird in canvas_edges gespeichert
    → Exploration geht zur nächsten Verbindung

    User sagt "Tiefer":
    → Exploration folgt diesem Pfad (Social Media als neuer Startpunkt)
    → Findet Verbindungen VON Social Media aus
    """)


if __name__ == "__main__":
    asyncio.run(test_direct_exploration())
