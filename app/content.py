"""Posts: creation, editing, Slugs and the list. Shared by the console and Export."""
from __future__ import annotations

import re
import sqlite3
import unicodedata

from app.timeutil import utc_now

KINDS = ("news", "event", "menu")


class PostError(ValueError):
    """A problem with what the User typed, worded for the form."""


def slugify(text: str) -> str:
    """Lower-case ASCII, accents stripped, hyphens between words."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _taken(conn: sqlite3.Connection, kind: str, slug: str,
           except_id: int | None) -> bool:
    return conn.execute("SELECT 1 FROM posts WHERE kind = ? AND slug = ? AND id IS NOT ?",
                        (kind, slug, except_id)).fetchone() is not None


def _slug_for(conn: sqlite3.Connection, kind: str, title: str, typed: str,
              except_id: int | None = None) -> str:
    """A typed Slug must be free; a generated one gets -2, -3, ... until it is."""
    if typed.strip():
        slug = slugify(typed)
        if not slug:
            raise PostError("The slug needs letters or numbers.")
        if _taken(conn, kind, slug, except_id):
            raise PostError(f"The slug “{slug}” is already used by another post of this kind.")
        return slug
    base = slugify(title)
    if not base:
        raise PostError("The title needs letters or numbers to make a slug from.")
    slug, n = base, 1
    while _taken(conn, kind, slug, except_id):
        n += 1
        slug = f"{base}-{n}"
    return slug


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise PostError("The title is required.")
    return title


def create_post(conn: sqlite3.Connection, *, kind: str, title: str, slug: str,
                body_md: str, author_id: int) -> int:
    if kind not in KINDS:
        raise PostError("Choose News, Event or Menu.")
    title = _clean_title(title)
    slug = _slug_for(conn, kind, title, slug)
    now = utc_now()
    cur = conn.execute(
        "INSERT INTO posts (kind, title, slug, body_md, author_id, created_at, "
        "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (kind, title, slug, body_md, author_id, now, now))
    conn.commit()
    return cur.lastrowid


def update_post(conn: sqlite3.Connection, post: sqlite3.Row, *, title: str,
                slug: str, body_md: str) -> None:
    """Kind and Author never change. The Slug is locked once first published."""
    title = _clean_title(title)
    if post["first_published_at"]:
        slug = post["slug"]
    else:
        slug = _slug_for(conn, post["kind"], title, slug or post["slug"], post["id"])
    conn.execute("UPDATE posts SET title = ?, slug = ?, body_md = ?, updated_at = ? "
                 "WHERE id = ?", (title, slug, body_md, utc_now(), post["id"]))
    conn.commit()


def get_post(conn: sqlite3.Connection, post_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()


def list_posts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT posts.*, users.name AS author_name FROM posts "
        "JOIN users ON users.id = posts.author_id "
        "ORDER BY posts.updated_at DESC, posts.id DESC").fetchall()
