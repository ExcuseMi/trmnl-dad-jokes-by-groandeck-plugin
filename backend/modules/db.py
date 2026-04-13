import logging
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv('DB_PATH', '/data/jokes.db')
MAX_CACHED = 1000

log = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jokes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                setup       TEXT NOT NULL,
                punchline   TEXT NOT NULL,
                explanation TEXT,
                fetched_at  REAL DEFAULT (unixepoch())
            )
        """)
    log.info('SQLite joke cache ready at %s', DB_PATH)


def save_jokes(jokes: list[dict]):
    with _conn() as conn:
        conn.executemany(
            "INSERT INTO jokes (setup, punchline, explanation) VALUES (?, ?, ?)",
            [(j.get('setup', ''), j.get('punchline', ''), j.get('explanation', '')) for j in jokes],
        )
        conn.execute(f"""
            DELETE FROM jokes WHERE id NOT IN (
                SELECT id FROM jokes ORDER BY id DESC LIMIT {MAX_CACHED}
            )
        """)


def get_random_jokes(n: int) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT setup, punchline, explanation FROM jokes ORDER BY RANDOM() LIMIT ?", (n,)
        ).fetchall()
    return [{'setup': r[0], 'punchline': r[1], 'explanation': r[2]} for r in rows]
