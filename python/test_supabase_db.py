"""Test SupabaseDatabase adapter against live Supabase."""
import os
os.environ["USE_SUPABASE_DB"] = "true"

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data.supabase_database import SupabaseDatabase

db = SupabaseDatabase()

print("=== Test 1: SELECT COUNT(*) ===")
row = db.fetch_one("SELECT COUNT(*) FROM ideas")
print(f"  ideas count: {row[0]} (type={type(row).__name__})")
assert row[0] >= 0

print("\n=== Test 2: INSERT ===")
cursor = db.execute(
    "INSERT INTO ideas (id, title, description, source, created_at, score, status, promoted_to_project_id, tags, metadata, parent_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    ("phase5test", "Phase5 Adapter Test", "Created via SupabaseDatabase adapter", "test", "2026-04-12T16:00:00", 0.0, "raw", None, "[]", "{}", None),
)
print(f"  lastrowid: {cursor.lastrowid}")

print("\n=== Test 3: SELECT by id ===")
row = db.fetch_one("SELECT * FROM ideas WHERE id = ?", ("phase5test",))
if row:
    print(f"  id={row['id']} title={row['title']}")
    print(f"  row[0] (positional) = {row[0]}")
    print(f"  dict access: row['source'] = {row['source']}")
else:
    print("  ERROR: row not found")

print("\n=== Test 4: UPDATE ===")
db.execute(
    "UPDATE ideas SET title = ?, description = ?, source = ?, score = ?, status = ?, promoted_to_project_id = ?, tags = ?, metadata = ?, parent_id = ? WHERE id = ?",
    ("Phase5 UPDATED", "After update", "test", 5.5, "scored", None, "[]", "{}", None, "phase5test"),
)
row = db.fetch_one("SELECT * FROM ideas WHERE id = ?", ("phase5test",))
print(f"  title={row['title']}, score={row['score']}, status={row['status']}")
assert row["title"] == "Phase5 UPDATED"

print("\n=== Test 5: LIST with ORDER BY + LIMIT ===")
rows = db.fetch_all(
    "SELECT * FROM ideas WHERE status = ? ORDER BY created_at DESC LIMIT 5",
    ("raw",)
)
print(f"  got {len(rows)} rows")
for r in rows[:3]:
    print(f"  - {r['id'][:12]}... {r['title'][:50]}")

print("\n=== Test 6: DELETE ===")
db.execute("DELETE FROM ideas WHERE id = ?", ("phase5test",))
row = db.fetch_one("SELECT * FROM ideas WHERE id = ?", ("phase5test",))
print(f"  after delete: {row}")
assert row is None

print("\n=== Test 7: LIKE search ===")
rows = db.fetch_all("SELECT * FROM ideas WHERE LOWER(title) LIKE LOWER(?) LIMIT 3", ("%Test%",))
print(f"  LIKE %Test% found {len(rows)} rows")

print("\n=== Test 8: IS NULL ===")
rows = db.fetch_all("SELECT * FROM ideas WHERE parent_id IS NULL LIMIT 3")
print(f"  IS NULL found {len(rows)} rows")

print("\n=== ALL TESTS PASSED ===")
