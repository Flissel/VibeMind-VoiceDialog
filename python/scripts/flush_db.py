#!/usr/bin/env python3
"""
VibeMind Database Flush Script

Clears all data from the database while preserving the schema.
Tables are deleted in the correct order to respect foreign key constraints.

Usage:
    python flush_db.py           # Clear all data
    python flush_db.py --confirm # Skip confirmation prompt
    python flush_db.py --reset   # Also reset schema version
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from data.database import get_database, reset_database


def flush_database(confirm: bool = False, reset_schema: bool = False) -> dict:
    """
    Flush all data from the database.
    
    Deletes data in FK-safe order:
    1. canvas_edges (FK to canvas_nodes)
    2. canvas_nodes (FK to ideas, projects)
    3. conversation_history (FK to conversation_sessions)
    4. conversation_sessions
    5. projects (FK to ideas)
    6. ideas
    
    Args:
        confirm: Skip confirmation prompt
        reset_schema: Also reset schema version to trigger re-migration
    
    Returns:
        dict: Count of deleted rows per table
    """
    if not confirm:
        print("\n⚠️  WARNING: This will delete ALL data from the database!")
        print("    - All ideas (bubbles)")
        print("    - All projects")
        print("    - All canvas nodes and edges")
        print("    - All conversation history")
        response = input("\nType 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("Aborted.")
            return {}
    
    db = get_database()
    stats = {}
    
    # Order matters! Delete in FK-safe order
    tables_order = [
        "canvas_edges",
        "canvas_nodes", 
        "conversation_history",
        "conversation_sessions",
        "projects",
        "ideas",
    ]
    
    print("\n🗑️  Flushing database...")
    
    with db.connection() as conn:
        # Temporarily disable FK checks for bulk delete
        conn.execute("PRAGMA foreign_keys=OFF")
        
        for table in tables_order:
            try:
                # Count before delete
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                
                # Delete all rows
                conn.execute(f"DELETE FROM {table}")
                
                stats[table] = count
                print(f"   ✅ {table}: {count} rows deleted")
            except Exception as e:
                print(f"   ❌ {table}: Error - {e}")
                stats[table] = f"Error: {e}"
        
        # Reset schema version if requested
        if reset_schema:
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version (version) VALUES (0)")
            print("   🔄 Schema version reset to 0")
        
        # Re-enable FK checks
        conn.execute("PRAGMA foreign_keys=ON")
        
        conn.commit()
    
    print("\n✅ Database flushed successfully!")
    print(f"   Total rows deleted: {sum(v for v in stats.values() if isinstance(v, int))}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Flush VibeMind database")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--reset", action="store_true", help="Also reset schema version")
    
    args = parser.parse_args()
    
    flush_database(confirm=args.confirm, reset_schema=args.reset)


if __name__ == "__main__":
    main()