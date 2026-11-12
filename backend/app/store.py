import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "onboarding.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding (
  id INTEGER PRIMARY KEY,
  token TEXT UNIQUE,
  name TEXT, employment TEXT, job_family TEXT,
  project TEXT, start_date TEXT,
  starter_email TEXT, personal_email TEXT,
  work_email TEXT, bitbucket_user TEXT,
  want_claude INTEGER DEFAULT 1,
  manual INTEGER DEFAULT 0,      -- 1 = demo tour hire: tickets resolve only when the tour says so
  created_at REAL
);
CREATE TABLE IF NOT EXISTS step (
  id INTEGER PRIMARY KEY,
  onboarding_id INTEGER, step_id TEXT, state TEXT,
  ticket_id INTEGER, updated_at REAL
);
CREATE TABLE IF NOT EXISTS mock_ticket (
  id INTEGER PRIMARY KEY,
  subject TEXT, description TEXT, email TEXT,
  created_at REAL, resolve_at REAL, forced INTEGER DEFAULT 0
);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.executescript(SCHEMA)
    try:                                   # older DB files: add the column if it is missing
        conn.execute("ALTER TABLE onboarding ADD COLUMN manual INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn
