#!/usr/bin/env python3
"""
Analyze existing VibeMind database schema
"""

import sqlite3
import os

def analyze_database():
    db_path = 'vibemind.db'
    if not os.path.exists(db_path):
        print('Database file not found')
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table";')
    tables = cursor.fetchall()

    print('Existing database tables:')
    for table in tables:
        table_name = table[0]
        print(f'  - {table_name}')

        # Get table schema
        cursor.execute(f'PRAGMA table_info({table_name})')
        columns = cursor.fetchall()
        if columns:
            print('    Columns:')
            for col in columns:
                col_name, col_type, not_null, default, pk = col[1], col[2], col[3], col[4], col[5]
                constraints = []
                if pk: constraints.append('PRIMARY KEY')
                if not_null: constraints.append('NOT NULL')
                constraint_str = f" ({', '.join(constraints)})" if constraints else ""
                print(f'      {col_name} ({col_type}){constraint_str}')
        print()

    conn.close()

if __name__ == "__main__":
    analyze_database()