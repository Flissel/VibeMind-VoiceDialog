"""Run database migration to add exploration tables."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from data.database import get_database, reset_database

# Reset to force re-initialization with new schema
print("Resetting database connection...")
reset_database()

# Get fresh database instance - this triggers migrations
print("Running migrations...")
db = get_database()
version = db.get_schema_version()
print(f"Database schema version: {version}")

# Check if exploration tables exist
tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
print(f"\nTables ({len(tables)}):")
for t in tables:
    name = t[0]
    if 'exploration' in name or 'discovered' in name:
        print(f"  ✓ {name} (NEW)")
    else:
        print(f"  - {name}")

# Verify exploration tables
exploration_tables = ['exploration_sessions', 'exploration_nodes', 'discovered_edges']
missing = [t for t in exploration_tables if t not in [row[0] for row in tables]]

if missing:
    print(f"\n✗ Missing tables: {missing}")
else:
    print(f"\n✓ All exploration tables created successfully!")
