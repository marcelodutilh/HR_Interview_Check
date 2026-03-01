import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jobsearch.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS job_searches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            job_search_id INTEGER NOT NULL REFERENCES job_searches(id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            notes         TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rubrics (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            job_search_id INTEGER NOT NULL REFERENCES job_searches(id) ON DELETE CASCADE,
            competencies  TEXT NOT NULL DEFAULT '[]',
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS interviews (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            transcript   TEXT,
            ai_analysis  TEXT,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


def get_setting(key):
    """Return the value for a setting, or None if not set."""
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    """Store or update a setting. Value must be a string."""
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
