"""Persistent memory layer using SQLite.

Stores chat history, face recognition logs, and system state
so everything survives server restarts.
"""
import os
import json
import sqlite3
import threading
from datetime import datetime


class MemoryStore:
    """Thread-safe SQLite-backed persistence for the AI Command Center."""

    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "memory.db")

        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
        print(f"💾 MemoryStore initialized: {self.db_path}")

    def _get_conn(self):
        """Get a thread-local SQLite connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            # self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA journal_mode=DELETE")

        return self._local.conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS face_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracker_id INTEGER,
                name TEXT,
                is_authorized INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                area TEXT NOT NULL DEFAULT 'default',
                plant TEXT NOT NULL DEFAULT 'Plant 1',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                zone_a TEXT,
                zone_b TEXT,
                people_limit INTEGER DEFAULT 0,
                homography_matrix TEXT
            );
        """)
        
        # Add columns if they don't exist (for existing DBs)
        try:
            conn.execute("ALTER TABLE cameras ADD COLUMN zone_a TEXT")
            conn.execute("ALTER TABLE cameras ADD COLUMN zone_b TEXT")
        except sqlite3.OperationalError:
            pass # Columns already exist

        try:
            conn.execute("ALTER TABLE cameras ADD COLUMN people_limit INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Column already exists

        try:
            conn.execute("ALTER TABLE cameras ADD COLUMN plant TEXT NOT NULL DEFAULT 'Plant 1'")
        except sqlite3.OperationalError:
            pass # Column already exists

        try:
            conn.execute("ALTER TABLE cameras ADD COLUMN homography_matrix TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists

        conn.commit()

    # =========================================================================
    # CHAT HISTORY
    # =========================================================================

    def save_chat(self, role, content):
        """Save a chat message (role = 'user' or 'assistant')."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, datetime.now().isoformat())
        )
        conn.commit()

    def get_chat_history(self, limit=20):
        """Return the last N chat messages as a list of dicts."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        # Reverse so oldest is first (chronological order)
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]

    def clear_chat_history(self):
        """Clear all chat history."""
        conn = self._get_conn()
        conn.execute("DELETE FROM chat_history")
        conn.commit()

    # =========================================================================
    # FACE RECOGNITION LOG
    # =========================================================================

    def log_face_event(self, tracker_id, name, is_authorized):
        """Log a face recognition event."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO face_log (tracker_id, name, is_authorized, timestamp) VALUES (?, ?, ?, ?)",
            (int(tracker_id), name or "", 1 if is_authorized else 0, datetime.now().isoformat())
        )
        conn.commit()

    def get_face_history(self, limit=50):
        """Return the last N face recognition events."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT tracker_id, name, is_authorized, timestamp FROM face_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{
            "tracker_id": r["tracker_id"],
            "name": r["name"],
            "is_authorized": bool(r["is_authorized"]),
            "timestamp": r["timestamp"]
        } for r in rows]

    def get_face_summary(self):
        """Return summary stats for face recognition."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM face_log").fetchone()[0]
        authorized = conn.execute("SELECT COUNT(*) FROM face_log WHERE is_authorized = 1").fetchone()[0]
        unauthorized = total - authorized
        unique_names = conn.execute(
            "SELECT DISTINCT name FROM face_log WHERE is_authorized = 1 AND name != ''"
        ).fetchall()
        return {
            "total_scans": total,
            "authorized": authorized,
            "unauthorized": unauthorized,
            "known_people": [r["name"] for r in unique_names]
        }

    # =========================================================================
    # SYSTEM STATE PERSISTENCE
    # =========================================================================

    def save_state(self, key, value):
        """Save a key-value pair (value is JSON-serialized)."""
        conn = self._get_conn()
        json_value = json.dumps(value)
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json_value, datetime.now().isoformat())
        )
        conn.commit()

    def load_state(self, key, default=None):
        """Load a value by key, returning default if not found."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM system_state WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row["value"])
        return default

    def save_all_state(self, state_dict):
        """Save multiple key-value pairs at once."""
        conn = self._get_conn()
        now = datetime.now().isoformat()
        for key, value in state_dict.items():
            conn.execute(
                "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), now)
            )
        conn.commit()

    def load_all_state(self):
        """Load all saved state as a dict."""
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM system_state").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # =========================================================================
    # CAMERA MANAGEMENT
    # =========================================================================

    def add_camera(self, name, url, area="default", plant="Plant 1"):
        """Add a new camera. Returns the new camera's ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO cameras (name, url, area, plant, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, url, area, plant, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid

    def get_cameras(self, active_only=True):
        """Return all cameras as a list of dicts."""
        conn = self._get_conn()
        query = "SELECT id, name, url, area, plant, is_active, created_at, zone_a, zone_b, people_limit, homography_matrix FROM cameras"
        if active_only:
            query += " WHERE is_active = 1"
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]

    def get_camera(self, camera_id):
        """Return a single camera by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, name, url, area, plant, is_active, created_at, zone_a, zone_b, people_limit, homography_matrix FROM cameras WHERE id = ?",
            (camera_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_camera(self, camera_id, name=None, url=None, area=None, plant=None, is_active=None):
        """Update specific fields of a camera."""
        conn = self._get_conn()
        updates = {}
        if name is not None:
            updates["name"] = name
        if url is not None:
            updates["url"] = url
        if area is not None:
            updates["area"] = area
        if plant is not None:
            updates["plant"] = plant
        if is_active is not None:
            updates["is_active"] = 1 if is_active else 0
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE cameras SET {set_clause} WHERE id = ?",
            list(updates.values()) + [camera_id]
        )
        conn.commit()
        return True

    def update_camera_zones(self, camera_id, zone_a_list, zone_b_list):
        """Update the zone configurations for a specific camera."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE cameras SET zone_a = ?, zone_b = ? WHERE id = ?",
            (json.dumps(zone_a_list), json.dumps(zone_b_list), camera_id)
        )
        conn.commit()
        return True

    def update_camera_homography(self, camera_id, matrix):
        """Update the homography matrix for a specific camera."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE cameras SET homography_matrix = ? WHERE id = ?",
            (json.dumps(matrix), camera_id)
        )
        conn.commit()
        return True

    def delete_camera(self, camera_id):
        """Delete a camera permanently."""
        conn = self._get_conn()
        conn.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        conn.commit()
        return True

    def get_areas(self):
        """Return a list of distinct area names."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT area FROM cameras WHERE is_active = 1"
        ).fetchall()
        return [r["area"] for r in rows]

    def get_area_limits(self):
        """Return a dict of {area_name: people_limit} based on active cameras.
        If cameras in the same area have differing limits, we take the max."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT area, MAX(people_limit) as max_limit FROM cameras WHERE is_active = 1 GROUP BY area"
        ).fetchall()
        limits = {}
        for r in rows:
            limits[r["area"]] = r["max_limit"] or 0
        return limits

    def update_area_limit(self, area, people_limit):
        """Update the people_limit for all cameras in the specified area."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE cameras SET people_limit = ? WHERE area = ?",
            (int(people_limit), area)
        )
        conn.commit()
        return True

