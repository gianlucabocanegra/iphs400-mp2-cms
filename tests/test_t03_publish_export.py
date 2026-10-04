"""T03: publish a Post, then Export it. Seam 1 (console) and Seam 2 (render_site)."""
import html
import re
from datetime import date

from app.publish import render_site
from tests.conftest import csrf_from
from tests.test_t02_posts import edit_post, save_post

EXPORT_DAY = date(2026, 9, 29)


def confirm(client, screen):
    """Submit a Confirmation screen as the browser would: its hidden fields, confirm flag."""
    form = re.search(r'<form method="post" action="([^"]+)"[^>]*>\s*'
                     r'((?:<input type="hidden"[^>]*>\s*)+)<button[^>]*value="confirm"',
                     screen.text)
    assert form, "no confirm form on the page"
    fields = {k: html.unescape(v) for k, v in
              re.findall(r'name="([^"]+)" value="([^"]*)"', form.group(2))}
    return client.post(form.group(1), data={**fields, "confirm": "1"},
                       follow_redirects=False)


def new_post(client, **kw):
    return save_post(client, **kw).headers["location"]


def post_action(client, location, action):
    """Ask for `action`, then give the Confirmation (T05). Returns the confirmed response."""
    token = csrf_from(client.get(location))
    asked = client.post(f"{location}/{action}", data={"csrf_token": token},
                        follow_redirects=False)
    assert asked.status_code == 200, "expected a Confirmation screen"
    return confirm(client, asked)


def publish(client, **kw):
    location = new_post(client, **kw)
    assert post_action(client, location, "publish").status_code == 303
    return location


def export(tmp_path):
    return render_site(tmp_path / "site", export_date=EXPORT_DAY)


def all_html(out):
    return "\n".join(p.read_text() for p in out.rglob("*.html"))


# --- console -------------------------------------------------------------

def test_editor_publishes_and_unpublishes(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="news", title="Torneo")
    assert "Draft" in editor.get(location).text
    assert post_action(editor, location, "publish").status_code == 303
    assert "Published" in editor.get(location).text
    assert post_action(editor, location, "unpublish").status_code == 303
    page = editor.get(location).text
    assert "Draft" in page and "Published" not in page


def test_publish_needs_a_csrf_token(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="news", title="Torneo")
    assert editor.post(f"{location}/publish").status_code == 403
    assert "Draft" in editor.get(location).text


def test_slug_stays_locked_after_publish_and_unpublish(client_as):
    editor = client_as("editor")
    location = publish(editor, kind="news", title="Torneo", slug="torneo")
    post_action(editor, location, "unpublish")
    edit_post(editor, location, title="Torneo", slug="otro", body_md="x")
    assert "readonly" in editor.get(location).text
    assert 'value="torneo"' in editor.get(location).text


def test_first_published_time_never_changes(client_as, monkeypatch):
    from app import content
    editor = client_as("editor")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-29T15:00:00+00:00")
    location = publish(editor, kind="news", title="Torneo")
    assert "First published (Lima): 2026-09-29 10:00" in editor.get(location).text
    monkeypatch.setattr(content, "utc_now", lambda: "2026-10-05T15:00:00+00:00")
    post_action(editor, location, "unpublish")
    post_action(editor, location, "publish")
    assert "First published (Lima): 2026-09-29 10:00" in editor.get(location).text


# --- Export --------------------------------------------------------------

def test_drafts_never_reach_the_site(client_as, tmp_path):
    editor = client_as("editor")
    new_post(editor, kind="news", title="Borrador secreto", slug="borrador")
    publish(editor, kind="news", title="Noticia pública")
    out = export(tmp_path)
    assert "Borrador secreto" not in all_html(out)
    assert not (out / "noticias" / "borrador.html").exists()
    assert (out / "noticias" / "noticia-publica.html").exists()


def test_unpublished_post_leaves_the_site_at_next_export(client_as, tmp_path):
    editor = client_as("editor")
    location = publish(editor, kind="news", title="Retirada")
    post_action(editor, location, "unpublish")
    out = export(tmp_path)
    assert "Retirada" not in all_html(out)


def test_home_shows_latest_five_news_newest_first(client_as, tmp_path):
    editor = client_as("editor")
    for n in range(1, 8):
        publish(editor, kind="news", title=f"Noticia {n}")
    home = (export(tmp_path) / "index.html").read_text()
    assert "Noticia 7" in home and "Noticia 3" in home
    assert "Noticia 2" not in home and "Noticia 1" not in home
    assert home.index("Noticia 7") < home.index("Noticia 6") < home.index("Noticia 3")


def test_news_index_lists_all_published_news(client_as, tmp_path):
    editor = client_as("editor")
    for n in range(1, 8):
        publish(editor, kind="news", title=f"Noticia {n}")
    index = (export(tmp_path) / "noticias" / "index.html").read_text()
    assert all(f"Noticia {n}" in index for n in range(1, 8))


def test_each_kind_gets_its_page_in_its_own_folder(client_as, tmp_path):
    editor = client_as("editor")
    publish(editor, kind="news", title="Una noticia")
    publish(editor, kind="event", title="Un evento")
    publish(editor, kind="menu", title="Un menú")
    out = export(tmp_path)
    assert (out / "noticias" / "una-noticia.html").exists()
    assert (out / "eventos" / "un-evento.html").exists()
    assert (out / "menus" / "un-menu.html").exists()


def test_news_date_is_spanish_and_in_lima_time(client_as, tmp_path, monkeypatch):
    from app import content
    # 2026-09-30 02:30 UTC is still 29 September 21:30 in Lima.
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-30T02:30:00+00:00")
    editor = client_as("editor")
    publish(editor, kind="news", title="Noche de gala")
    out = export(tmp_path)
    assert "29 de septiembre de 2026" in (out / "noticias" / "noche-de-gala.html").read_text()
    assert "29 de septiembre de 2026" in (out / "noticias" / "index.html").read_text()


def test_no_author_name_anywhere_in_the_site(client_as, tmp_path):
    publish(client_as("editor"), kind="news", title="Con autor")
    publish(client_as("admin"), kind="news", title="Con otro autor")
    html = all_html(export(tmp_path))
    assert "Demo Editor" not in html and "Demo Admin" not in html
    assert "editor@example.test" not in html


def test_script_in_a_body_is_stripped_but_external_image_survives(client_as, tmp_path):
    body = "Hola <script>alert(1)</script>\n\n![foto](https://example.org/a.png)"
    publish(client_as("editor"), kind="news", title="Peligro", body=body)
    html = (export(tmp_path) / "noticias" / "peligro.html").read_text()
    assert "<script" not in html and "alert(1)" not in html
    assert 'src="https://example.org/a.png"' in html


def test_site_uses_relative_paths_only(client_as, tmp_path):
    editor = client_as("editor")
    publish(editor, kind="news", title="Ruta", body="[a](/x) ![i](/y.png)")
    publish(editor, kind="event", title="Otro")
    out = export(tmp_path)
    for path in out.rglob("*.html"):
        text = path.read_text()
        assert 'href="/' not in text and 'src="/' not in text, path
    assert 'href="../style.css"' in (out / "noticias" / "ruta.html").read_text()
    assert 'href="style.css"' in (out / "index.html").read_text()


def test_each_export_records_the_time_it_ran(client_as, tmp_path, db_path):
    import sqlite3
    export(tmp_path)
    export(tmp_path)
    rows = sqlite3.connect(db_path).execute("SELECT ran_at FROM exports").fetchall()
    assert len(rows) == 2 and all(r[0] for r in rows)
