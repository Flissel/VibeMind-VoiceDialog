"""Test the flexible format system end-to-end."""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("VibeMind Format System Test")
print("=" * 60)

# 1. Test format schemas
print("\n1. Testing format schemas...")
from data.format_schemas import FORMAT_SCHEMAS, DEFAULT_FORMAT, get_format_schema

print(f"   Default format: {DEFAULT_FORMAT}")
print(f"   Available formats: {list(FORMAT_SCHEMAS.keys())}")

try:
    note_schema = get_format_schema("note")
    print(f"   note schema type: {note_schema.get('properties', {}).get('type', {})}")
    print("   [OK] Format schemas loaded")
except Exception as e:
    print(f"   [FAIL] {e}")

# 2. Test database migration
print("\n2. Testing database migration...")
from data.database import get_database

db = get_database()
version = db.get_schema_version()
print(f"   Schema version: {version}")

result = db.fetch_all('PRAGMA table_info(canvas_nodes)')
col_names = [col[1] for col in result]
format_cols = ['format_schema', 'content_json', 'last_formatted']

all_present = all(fc in col_names for fc in format_cols)
print(f"   Format columns present: {all_present}")
if all_present:
    print("   [OK] Migration applied")
else:
    missing = [fc for fc in format_cols if fc not in col_names]
    print(f"   [FAIL] Missing columns: {missing}")

# 3. Test format dispatcher import
print("\n3. Testing format dispatcher...")
try:
    from tools.format_dispatcher import (
        FORMAT_AGENTS,
        convert_format,
        list_available_formats,
        format_as_note,
        format_as_table,
        format_as_action_list,
        format_as_pros_cons,
        format_as_hierarchy,
        format_as_specs,
    )
    print(f"   Format agents: {list(FORMAT_AGENTS.keys())}")
    print("   [OK] Format dispatcher loaded")
except Exception as e:
    print(f"   [FAIL] {e}")

# 4. Test list_available_formats
print("\n4. Testing list_available_formats...")
try:
    result = list_available_formats({})
    print(f"   Result preview: {result[:100]}...")
    print("   [OK] list_available_formats works")
except Exception as e:
    print(f"   [FAIL] {e}")

# 5. Test format agent (note)
print("\n5. Testing format_as_note...")
try:
    source = {"type": "table", "title": "Test", "headers": ["A", "B"], "rows": [["1", "2"]]}
    result = format_as_note(source, "Test Note")
    print(f"   Output type: {result.get('type')}")
    print(f"   Has text: {'text' in result}")
    print("   [OK] format_as_note works")
except Exception as e:
    print(f"   [FAIL] {e}")

# 6. Test IdeasAgent EVENT_TO_TOOL mapping
print("\n6. Testing IdeasAgent mappings...")
try:
    from swarm.backend_agents.ideas_agent import IdeasAgent

    format_events = [
        "idea.format_note", "idea.format_action_list", "idea.format_pros_cons",
        "idea.format_hierarchy", "idea.format_specs", "idea.convert_format",
        "idea.list_formats"
    ]

    agent = IdeasAgent()
    missing = []
    for event in format_events:
        if event not in agent.EVENT_TO_TOOL:
            missing.append(event)

    if missing:
        print(f"   [FAIL] Missing events: {missing}")
    else:
        print(f"   All {len(format_events)} format events mapped")
        print("   [OK] IdeasAgent mappings complete")
except Exception as e:
    print(f"   [FAIL] {e}")

# 7. Test event router
print("\n7. Testing EventRouter mappings...")
try:
    from swarm.event_team.event_router import get_event_router

    router = get_event_router()
    all_correct = True
    for event in format_events:
        stream = router.get_stream(event)
        if stream != "events:tasks:ideas":
            print(f"   [FAIL] {event} -> {stream} (should be events:tasks:ideas)")
            all_correct = False

    if all_correct:
        print(f"   All {len(format_events)} events route to events:tasks:ideas")
        print("   [OK] EventRouter mappings correct")
except Exception as e:
    print(f"   [FAIL] {e}")

# 8. Test intent rules
print("\n8. Testing intent rules...")
try:
    from data.intent_rule_repository import INITIAL_INTENT_RULES

    format_intents = [
        "idea.format_note", "idea.format_action_list", "idea.format_pros_cons",
        "idea.format_hierarchy", "idea.format_specs", "idea.convert_format",
        "idea.list_formats"
    ]

    existing_intents = [rule["intent_type"] for rule in INITIAL_INTENT_RULES]
    missing = [i for i in format_intents if i not in existing_intents]

    if missing:
        print(f"   [FAIL] Missing intent rules: {missing}")
    else:
        print(f"   All {len(format_intents)} format intent rules exist")
        print("   [OK] Intent rules complete")
except Exception as e:
    print(f"   [FAIL] {e}")

# Summary
print("\n" + "=" * 60)
print("Format System Test Complete")
print("=" * 60)
print("\nTo test voice commands, start the Electron app and try:")
print("  - 'Formatiere als Aufgabenliste'")
print("  - 'Erstelle Pro-Contra-Liste'")
print("  - 'Formatiere als Gliederung'")
print("  - 'Welche Formate gibt es?'")
