import sqlite3
import os

db_path = 'data/memory.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, is_active FROM cameras")
    rows = cursor.fetchall()
    print(f"Total cameras in DB: {len(rows)}")
    for row in rows:
        print(f"ID: {row['id']} | Name: {row['name']} | Active: {row['is_active']} | URL: {row['url'][:30]}...")
    conn.close()
