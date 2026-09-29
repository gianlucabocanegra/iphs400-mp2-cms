"""Users: argon2 hashing, authentication, and Deactivation.

Users are never deleted, only Deactivated (see CONTEXT.md).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app import db

_hasher = PasswordHasher()
# Verified against when the email is unknown, so a miss costs as much as a hit.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def create_user(conn: sqlite3.Connection, *, name: str, email: str,
                password: str, role: str) -> None:
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, email.strip(), _hasher.hash(password), role,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def authenticate(conn: sqlite3.Connection, email: str,
                 password: str) -> sqlite3.Row | None:
    """The active User with this email and password, else None (never says why)."""
    user = conn.execute("SELECT * FROM users WHERE email = ?",
                        (email.strip(),)).fetchone()
    stored = user["password_hash"] if user else _DUMMY_HASH
    try:
        _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return None
    if user is None or not user["active"]:
        return None
    return user


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def end_sessions(conn: sqlite3.Connection, user_id: int) -> None:
    """Invalidate every session cookie issued to this User."""
    conn.execute("UPDATE users SET session_version = session_version + 1 "
                 "WHERE id = ?", (user_id,))
    conn.commit()


def set_active(path: Path | str, email: str, active: bool) -> None:
    """Deactivate or reactivate a User. Their content and authorship stay put."""
    conn = db.connect(path)
    try:
        conn.execute("UPDATE users SET active = ? WHERE email = ?",
                     (int(active), email.strip()))
        conn.commit()
    finally:
        conn.close()


def seed_users(path: Path | str, *, admin_password: str, editor_password: str,
               admin_email: str = "admin@example.test",
               editor_email: str = "editor@example.test") -> None:
    """Create the first Admin and Editor. Existing emails are left alone."""
    db.init_db(path)
    conn = db.connect(path)
    try:
        for name, email, password, role in (
            ("Demo Admin", admin_email, admin_password, "admin"),
            ("Demo Editor", editor_email, editor_password, "editor"),
        ):
            exists = conn.execute("SELECT 1 FROM users WHERE email = ?",
                                  (email,)).fetchone()
            if not exists:
                create_user(conn, name=name, email=email, password=password,
                            role=role)
    finally:
        conn.close()
