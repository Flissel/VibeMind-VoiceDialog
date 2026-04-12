"""Test vibemind_db_mcp.py write tools against Supabase."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from vibemind_db_mcp import handle_tool

def test(name, args):
    result = handle_tool(name, args)
    print(f"  {name}: {result[:150]}")
    return result

print("=== Supabase MCP Write Tests ===\n")

# 1. Create idea
print("1. Create idea:")
r = test("db_ideas_create", {"title": "OpenFang Integration Test", "description": "Created via MCP", "source": "test"})

# 2. List ideas
print("\n2. List ideas:")
test("db_ideas_list", {"limit": 5})

# 3. Create project
print("\n3. Create project:")
test("db_projects_create", {"name": "Test Project", "tech_stack": "Python + Rust"})

# 4. Create canvas node
print("\n4. Create canvas node:")
test("db_canvas_create", {"title": "Test Node", "node_type": "note", "content": "Created by MCP test"})

# 5. Flowzen checkin
print("\n5. Flowzen checkin:")
test("db_flowzen_checkin", {"mood": "focused", "energy": 8, "notes": "MCP test"})

# 6. Generic insert
print("\n6. Generic insert (flowzen_activity):")
test("db_insert", {"table": "flowzen_activity", "data": {"event_type": "test.mcp", "time_window": "evening", "hour": 20}})

# 7. Schema
print("\n7. Schema (row counts):")
test("db_schema", {})

print("\n=== Done ===")
