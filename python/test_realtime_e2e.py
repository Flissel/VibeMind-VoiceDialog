"""E2E Test: Write to Supabase via MCP, verify it appears in PostgREST."""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from vibemind_db_mcp import handle_tool

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:54321")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0")


def query_supabase(table, filters=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*&{filters}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    resp = urllib.request.urlopen(req, timeout=5)
    return json.loads(resp.read().decode())


print("=== E2E: MCP Write -> Supabase Verify ===\n")

# 1. Create idea via MCP
title = f"E2E Test {int(time.time())}"
result = handle_tool("db_ideas_create", {"title": title, "description": "Realtime test", "source": "e2e-test"})
created = json.loads(result)
idea_id = created["created"][0]["id"]
print(f"1. Created idea: {title} (id={idea_id[:12]}...)")

# 2. Verify it exists in Supabase via direct REST query
rows = query_supabase("ideas", f"id=eq.{idea_id}")
assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
assert rows[0]["title"] == title
print(f"2. Verified in Supabase: title='{rows[0]['title']}' -- OK")

# 3. Update via MCP
handle_tool("db_ideas_update", {"id": idea_id, "status": "scored", "description": "Updated by E2E"})
rows2 = query_supabase("ideas", f"id=eq.{idea_id}")
assert rows2[0]["status"] == "scored"
assert rows2[0]["description"] == "Updated by E2E"
print(f"3. Updated status to 'scored' -- OK")

# 4. Generic insert
handle_tool("db_insert", {"table": "flowzen_activity", "data": {"event_type": "e2e.test", "hour": 12}})
fa = query_supabase("flowzen_activity", "event_type=eq.e2e.test")
assert len(fa) >= 1
print(f"4. Generic insert flowzen_activity -- OK")

# 5. Delete via MCP
handle_tool("db_ideas_delete", {"id": idea_id})
rows3 = query_supabase("ideas", f"id=eq.{idea_id}")
assert len(rows3) == 0
print(f"5. Deleted idea -- OK")

print(f"\n=== ALL TESTS PASSED ===")
print(f"\nWhen Electron runs with USE_SUPABASE_REALTIME=true,")
print(f"each of these writes would trigger a Realtime event")
print(f"-> supabase-realtime.js -> python-message IPC -> renderer update")
