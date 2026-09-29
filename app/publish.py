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
from app.timeutil import fecha, today_lima, utc_now

FOLDERS = {"news": "noticias", "event": "eventos", "menu": "menus"}
KIND_LABELS_ES = {"news": "Noticia", "event": "Evento", "menu": "Menú de la semana"}
HOME_NEWS = 5

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


def _link(post, root: str) -> dict:
    """A feed entry. `root` is the relative path from the page back to site/."""
    kind = post["kind"]
    return {"title": post["title"], "href": f"{root}{FOLDERS[kind]}/{post['slug']}.html",
            "date": fecha(post["first_published_at"]) if kind == "news" else ""}


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
    finally:
        conn.close()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "style.css").write_text(CSS)

    def page(template: str, depth: int, **ctx) -> str:
        root = "../" * depth
        nav = [("Inicio", f"{root}index.html"), ("Noticias", f"{root}noticias/index.html")]
        return env.get_template(template).render(
            title=settings.SITE_TITLE, lang="es", nav=nav, css_path=f"{root}style.css",
            home_path=f"{root}index.html", **ctx)

    news = [p for p in posts if p["kind"] == "news"]
    _write(out, "index.html", page(
        "public/home.html", 0,
        news=[_link(p, "") for p in news[:HOME_NEWS]]))
    _write(out, "noticias/index.html", page(
        "public/feed.html", 1, page_title="Noticias", heading="Noticias",
        items=[_link(p, "../") for p in news]))
    for p in posts:
        _write(out, f"{FOLDERS[p['kind']]}/{p['slug']}.html", page(
            "public/post.html", 1, page_title=p["title"], post=p,
            kind_label=KIND_LABELS_ES[p["kind"]],
            date_label=fecha(p["first_published_at"]) if p["kind"] == "news" else "",
            body_html=render_markdown(p["body_md"])))

    conn = db.connect(settings.DATABASE_PATH)
    try:
        conn.execute("INSERT INTO exports (ran_at) VALUES (?)", (utc_now(),))
        conn.commit()
    finally:
        conn.close()
    return out
