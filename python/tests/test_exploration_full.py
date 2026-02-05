"""
Full exploration test with real bubbles and descriptions.
"""
import sys
import os
import asyncio

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add python folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def setup_test_bubbles():
    """Create test bubbles with rich descriptions for exploration."""
    print("=" * 70)
    print("SETUP: Creating test bubbles for exploration")
    print("=" * 70)

    from data import IdeasRepository
    repo = IdeasRepository()

    test_bubbles = [
        (
            "Marketing Strategie",
            "Entwicklung einer umfassenden Marketing-Strategie für B2B SaaS Produkte. "
            "Fokus auf Content Marketing, SEO, und Lead Generation. "
            "Zielgruppe sind mittelständische Unternehmen im DACH-Raum."
        ),
        (
            "Produktentwicklung",
            "Roadmap für die nächsten 6 Monate. Neue Features: KI-gestützte Analyse, "
            "Dashboard-Redesign, API-Erweiterungen. Priorisierung nach Kundenfeedback."
        ),
        (
            "KI Integration",
            "Machine Learning Modelle für automatische Textanalyse und Empfehlungen. "
            "OpenAI API, Embeddings, RAG-System. Ziel: intelligentere Produktvorschläge."
        ),
        (
            "Social Media",
            "LinkedIn, Twitter und Instagram Kampagnen. Content-Kalender, "
            "Influencer-Kooperationen, Paid Ads Budget von 5000€/Monat."
        ),
        (
            "Customer Success",
            "Onboarding-Prozesse verbessern, Churn-Rate reduzieren. "
            "Feedback-Loops, NPS-Umfragen, Support-Tickets analysieren."
        ),
    ]

    created = []
    for title, description in test_bubbles:
        # Check if exists
        existing = repo.get_by_title(title)
        if existing:
            # Update with description if missing
            if not existing.description:
                repo.update(existing.id, description=description)
                print(f"✓ Updated: {title}")
            else:
                print(f"• Exists: {title}")
            created.append(existing.id)
        else:
            new_id = repo.create(title=title, description=description)
            print(f"✓ Created: {title}")
            created.append(new_id)

    return created


async def test_exploration_with_data():
    """Test exploration with real data."""
    print("\n" + "=" * 70)
    print("EXPLORATION TEST WITH REAL DATA")
    print("=" * 70)

    from swarm.tools.exploration_tools import start_exploration, get_exploration_status

    # Try to start exploration
    print("\n1. Starting exploration...")
    result = await start_exploration(
        bubble_id=None,  # Start from current space
        depth=3,
        mode="auto",  # auto mode - no user interaction needed
        context="Finde Verbindungen zwischen Marketing und KI"
    )

    print(f"\n   Result: {result.get('success')}")
    print(f"   Message: {result.get('message')}")

    if result.get('connections'):
        print(f"\n   Gefundene Verbindungen:")
        for conn in result.get('connections', []):
            print(f"     • {conn.get('source')} ↔ {conn.get('target')}: {conn.get('reasoning', 'N/A')}")

    # Check status
    print("\n2. Checking status...")
    status = await get_exploration_status()
    print(f"   Status: {status}")


async def show_current_bubbles():
    """Show current bubbles in the database."""
    print("\n" + "=" * 70)
    print("CURRENT BUBBLES IN DATABASE")
    print("=" * 70)

    from data import IdeasRepository
    repo = IdeasRepository()
    ideas = repo.list(limit=20)

    bubbles = [i for i in ideas if not i.parent_id]
    print(f"\nFound {len(bubbles)} bubbles:\n")

    for b in bubbles:
        desc = (b.description or "keine Beschreibung")[:80]
        print(f"• {b.title}")
        print(f"  {desc}...")
        print()


if __name__ == "__main__":
    async def main():
        await setup_test_bubbles()
        await show_current_bubbles()
        await test_exploration_with_data()

    asyncio.run(main())
