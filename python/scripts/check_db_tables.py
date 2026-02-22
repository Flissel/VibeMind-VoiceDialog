import sqlite3
import os

db_path = os.path.join('..', 'vibemind.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
rows = cursor.fetchall()

print('Available tables:')
for row in rows:
    print(f'  {row[0]}')

conn.close()
