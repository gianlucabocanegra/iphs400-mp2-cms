"""T05: Confirmation screens. Seam 1, the console over HTTP."""
import html
import re
from datetime import date

from app.publish import render_site
from tests.conftest import csrf_from
from tests.test_t02_posts import save_post
from tests.test_t03_publish_export import confirm, new_post, post_action, publish

PRICE_MENU = "Lomo saltado S/ 35"


def ask(client, location, action, **fields):
    """The first submission of an action, with the editor's current values."""
    token = csrf_from(client.get(location))
    return client.post(f"{location}/{action}" if action else location, data={"csrf_token": token, **fields},
                       follow_redirects=False)


def editor_values(**over):
    return {"title": "Menú", "slug": "menu", "body_md": PRICE_MENU, **over}


def status_of(client, location):
    return "Published" if "Status: Published" in client.get(location).text else "Draft"


def is_live(tmp_path, name):
    return (render_site(tmp_path / "site", export_date=date(2026, 9, 29)) / name).exists()


# --- publish -------------------------------------------------------------

def test_publish_shows_a_confirmation_with_the_preview_and_changes_nothing(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="menu", title="Menú", slug="menu", body=PRICE_MENU)
    screen = ask(editor, location, "publish", **editor_values())
    assert screen.status_code == 200
    assert "Confirm" in screen.text and PRICE_MENU in screen.text
    assert status_of(editor, location) == "Draft"


def test_confirmed_publish_applies_the_values_on_the_screen(client_as, tmp_path):
    editor = client_as("editor")
    location = new_post(editor, kind="menu", title="Menú", slug="menu", body=PRICE_MENU)
    screen = ask(editor, location, "publish", **editor_values(body_md="Lomo saltado S/ 38"))
    assert "S/ 38" in screen.text
    assert confirm(editor, screen).status_code == 303
    assert status_of(editor, location) == "Published"
    export = render_site(tmp_path / "site", export_date=date(2026, 9, 29))
    assert "S/ 38" in (export / "menus" / "menu.html").read_text()


def test_publish_with_an_invalid_value_shows_the_form_error_not_a_confirmation(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="menu", title="Menú")
    response = ask(editor, location, "publish", **editor_values(title=""))
    assert response.status_code == 422 and "title is required" in response.text
    assert status_of(editor, location) == "Draft"


# --- saving edits to Published content -----------------------------------

def test_saving_edits_to_a_published_post_needs_confirmation(client_as):
    editor = client_as("editor")
    location = publish(editor, kind="menu", title="Menú", slug="menu", body=PRICE_MENU)
    screen = ask(editor, location, "", **editor_values(body_md="Lomo saltado S/ 99"))
    assert screen.status_code == 200 and "S/ 99" in screen.text
    assert PRICE_MENU in editor.get(location).text  # stored Post unchanged
    assert confirm(editor, screen).status_code == 303
    assert "S/ 99" in editor.get(location).text


def test_saving_a_draft_needs_no_confirmation(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="menu", title="Menú", slug="menu", body=PRICE_MENU)
    response = ask(editor, location, "", **editor_values(body_md="Nuevo"))
    assert response.status_code == 303
    assert "Nuevo" in editor.get(location).text


# --- unpublish and delete ------------------------------------------------

def test_unpublish_needs_confirmation(client_as):
    editor = client_as("editor")
    location = publish(editor, kind="news", title="Torneo")
    screen = ask(editor, location, "unpublish")
    assert screen.status_code == 200
    assert status_of(editor, location) == "Published"
    assert confirm(editor, screen).status_code == 303
    assert status_of(editor, location) == "Draft"


def test_delete_needs_confirmation_that_says_it_is_permanent(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="news", title="Torneo")
    screen = ask(editor, location, "delete")
    assert screen.status_code == 200 and "permanent" in screen.text
    assert editor.get(location).status_code == 200  # still there
    assert confirm(editor, screen).status_code == 303
    assert editor.get(location).status_code == 404
    assert "Torneo" not in editor.get("/admin/posts").text


def test_deleting_a_published_post_removes_it_from_the_site_at_next_export(client_as, tmp_path):
    editor = client_as("editor")
    location = publish(editor, kind="news", title="Torneo")
    assert is_live(tmp_path, "noticias/torneo.html")
    confirm(editor, ask(editor, location, "delete"))
    assert not is_live(tmp_path, "noticias/torneo.html")


# --- cancel --------------------------------------------------------------

def test_cancel_returns_to_the_editor_with_the_unsaved_values(client_as):
    editor = client_as("editor")
    location = publish(editor, kind="menu", title="Menú", slug="menu", body=PRICE_MENU)
    screen = ask(editor, location, "", **editor_values(title="Menú nuevo",
                                                       body_md='Sin "comillas" <b>'))
    cancel = re.search(r'formaction="([^"]+)"[^>]*value="cancel"', screen.text)
    assert cancel, "no cancel button"
    fields = {k: html.unescape(v) for k, v in
              re.findall(r'name="([^"]+)" value="([^"]*)"', screen.text)}
    back = editor.post(cancel.group(1), data=fields, follow_redirects=False)
    assert back.status_code == 200
    assert 'value="Menú nuevo"' in back.text and "Sin &#34;comillas&#34; &lt;b&gt;" in back.text
    assert PRICE_MENU in editor.get(location).text  # nothing was saved


# --- CSRF ----------------------------------------------------------------

def test_confirmed_submission_without_a_csrf_token_is_rejected(client_as):
    editor = client_as("editor")
    location = new_post(editor, kind="news", title="Torneo")
    response = editor.post(f"{location}/publish", data={"confirm": "1", **editor_values()})
    assert response.status_code == 403
    assert status_of(editor, location) == "Draft"
    assert editor.post(f"{location}/delete", data={"confirm": "1"}).status_code == 403
    assert editor.get(location).status_code == 200


def test_every_confirmation_form_carries_the_csrf_token(client_as):
    editor = client_as("editor")
    location = publish(editor, kind="news", title="Torneo")
    for action in ("unpublish", "delete"):
        csrf_from(ask(editor, location, action))


# --- not yet Live --------------------------------------------------------

def not_live(client):
    return int(re.search(r"Changes not yet Live: (\d+)", client.get("/admin").text).group(1))


def test_deleting_a_live_post_counts_as_not_yet_live_until_the_next_export(client_as, tmp_path):
    editor = client_as("editor")
    location = publish(editor, kind="news", title="Torneo")
    is_live(tmp_path, "index.html")  # an Export
    assert not_live(editor) == 0
    confirm(editor, ask(editor, location, "delete"))
    assert not_live(editor) == 1
    is_live(tmp_path, "index.html")
    assert not_live(editor) == 0


def test_published_work_counts_as_not_yet_live_until_exported(client_as, tmp_path):
    editor = client_as("editor")
    assert not_live(editor) == 0
    publish(editor, kind="news", title="Torneo")
    assert not_live(editor) == 1
    is_live(tmp_path, "index.html")
    assert not_live(editor) == 0


# --- public site ---------------------------------------------------------

def test_public_site_has_no_javascript(client_as, tmp_path):
    editor = client_as("editor")
    publish(editor, kind="news", title="Torneo")
    publish(editor, kind="menu", title="Menú")
    out = render_site(tmp_path / "site", export_date=date(2026, 9, 29))
    for path in out.rglob("*.html"):
        assert "<script" not in path.read_text(), path
    assert not list(out.rglob("*.js"))
