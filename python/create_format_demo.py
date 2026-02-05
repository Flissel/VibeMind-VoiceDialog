"""
Create Format Demo bubble with all 11 format types.
"""
import sys
import os
import time

# Add python dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env from project root
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
print(f"Loaded .env from: {env_path}")
print(f"OPENROUTER_API_KEY: {'SET' if os.getenv('OPENROUTER_API_KEY') else 'NOT SET'}")

from tools.bubble_tools import create_bubble, enter_bubble, list_bubbles
from tools import bubble_tools
from tools.idea_tools import create_idea
from tools.format_dispatcher import (
    format_idea_note, format_idea_table, format_idea_action_list,
    format_idea_pros_cons, format_idea_hierarchy, format_idea_specs,
    format_idea_kanban, format_idea_mindmap, format_idea_swot,
    format_idea_user_story, format_idea_flowchart
)
from data import IdeasRepository

print("=" * 60)
print("  FORMAT DEMO CREATOR")
print("=" * 60)

# 1. Create bubble
print("\n[1] Creating 'Format Demo' bubble...")
result = create_bubble({'title': 'Format Demo', 'description': 'Test aller 11 Formattypen'})
print(f"    Result: {result[:100]}...")

# 2. Enter bubble - set context manually
print("\n[2] Entering 'Format Demo' bubble...")
repo = IdeasRepository()
bubble = repo.get_by_title_fuzzy('Format Demo')
if bubble:
    bubble_tools._current_bubble_db_id = bubble.id
    print(f"    Set current bubble: {bubble.id} ({bubble.title})")
else:
    print("    ERROR: Could not find Format Demo bubble!")
    sys.exit(1)

# 3. Create base ideas for each format
print("\n[3] Creating test ideas...")

test_content = """
Projektmanagement-App fuer Teams:
- Aufgabenverwaltung mit Deadlines
- Team-Kalender und Ressourcenplanung
- Echtzeit-Kollaboration
- Benachrichtigungen und Erinnerungen
- Reporting und Analytics
- Integration mit Slack und Email
- Mobile App fuer iOS und Android
- Offline-Modus
"""

formats = [
    ("Note Format", "note", format_idea_note),
    ("Table Format", "table", format_idea_table),
    ("Action List Format", "action_list", format_idea_action_list),
    ("Pros Cons Format", "pros_cons", format_idea_pros_cons),
    ("Hierarchy Format", "hierarchy", format_idea_hierarchy),
    ("Specs Format", "specs", format_idea_specs),
    ("Kanban Format", "kanban", format_idea_kanban),
    ("Mindmap Format", "mindmap", format_idea_mindmap),
    ("SWOT Format", "swot", format_idea_swot),
    ("User Story Format", "user_story", format_idea_user_story),
    ("Flowchart Format", "flowchart", format_idea_flowchart),
]

created_ideas = []

for title, fmt, func in formats:
    print(f"\n    Creating idea: {title}...")
    result = create_idea({
        'title': title,
        'content': test_content,
        'type': 'note'
    })
    print(f"    Created: {result[:80]}...")
    created_ideas.append((title, fmt, func))

# 4. Apply format conversions
print("\n" + "=" * 60)
print("  APPLYING FORMAT CONVERSIONS (LLM calls)")
print("=" * 60)

for title, fmt, format_func in created_ideas:
    print(f"\n[FORMAT] {title} -> {fmt}")
    start = time.time()
    try:
        result = format_func({'idea_name': title})
        elapsed = time.time() - start
        if 'success' in result.lower() or 'erfolgreich' in result.lower() or 'formatiert' in result.lower():
            print(f"    OK ({elapsed:.1f}s)")
        else:
            print(f"    Result: {result[:100]}...")
    except Exception as e:
        print(f"    ERROR: {e}")

print("\n" + "=" * 60)
print("  DONE - Check Electron UI for rendered formats")
print("=" * 60)
