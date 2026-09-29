"""SQLite access. No ORM (ADR-002): a connection per request, plain SQL."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('admin', 'editor')),
    active          INTEGER NOT NULL DEFAULT 1,
    session_version INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id                INTEGER PRIMARY KEY,
    kind              TEXT    NOT NULL CHECK (kind IN ('news', 'event', 'menu')),
    title             TEXT    NOT NULL,
    slug              TEXT    NOT NULL,
    body_md           TEXT    NOT NULL DEFAULT '',
    status            TEXT    NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft', 'published')),
    author_id         INTEGER NOT NULL REFERENCES users (id),
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    first_published_at TEXT,
    UNIQUE (kind, slug)
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    # Sync FastAPI dependencies and endpoints may run on different threads.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
