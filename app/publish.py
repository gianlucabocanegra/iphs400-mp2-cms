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

from app import content, db, pages as page_store, settings
from app.markdown import render_markdown
from app.timeutil import fecha, fecha_evento, today_lima, utc_now

FOLDERS = {"news": "noticias", "event": "eventos", "menu": "menus"}
KIND_LABELS_ES = {"news": "Noticia", "event": "Evento", "menu": "Menú de la semana"}
HOME_NEWS = 5
HOME_EVENTS = 3

CSS = """/* Club styles: system fonts only, relative paths only. */
:root {
  --green: #1f4d36; --green-deep: #173a29; --green-soft: #2f6b4b;
  --cream: #f8f3e6; --paper: #fffdf7; --ink: #25231d; --muted: #5f5a4c;
  --gutter: max(1rem, calc((100% - 44rem) / 2));
}
* { box-sizing: border-box; }
html { background: var(--cream); }
body { margin: 0; background: var(--cream); color: var(--ink);
  font: 17px/1.65 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  overflow-wrap: break-word; }

/* Header band */
header { background: var(--green); color: var(--cream);
  padding: 1.5rem var(--gutter) 0; border-bottom: 4px solid #b89b52; }
header > a { display: block; color: var(--cream); text-decoration: none;
  font: 700 clamp(1.5rem, 5vw, 2.1rem)/1.2 Georgia, "Times New Roman", serif;
  letter-spacing: .01em; }
nav { display: flex; flex-wrap: wrap; gap: .25rem 1.25rem; margin: 1rem 0 0; }
header nav a { color: var(--cream); text-decoration: none; padding: .5rem 0 .4rem;
  border-bottom: 3px solid transparent; font-size: .95rem; }
header nav a:hover, header nav a:focus-visible,
header nav a[aria-current="page"] { border-bottom-color: #e3c97a; }

/* Page */
main { padding: 0 var(--gutter); margin-block: 2rem 3rem; }
h1, h2, h3 { font-family: Georgia, "Times New Roman", serif; color: var(--green-deep);
  line-height: 1.25; margin: 0 0 .6rem; }
h1 { font-size: 1.7rem; } h2 { font-size: 1.3rem; } h3 { font-size: 1.1rem; }
p, ul, ol { margin: 0 0 1rem; }
a { color: var(--green); text-underline-offset: .15em; }
a:hover { color: var(--green-deep); text-decoration-thickness: 2px; }
a:focus-visible, button:focus-visible { outline: 3px solid #b89b52; outline-offset: 2px; }
small { color: var(--muted); font-size: .88rem; }
article > p:first-child strong { color: var(--green); }

/* Soft cards */
main > section { background: var(--paper); border: 1px solid var(--green-soft);
  border-radius: .6rem; padding: 1.1rem 1.4rem 1.2rem; margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(31, 77, 54, .08); }
main > section > :last-child { margin-bottom: 0; }
main > section ul { list-style: none; padding: 0; }
main > section li { padding: .55rem 0; border-top: 1px solid #e6dfca; }
main > section li:first-child { border-top: 0; }
main > section li small { display: block; }
main > section li strong { color: var(--muted); font-weight: 600; margin-right: .4rem; }
article ul, article ol { padding-left: 1.4rem; }
article li { margin-bottom: .3rem; }

/* Footer */
footer { border-top: 1px solid #d9d0b6; padding: 1.25rem var(--gutter) 2rem;
  color: var(--muted); text-align: center; }

/* Admin console (shares this sheet): nav, tables, forms. */
main > nav { align-items: center; margin: 0 0 1.5rem; padding-bottom: .75rem;
  border-bottom: 1px solid #d9d0b6; }
main > nav form { margin: 0; }
.scroll { margin-bottom: 1.5rem; }
table { border-collapse: collapse; min-width: 30rem; width: 100%; background: var(--paper); }
th, td { text-align: left; padding: .55rem .75rem; border-bottom: 1px solid #e6dfca;
  vertical-align: top; }
th { color: var(--green-deep); border-bottom: 2px solid var(--green-soft); white-space: nowrap; }
label { display: block; margin-bottom: 1rem; }
input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea {
  display: block; width: 100%; margin-top: .25rem; padding: .5rem .6rem; font: inherit;
  background: #fff; color: var(--ink); border: 1px solid #8a8670; border-radius: .3rem; }
button { font: inherit; font-size: .95rem; padding: .45rem .9rem; cursor: pointer;
  color: var(--cream); background: var(--green); border: 1px solid var(--green-deep);
  border-radius: .3rem; }
button:hover { background: var(--green-deep); }

/* Phone width: nothing may push the page wider than the screen. */
img, input, select, textarea { max-width: 100%; }
img { height: auto; }
pre { overflow-x: auto; }
.scroll { overflow-x: auto; }
.flash { border: 1px solid; border-radius: .25rem; padding: .5rem .75rem; }
@media (max-width: 480px) {
  body { font-size: 16px; }
  main > section { padding: 1rem; }
}
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
    """Write every Published Post and Page into `out` and record the Export.

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
        pages = page_store.published_pages(conn)
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
               ("Menús anteriores", f"{root}menus/index.html"),
               *((p["title"], f"{root}{p['slug']}.html") for p in pages)]
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

    for p in pages:
        _write(out, f"{p['slug']}.html", page(
            "public/post.html", 0, page_title=p["title"], post=p, kind_label="",
            event_label="", date_label="", body_html=render_markdown(p["body_md"])))

    conn = db.connect(settings.DATABASE_PATH)
    try:
        conn.execute("INSERT INTO exports (ran_at) VALUES (?)", (utc_now(),))
        conn.commit()
    finally:
        conn.close()
    return out
