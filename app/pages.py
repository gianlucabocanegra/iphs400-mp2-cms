"""Pages: standing content with a navigation entry. Shared by the console and Export.

Same Draft/Published lifecycle and Slug rules as Posts (see content.py), but a
Page Slug is unique across all Pages and can't be one of the public site's own
addresses.
"""
from __future__ import annotations

import sqlite3

from app.content import PostError, _clean_title, slugify
from app.timeutil import utc_now

RESERVED_SLUGS = ("index", "noticias", "eventos", "menus", "style")


def _taken(conn: sqlite3.Connection, slug: str, except_id: int | None) -> bool:
    return conn.execute("SELECT 1 FROM pages WHERE slug = ? AND id IS NOT ?",
                        (slug, except_id)).fetchone() is not None


def _reserved(slug: str) -> PostError:
    return PostError(f"The slug “{slug}” is reserved for the public site. Choose another.")


def _slug_for(conn: sqlite3.Connection, title: str, typed: str,
              except_id: int | None = None) -> str:
    """A typed Slug must be free; a generated one gets -2, -3, ... until it is."""
    if typed.strip():
        slug = slugify(typed)
        if not slug:
            raise PostError("The slug needs letters or numbers.")
        if slug in RESERVED_SLUGS:
            raise _reserved(slug)
        if _taken(conn, slug, except_id):
            raise PostError(f"The slug “{slug}” is already used by another page.")
        return slug
    base = slugify(title)
    if not base:
        raise PostError("The title needs letters or numbers to make a slug from.")
    if base in RESERVED_SLUGS:
        raise _reserved(base)
    slug, n = base, 1
    while _taken(conn, slug, except_id):
        n += 1
        slug = f"{base}-{n}"
    return slug


def _nav_order(value: str) -> int:
    try:
        return int(value.strip() or 0)
    except ValueError:
        raise PostError("The navigation order must be a whole number.") from None


def _nav_key(page: sqlite3.Row) -> tuple:
    """Navigation order, ties by title. Accents and case are ignored, so "Álbum" sorts with A."""
    return (page["nav_order"], slugify(page["title"]), page["id"])


def create_page(conn: sqlite3.Connection, *, title: str, slug: str, body_md: str,
                nav_order: str, author_id: int) -> int:
    title = _clean_title(title)
    order = _nav_order(nav_order)
    slug = _slug_for(conn, title, slug)
    now = utc_now()
    cur = conn.execute(
        "INSERT INTO pages (title, slug, body_md, nav_order, author_id, created_at, "
        "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, slug, body_md, order, author_id, now, now))
    conn.commit()
    return cur.lastrowid


def clean_update(conn: sqlite3.Connection, page: sqlite3.Row, *, title: str, slug: str,
                 nav_order: str) -> dict:
    """The editable values as they would be stored, or a PostError. Changes nothing.

    The Author never changes. The Slug is locked once first published.
    """
    title = _clean_title(title)
    order = _nav_order(nav_order)
    if page["first_published_at"]:
        slug = page["slug"]
    else:
        slug = _slug_for(conn, title, slug or page["slug"], page["id"])
    return {"title": title, "slug": slug, "nav_order": order}


def update_page(conn: sqlite3.Connection, page: sqlite3.Row, *, title: str, slug: str,
                body_md: str, nav_order: str) -> None:
    v = clean_update(conn, page, title=title, slug=slug, nav_order=nav_order)
    conn.execute("UPDATE pages SET title = ?, slug = ?, body_md = ?, nav_order = ?, "
                 "updated_at = ? WHERE id = ?",
                 (v["title"], v["slug"], body_md, v["nav_order"], utc_now(), page["id"]))
    conn.commit()


def get_page(conn: sqlite3.Connection, page_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()


def list_pages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT pages.*, users.name AS author_name FROM pages "
        "JOIN users ON users.id = pages.author_id").fetchall()
    return sorted(rows, key=_nav_key)


def publish_page(conn: sqlite3.Connection, page: sqlite3.Row) -> None:
    """Mark as Published. The first-published time is set once and never cleared."""
    now = utc_now()
    conn.execute("UPDATE pages SET status = 'published', updated_at = ?, "
                 "first_published_at = coalesce(first_published_at, ?) WHERE id = ?",
                 (now, now, page["id"]))
    conn.commit()


def unpublish_page(conn: sqlite3.Connection, page: sqlite3.Row) -> None:
    """Back to Draft. first_published_at stays, so the Slug stays locked."""
    conn.execute("UPDATE pages SET status = 'draft', updated_at = ? WHERE id = ?",
                 (utc_now(), page["id"]))
    conn.commit()


def delete_page(conn: sqlite3.Connection, page: sqlite3.Row) -> None:
    """Permanently remove a Page. A Published one is remembered, so the
    not-yet-Live count includes it until the next Export."""
    if page["status"] == "published":
        conn.execute("INSERT INTO deleted_published (deleted_at) VALUES (?)", (utc_now(),))
    conn.execute("DELETE FROM pages WHERE id = ?", (page["id"],))
    conn.commit()


def published_pages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Published Pages in Navigation order: nav_order, ties by title. No Author."""
    rows = conn.execute("SELECT id, title, slug, body_md, nav_order FROM pages "
                        "WHERE status = 'published'").fetchall()
    return sorted(rows, key=_nav_key)
