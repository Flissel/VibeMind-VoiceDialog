"""Test the current state of the exploration system."""
import sys
import os

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add python folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_exploration_module():
    print("=== Test 1: Exploration Module ===")
    try:
        from spaces.ideas.explorer import IdeaTreeSearch, IdeaNode, IdeaJournal
        print("✓ IdeaTreeSearch imported")
        print("✓ IdeaNode imported")
        print("✓ IdeaJournal imported")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_exploration_tools():
    print("\n=== Test 2: Exploration Tools ===")
    try:
        from swarm.tools.exploration_tools import (
            start_exploration, stop_exploration, get_exploration_status,
            accept_connection, reject_connection, explore_deeper,
            visualize_exploration, respond_to_exploration_question,
            set_exploration_direction
        )
        print("✓ start_exploration")
        print("✓ stop_exploration")
        print("✓ get_exploration_status")
        print("✓ accept_connection")
        print("✓ reject_connection")
        print("✓ explore_deeper")
        print("✓ visualize_exploration")
        print("✓ respond_to_exploration_question")
        print("✓ set_exploration_direction")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_ideas_agent_mappings():
    print("\n=== Test 3: IdeasAgent EVENT_TO_TOOL ===")
    try:
        from spaces.ideas.agents.ideas_agent import IdeasAgent
        agent = IdeasAgent()

        # Check for exploration mappings
        explore_events = [k for k in agent.EVENT_TO_TOOL.keys() if 'explore' in k]
        if explore_events:
            print(f"✓ Found exploration mappings: {explore_events}")
        else:
            print("✗ No idea.explore.* mappings in EVENT_TO_TOOL (needs integration)")
            print("  Expected events: idea.explore.start, idea.explore.stop, etc.")

        # Show what IS mapped
        print(f"\n  Currently mapped events ({len(agent.EVENT_TO_TOOL)}):")
        for evt in sorted(agent.EVENT_TO_TOOL.keys())[:10]:
            print(f"    - {evt}")
        if len(agent.EVENT_TO_TOOL) > 10:
            print(f"    ... and {len(agent.EVENT_TO_TOOL) - 10} more")
        return bool(explore_events)
    except Exception as e:
        print(f"✗ Check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_tables():
    print("\n=== Test 4: Database Tables ===")
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), 'vibemind.db')
        if not os.path.exists(db_path):
            print(f"✗ Database not found: {db_path}")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]

        print(f"  Found {len(tables)} tables in database")

        exploration_tables = ['exploration_sessions', 'exploration_nodes', 'discovered_edges']
        found = 0
        for t in exploration_tables:
            if t in tables:
                print(f"✓ Table exists: {t}")
                found += 1
            else:
                print(f"✗ Missing table: {t} (needs migration)")

        # Show existing tables
        print(f"\n  Existing tables:")
        for t in sorted(tables):
            print(f"    - {t}")

        conn.close()
        return found == len(exploration_tables)
    except Exception as e:
        print(f"✗ DB check failed: {e}")
        return False

def test_intent_classification():
    print("\n=== Test 5: Intent Classification ===")
    try:
        from swarm.orchestrator.intent_classifier import IntentClassifier

        # Check if exploration events are in the prompt template
        classifier = IntentClassifier()

        # Look for exploration events in CLASSIFIER_PROMPT_TEMPLATE
        from swarm.orchestrator.intent_classifier import CLASSIFIER_PROMPT_TEMPLATE

        exploration_intents = [
            "idea.explore.start",
            "idea.explore.stop",
            "idea.explore.accept",
            "idea.explore.reject",
        ]

        found = []
        for intent in exploration_intents:
            if intent in CLASSIFIER_PROMPT_TEMPLATE:
                found.append(intent)
                print(f"✓ Intent defined: {intent}")
            else:
                print(f"✗ Intent missing: {intent}")

        return len(found) == len(exploration_intents)
    except Exception as e:
        print(f"✗ Check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_bubbles_exist():
    print("\n=== Test 6: Check Existing Bubbles ===")
    try:
        from data import IdeasRepository
        repo = IdeasRepository()
        ideas = repo.list(limit=20)

        # Filter top-level bubbles (no parent)
        bubbles = [i for i in ideas if not i.parent_id]
        child_ideas = [i for i in ideas if i.parent_id]

        print(f"✓ Found {len(bubbles)} bubbles and {len(child_ideas)} child ideas")

        if bubbles:
            print("\n  Bubbles:")
            for b in bubbles[:5]:
                desc = (b.description or "")[:50]
                print(f"    - {b.title}: {desc}...")

        return len(bubbles) > 0
    except Exception as e:
        print(f"✗ Check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("EXPLORATION SYSTEM STATUS CHECK")
    print("=" * 60)

    results = {
        "Exploration Module": test_exploration_module(),
        "Exploration Tools": test_exploration_tools(),
        "IdeasAgent Mappings": test_ideas_agent_mappings(),
        "Database Tables": test_database_tables(),
        "Intent Classification": test_intent_classification(),
        "Bubbles Exist": test_bubbles_exist(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed")

    if passed < total:
        print("\n  INTEGRATION NEEDED:")
        if not results["IdeasAgent Mappings"]:
            print("    - Add EVENT_TO_TOOL mappings in ideas_agent.py")
        if not results["Database Tables"]:
            print("    - Add exploration tables in database.py migration")
