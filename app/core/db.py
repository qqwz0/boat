import sqlite3
import time
from pathlib import Path


class EventLog:
    """SQLite-backed log of control commands, boat events, and update history."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS update_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                commit_hash TEXT,
                status TEXT NOT NULL,
                detail TEXT
            )
            """
        )
        self._conn.commit()

    def log_event(self, event_type: str, detail: str = "") -> None:
        """Records a control/boat event (e.g. control, release_bait, emergency_stop)."""
        self._conn.execute(
            "INSERT INTO events (ts, event_type, detail) VALUES (?, ?, ?)",
            (time.time(), event_type, detail),
        )
        self._conn.commit()

    def log_update(self, commit_hash: str, status: str, detail: str = "") -> None:
        """Records the outcome of a self-update attempt (status: ok/rolled_back/failed)."""
        self._conn.execute(
            "INSERT INTO update_history (ts, commit_hash, status, detail) VALUES (?, ?, ?, ?)",
            (time.time(), commit_hash, status, detail),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 50) -> list[tuple]:
        """Returns the most recent (ts, event_type, detail) rows, newest first."""
        cur = self._conn.execute(
            "SELECT ts, event_type, detail FROM events ORDER BY id DESC LIMIT ?", (limit,)
        )
        return cur.fetchall()

    def close(self) -> None:
        self._conn.close()
