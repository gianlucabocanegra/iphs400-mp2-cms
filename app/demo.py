"""Demo content for a fresh database, so the CMS can be tried right away."""
from __future__ import annotations

from pathlib import Path

from app import content, db
from app import pages as page_store

# (kind, title, body, mark Published?, Event dates). Saturday 10 and Sunday 11 October 2026.
POSTS = [
    ("news", "Nueva carta de verano", "El restaurante estrena **carta de verano**.", True, {}),
    ("news", "Mantenimiento de la piscina", "Borrador: fechas por confirmar.", False, {}),
    ("event", "Torneo de golf del club",
     "Torneo por parejas durante todo el fin de semana.", True,
     {"event_start_date": "2026-10-10", "event_start_time": "08:00",
      "event_end_date": "2026-10-11"}),
    ("event", "Cena de aniversario", "Borrador de la cena anual.", False,
     {"event_start_date": "2026-11-14", "event_start_time": "20:00"}),
    ("menu", "Menú de la semana", "- Lomo saltado — S/ 38\n- Ají de gallina — S/ 32\n",
     True, {}),
    ("menu", "Menú de la próxima semana", "- Arroz con pollo — S/ 30\n", False, {}),
]

PAGES = [
    ("Reglamento", "Normas de uso de las instalaciones del club.", True, "1"),
    ("Hazte socio", "Borrador: requisitos de membresía.", False, "2"),
]


def seed_content(path: Path | str) -> None:
    """Add the demo Posts and Pages, authored by the Admin. Safe to run twice:
    anything already there (same kind and title, or same Page title) is skipped."""
    db.init_db(path)
    conn = db.connect(path)
    try:
        admin = conn.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id"
                             ).fetchone()
        if admin is None:
            raise RuntimeError("Create the Admin first (seed_users).")
        for kind, title, body, published, event in POSTS:
            if conn.execute("SELECT 1 FROM posts WHERE kind = ? AND title = ?",
                            (kind, title)).fetchone():
                continue
            post_id = content.create_post(conn, kind=kind, title=title, slug="",
                                          body_md=body, author_id=admin["id"], **event)
            if published:
                content.publish_post(conn, content.get_post(conn, post_id))
        for title, body, published, order in PAGES:
            if conn.execute("SELECT 1 FROM pages WHERE title = ?", (title,)).fetchone():
                continue
            page_id = page_store.create_page(conn, title=title, slug="", body_md=body,
                                             nav_order=order, author_id=admin["id"])
            if published:
                page_store.publish_page(conn, page_store.get_page(conn, page_id))
    finally:
        conn.close()
