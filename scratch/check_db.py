import sqlite3
import os

db_path = "d:/Work/Projects/headcount/data/memory.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name, area FROM cameras").fetchall()
    for r in rows:
        print(f"ID: {r['id']}, Name: {r['name']}, Area: {r['area']}")
    conn.close()
else:
    print("Database not found")
