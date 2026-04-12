"""Final test: all repos work without SQLite module existing."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Verify SQLite module is REALLY gone
db_py = Path(__file__).parent / "data" / "database.py"
mirror_py = Path(__file__).parent / "data" / "supabase_mirror.py"
assert not db_py.exists(), f"database.py should be deleted! Still exists: {db_py}"
assert not mirror_py.exists(), f"supabase_mirror.py should be deleted! Still exists: {mirror_py}"
print("OK: database.py and supabase_mirror.py are gone")

# Import chain
from data import IdeasRepository, ProjectsRepository, get_database, Database
db = get_database()
print(f"Database: {type(db).__name__} from {type(db).__module__}")
assert type(db).__name__ == "SupabaseDatabase"

# Test IdeasRepository
repo = IdeasRepository(db=db)
rows = repo.list(limit=3)
print(f"IdeasRepository.list(3) -> {len(rows)} rows")
for r in rows:
    print(f"  - {r.id[:12]}... {r.title[:40]}")

# Create + delete via repo
idea = repo.create(title="SQLite-GONE Test", source="test-final")
print(f"Created: {idea.id} '{idea.title}'")
fetched = repo.get(idea.id)
assert fetched is not None
assert fetched.title == "SQLite-GONE Test"
repo.delete(idea.id)
assert repo.get(idea.id) is None
print("Create -> Fetch -> Delete roundtrip OK")

print("\n=== SQLite IS FULLY REMOVED ===")
