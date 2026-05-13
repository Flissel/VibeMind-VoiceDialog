"""Test IdeasRepository via SupabaseDatabase (no SQLite touch)."""
import os
os.environ["USE_SUPABASE_DB"] = "true"
os.environ["USE_SUPABASE_MIRROR"] = "false"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data import get_database, Database
from data.ideas_repository import IdeasRepository

print(f"Database class: {Database.__module__}.{Database.__name__}")
db = get_database()
print(f"Backend: {type(db).__name__}")
print(f"db.db_path: {db.db_path}")

repo = IdeasRepository(db=db)

print("\n=== Create idea via repo ===")
idea = repo.create(
    title="Repo Test via Supabase",
    description="IdeasRepository -> SupabaseDatabase -> PostgREST",
    source="test",
    tags=["test", "phase5"],
)
print(f"  created id={idea.id} title={idea.title}")

print("\n=== Fetch by id ===")
fetched = repo.get(idea.id)
print(f"  got title={fetched.title if fetched else 'NONE'}")
assert fetched is not None
assert fetched.title == idea.title

print("\n=== List ===")
rows = repo.list(limit=5)
print(f"  list(limit=5) -> {len(rows)} rows")
for r in rows[:3]:
    print(f"  - {r.id[:12]}... {r.title[:50]}")

print("\n=== Count ===")
n = repo.count()
print(f"  total ideas: {n}")

print("\n=== Update ===")
idea.title = "Repo Test UPDATED"
idea.description = "After update"
repo.update(idea)
fetched = repo.get(idea.id)
print(f"  updated title: {fetched.title}")
assert fetched.title == "Repo Test UPDATED"

print("\n=== Delete ===")
repo.delete(idea.id)
fetched = repo.get(idea.id)
print(f"  after delete: {fetched}")
assert fetched is None

print("\n=== ALL REPO TESTS PASSED ===")
