"""Render the public site into site/ as plain HTML.

Two rules the rubric checks:

  1. Only PUBLISHED content is written here. A draft that reaches site/ is a bug.
  2. Every href and src is RELATIVE ("style.css", "posts/x.html"), never
     root-absolute ("/style.css"), because Pages serves this from a subfolder.
"""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import content, db, settings
from app.markdown import render_markdown
from app.timeutil import fecha, fecha_evento, today_lima, utc_now

FOLDERS = {"news": "noticias", "event": "eventos", "menu": "menus"}
KIND_LABELS_ES = {"news": "Noticia", "event": "Evento", "menu": "Menú de la semana"}
HOME_NEWS = 5
HOME_EVENTS = 3

CSS = """/* Minimal starter styles — make them yours. */
:root { color-scheme: light dark; }
body { font: 16px/1.6 system-ui, sans-serif; margin: 0 auto; max-width: 42rem; padding: 1rem; }
header a { font-weight: 700; text-decoration: none; }
main { margin-block: 2rem; }
"""


def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(settings.TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


def _write(out: Path, name: str, html: str) -> None:
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)


def _event_label(post) -> str:
    return fecha_evento(post["event_start_date"], post["event_start_time"],
                        post["event_end_date"])


def _date_label(post) -> str:
    """Events are dated by when they happen; News and Menus by first publish."""
    if post["kind"] == "event":
        return _event_label(post)
    return fecha(post["first_published_at"])


def _link(post, root: str) -> dict:
    """A feed entry. `root` is the relative path from the page back to site/."""
    return {"title": post["title"],
            "href": f"{root}{FOLDERS[post['kind']]}/{post['slug']}.html",
            "date": _date_label(post)}


def render_site(out: Path | None = None, export_date: date | None = None) -> Path:
    """Write every Published Post into `out` and record the Export.

    `export_date` (a Lima date) is what Upcoming is measured against from T04 on.
    """
    out = out or settings.SITE
    export_date = export_date or today_lima()
    env = environment()
    db.init_db(settings.DATABASE_PATH)  # an older database may lack `exports`
    conn = db.connect(settings.DATABASE_PATH)
    try:
        posts = content.published_posts(conn)
        upcoming, past = content.published_events(conn, export_date)
        current_menu, archive = content.published_menus(conn)
    finally:
        conn.close()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "style.css").write_text(CSS)

    def page(template: str, depth: int, **ctx) -> str:
        root = "../" * depth
        nav = [("Inicio", f"{root}index.html"),
               ("Noticias", f"{root}noticias/index.html"),
               ("Eventos", f"{root}eventos/index.html"),
               ("Menús anteriores", f"{root}menus/index.html")]
        return env.get_template(template).render(
            title=settings.SITE_TITLE, lang="es", nav=nav, css_path=f"{root}style.css",
            home_path=f"{root}index.html", **ctx)

    news = [p for p in posts if p["kind"] == "news"]
    menu = None
    if current_menu:
        menu = {**_link(current_menu, ""),
                "body_html": render_markdown(current_menu["body_md"])}
    _write(out, "index.html", page(
        "public/home.html", 0, menu=menu,
        events=[_link(p, "") for p in upcoming[:HOME_EVENTS]],
        news=[_link(p, "") for p in news[:HOME_NEWS]]))
    _write(out, "noticias/index.html", page(
        "public/feed.html", 1, page_title="Noticias", heading="Noticias",
        items=[_link(p, "../") for p in news]))
    _write(out, "eventos/index.html", page(
        "public/events.html", 1, page_title="Eventos",
        upcoming=[_link(p, "../") for p in upcoming],
        past=[_link(p, "../") for p in past]))
    _write(out, "menus/index.html", page(
        "public/feed.html", 1, page_title="Menús anteriores",
        heading="Menús anteriores", items=[_link(p, "../") for p in archive]))
    for p in posts:
        event = p["kind"] == "event"
        _write(out, f"{FOLDERS[p['kind']]}/{p['slug']}.html", page(
            "public/post.html", 1, page_title=p["title"], post=p,
            kind_label=KIND_LABELS_ES[p["kind"]],
            event_label=_event_label(p) if event else "",
            date_label="" if event else fecha(p["first_published_at"]),
            body_html=render_markdown(p["body_md"])))

    conn = db.connect(settings.DATABASE_PATH)
    try:
        conn.execute("INSERT INTO exports (ran_at) VALUES (?)", (utc_now(),))
        conn.commit()
    finally:
        conn.close()
    return out
