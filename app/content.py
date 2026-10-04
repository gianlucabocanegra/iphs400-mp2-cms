"""Posts: creation, editing, Slugs and the list. Shared by the console and Export."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date, time

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


def _parsed(value: str, parse, label: str):
    try:
        return parse(value)
    except ValueError:
        raise PostError(f"The {label} isn’t valid.") from None


def _clean_event(kind: str, start_date: str, start_time: str,
                 end_date: str) -> tuple[str | None, str | None, str | None]:
    """The Event date fields as stored. Only Events have them, and Events need a start date."""
    typed = [v.strip() for v in (start_date, start_time, end_date)]
    if kind != "event":
        if any(typed):
            raise PostError("Event dates only apply to Events.")
        return None, None, None
    start_date, start_time, end_date = typed
    if not start_date:
        raise PostError("An Event needs a start date.")
    start = _parsed(start_date, date.fromisoformat, "start date")
    at = _parsed(start_time, time.fromisoformat, "start time") if start_time else None
    end = _parsed(end_date, date.fromisoformat, "end date") if end_date else None
    if end and end < start:
        raise PostError("The end date can’t be earlier than the start date.")
    return (start.isoformat(), at.strftime("%H:%M") if at else None,
            end.isoformat() if end else None)


def create_post(conn: sqlite3.Connection, *, kind: str, title: str, slug: str,
                body_md: str, author_id: int, event_start_date: str = "",
                event_start_time: str = "", event_end_date: str = "") -> int:
    if kind not in KINDS:
        raise PostError("Choose News, Event or Menu.")
    title = _clean_title(title)
    event = _clean_event(kind, event_start_date, event_start_time, event_end_date)
    slug = _slug_for(conn, kind, title, slug)
    now = utc_now()
    cur = conn.execute(
        "INSERT INTO posts (kind, title, slug, body_md, author_id, created_at, "
        "updated_at, event_start_date, event_start_time, event_end_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kind, title, slug, body_md, author_id, now, now, *event))
    conn.commit()
    return cur.lastrowid


def clean_update(conn: sqlite3.Connection, post: sqlite3.Row, *, title: str,
                 slug: str, event_start_date: str = "", event_start_time: str = "",
                 event_end_date: str = "") -> dict:
    """The editable values as they would be stored, or a PostError. Changes nothing.

    Kind and Author never change. The Slug is locked once first published.
    """
    title = _clean_title(title)
    event = _clean_event(post["kind"], event_start_date, event_start_time, event_end_date)
    if post["first_published_at"]:
        slug = post["slug"]
    else:
        slug = _slug_for(conn, post["kind"], title, slug or post["slug"], post["id"])
    return {"title": title, "slug": slug, "event_start_date": event[0],
            "event_start_time": event[1], "event_end_date": event[2]}


def update_post(conn: sqlite3.Connection, post: sqlite3.Row, *, title: str,
                slug: str, body_md: str, event_start_date: str = "",
                event_start_time: str = "", event_end_date: str = "") -> None:
    v = clean_update(conn, post, title=title, slug=slug, event_start_date=event_start_date,
                     event_start_time=event_start_time, event_end_date=event_end_date)
    conn.execute("UPDATE posts SET title = ?, slug = ?, body_md = ?, updated_at = ?, "
                 "event_start_date = ?, event_start_time = ?, event_end_date = ? "
                 "WHERE id = ?",
                 (v["title"], v["slug"], body_md, utc_now(), v["event_start_date"],
                  v["event_start_time"], v["event_end_date"], post["id"]))
    conn.commit()


def get_post(conn: sqlite3.Connection, post_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()


STATUSES = ("draft", "published")


def list_posts(conn: sqlite3.Connection, kind: str | None = None,
               status: str | None = None) -> list[sqlite3.Row]:
    """Posts, most recently updated first, optionally of one kind and/or status."""
    sql = ("SELECT posts.*, users.name AS author_name FROM posts "
           "JOIN users ON users.id = posts.author_id "
           "WHERE (? IS NULL OR kind = ?) AND (? IS NULL OR status = ?) "
           "ORDER BY posts.updated_at DESC, posts.id DESC")
    return conn.execute(sql, (kind, kind, status, status)).fetchall()


def post_counts(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Posts per (kind, status). Every combination is present, with 0 if empty."""
    counts = {(k, s): 0 for k in KINDS for s in STATUSES}
    for row in conn.execute("SELECT kind, status, count(*) AS n FROM posts "
                            "GROUP BY kind, status"):
        counts[(row["kind"], row["status"])] = row["n"]
    return counts


def last_export(conn: sqlite3.Connection) -> str | None:
    """When the last Export ran (UTC), or None if there has never been one."""
    return conn.execute("SELECT max(ran_at) FROM exports").fetchone()[0]


def publish_post(conn: sqlite3.Connection, post: sqlite3.Row) -> None:
    """Mark as Published. The first-published time is set once and never cleared."""
    now = utc_now()
    conn.execute("UPDATE posts SET status = 'published', updated_at = ?, "
                 "first_published_at = coalesce(first_published_at, ?) WHERE id = ?",
                 (now, now, post["id"]))
    conn.commit()


def unpublish_post(conn: sqlite3.Connection, post: sqlite3.Row) -> None:
    """Back to Draft. first_published_at stays, so the Slug stays locked."""
    conn.execute("UPDATE posts SET status = 'draft', updated_at = ? WHERE id = ?",
                 (utc_now(), post["id"]))
    conn.commit()


def delete_post(conn: sqlite3.Connection, post: sqlite3.Row) -> None:
    """Permanently remove a Post. A Published one is remembered, so the
    not-yet-Live count includes it until the next Export."""
    if post["status"] == "published":
        conn.execute("INSERT INTO deleted_published (deleted_at) VALUES (?)", (utc_now(),))
    conn.execute("DELETE FROM posts WHERE id = ?", (post["id"],))
    conn.commit()


def changes_not_live(conn: sqlite3.Connection) -> int:
    """Changes Members can't see yet: Posts and Pages touched since the last Export, plus
    Live ones deleted since then. Before any Export, every Published item counts."""
    last = last_export(conn)
    if last is None:
        return sum(conn.execute(f"SELECT count(*) FROM {table} WHERE status = 'published'"
                                ).fetchone()[0] for table in ("posts", "pages"))
    touched = sum(conn.execute(f"SELECT count(*) FROM {table} WHERE updated_at > ?",
                               (last,)).fetchone()[0] for table in ("posts", "pages"))
    deleted = conn.execute("SELECT count(*) FROM deleted_published WHERE deleted_at > ?",
                           (last,)).fetchone()[0]
    return touched + deleted


def published_posts(conn: sqlite3.Connection, kind: str | None = None,
                    limit: int | None = None) -> list[sqlite3.Row]:
    """Published Posts, newest first. Selects no Author: the public site has none."""
    sql = ("SELECT id, kind, title, slug, body_md, first_published_at, "
           "event_start_date, event_start_time, event_end_date FROM posts "
           "WHERE status = 'published'")
    args: list = []
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    sql += " ORDER BY first_published_at DESC, id DESC"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    return conn.execute(sql, args).fetchall()


def published_events(conn: sqlite3.Connection,
                     export_date: date) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """(Upcoming, past) Published Events.

    Upcoming: the end date, or the start date if there is none, is on or after
    the export date. Upcoming is soonest first; past is most recent first.
    """
    today = export_date.isoformat()

    def last_day(event) -> str:
        return event["event_end_date"] or event["event_start_date"] or ""

    def starts(event) -> tuple:
        return (event["event_start_date"] or "", event["event_start_time"] or "",
                event["id"])

    events = published_posts(conn, "event")
    upcoming = sorted((e for e in events if last_day(e) >= today), key=starts)
    past = sorted((e for e in events if last_day(e) < today),
                  key=lambda e: (last_day(e), *starts(e)), reverse=True)
    return upcoming, past


def published_menus(conn: sqlite3.Connection) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    """(Current menu, Menu archive): the newest Published Menu, then all the others."""
    menus = published_posts(conn, "menu")
    return (menus[0] if menus else None), menus[1:]
