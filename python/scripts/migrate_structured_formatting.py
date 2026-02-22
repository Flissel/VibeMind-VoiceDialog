#!/usr/bin/env python3
"""
Migration script for structured formatting fields.
Adds format_schema, content_json, and last_formatted columns to canvas_nodes table.
"""

import sqlite3
import os
from pathlib import Path

def run_migration():
    # Database path
    db_path = Path('vibemind.db')
    if not db_path.exists():
        print('Database not found')
        return False

    # Read migration
    migration_path = Path('data/migrations/014_structured_formatting.sql')
    with open(migration_path, 'r') as f:
        migration_sql = f.read()

    # Execute migration
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(migration_sql)
        conn.commit()
        print('Migration 014 executed successfully')

        # Verify columns were added
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(canvas_nodes)')
        columns = [row[1] for row in cursor.fetchall()]

        required_cols = ['format_schema', 'content_json', 'last_formatted']
        missing = [col for col in required_cols if col not in columns]

        if missing:
            print(f'ERROR: Missing columns: {missing}')
            return False
        else:
            print('All required columns added successfully')
            return True

    except Exception as e:
        print(f'Migration failed: {e}')
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    success = run_migration()
    exit(0 if success else 1)