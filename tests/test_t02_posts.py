"""T02: create and edit a Draft Post, through the console over HTTP (Seam 1)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import csrf_from


def save_post(client, *, title="Menú de la semana", kind="menu", body="Hola",
              slug=""):
    token = csrf_from(client.get("/admin/posts/new"))
    # Since T04 an Event needs a start date; News and Menus must not have one.
    event = {"event_start_date": "2026-10-10"} if kind == "event" else {}
    return client.post("/admin/posts", data={
        "csrf_token": token, "kind": kind, "title": title, "slug": slug,
        "body_md": body, **event}, follow_redirects=False)


def edit_post(client, location, **fields):
    token = csrf_from(client.get(location))
    return client.post(location, data={"csrf_token": token, **fields},
                       follow_redirects=False)


def test_editor_creates_a_draft_of_each_kind_with_themselves_as_author(client_as):
    editor = client_as("editor")
    for kind in ("news", "event", "menu"):
        response = save_post(editor, title=f"Un {kind}", kind=kind)
        assert response.status_code == 303
    page = editor.get("/admin/posts").text
    for kind in ("News", "Event", "Menu"):
        assert kind in page
    assert page.count("Draft") >= 3
    assert page.count("Demo Editor") >= 3


def test_post_forms_carry_the_csrf_token(client_as):
    editor = client_as("editor")
    location = save_post(editor).headers["location"]
    assert 'name="csrf_token"' in editor.get("/admin/posts/new").text
    assert 'name="csrf_token"' in editor.get(location).text


def test_post_form_without_csrf_token_is_refused(client_as):
    response = client_as("editor").post("/admin/posts", data={
        "kind": "news", "title": "x", "body_md": "y"})
    assert response.status_code == 403


def test_signed_out_visitor_is_sent_to_login(client):
    assert client.get("/admin/posts", follow_redirects=False).status_code == 303


def test_kind_cannot_be_changed_after_creation(client_as):
    editor = client_as("editor")
    location = save_post(editor, kind="news", title="Solo noticia").headers["location"]
    edit_post(editor, location, kind="menu", title="Solo noticia",
              slug="solo-noticia", body_md="cambio")
    rows = editor.get("/admin/posts").text.split("<tbody>")[1]  # the list, not the filters
    assert "News" in rows and "Menu" not in rows
    assert 'name="kind"' not in editor.get(location).text


@pytest.mark.parametrize("title, expected", [
    ("Menú de la semana", "menu-de-la-semana"),
    ("Cóctel de Año Nuevo: ¡Ñandú!", "coctel-de-ano-nuevo-nandu"),
])
def test_slug_is_generated_from_the_title(client_as, title, expected):
    editor = client_as("editor")
    location = save_post(editor, title=title).headers["location"]
    assert f'value="{expected}"' in editor.get(location).text


def test_auto_generated_slug_clash_gets_a_numeric_suffix(client_as):
    editor = client_as("editor")
    slugs = []
    for _ in range(3):
        location = save_post(editor).headers["location"]
        slugs.append(location)
    assert 'value="menu-de-la-semana"' in editor.get(slugs[0]).text
    assert 'value="menu-de-la-semana-2"' in editor.get(slugs[1]).text
    assert 'value="menu-de-la-semana-3"' in editor.get(slugs[2]).text


def test_same_slug_in_another_kind_is_not_a_clash(client_as):
    editor = client_as("editor")
    save_post(editor, title="Torneo", kind="news")
    location = save_post(editor, title="Torneo", kind="event").headers["location"]
    assert 'value="torneo"' in editor.get(location).text


def test_hand_typed_slug_clash_is_a_form_error_and_saves_nothing(client_as):
    editor = client_as("editor")
    save_post(editor, title="Primero", slug="mi-slug")
    response = save_post(editor, title="Segundo", slug="mi-slug")
    assert response.status_code == 422
    assert "already" in response.text.lower()
    assert "Segundo" in response.text  # the form keeps what was typed
    assert "Segundo" not in editor.get("/admin/posts").text


def test_editing_to_a_taken_slug_is_a_form_error(client_as):
    editor = client_as("editor")
    save_post(editor, title="Primero", slug="primero")
    location = save_post(editor, title="Segundo", slug="segundo").headers["location"]
    response = edit_post(editor, location, title="Segundo", slug="primero",
                         body_md="x")
    assert response.status_code == 422
    assert 'value="segundo"' in editor.get(location).text


def test_slug_can_be_edited_and_is_kept_when_the_title_changes(client_as):
    editor = client_as("editor")
    location = save_post(editor, title="Un título muy largo").headers["location"]
    edit_post(editor, location, title="Un título muy largo", slug="corto",
              body_md="x")
    edit_post(editor, location, title="Otro título", slug="corto", body_md="x")
    page = editor.get(location).text
    assert 'value="corto"' in page and "Otro título" in page


def test_another_editor_can_edit_and_the_author_stays(client_as):
    editor = client_as("editor")
    location = save_post(editor, title="De la editora").headers["location"]
    admin = client_as("admin")
    response = edit_post(admin, location, title="Corregido por admin",
                         slug="de-la-editora", body_md="nuevo")
    assert response.status_code == 303
    table = admin.get("/admin/posts").text.split("<table")[1]
    assert "Corregido por admin" in table
    assert "Demo Editor" in table and "Demo Admin" not in table


def test_preview_sanitizes_markdown_and_keeps_external_images(client_as):
    editor = client_as("editor")
    body = ("Hola\n\n<script>alert('x')</script>\n\n"
            "![foto](https://example.com/foto.png)")
    location = save_post(editor, body=body).headers["location"]
    html = editor.get(f"{location}/preview").text
    assert "<script" not in html
    assert '<img src="https://example.com/foto.png"' in html


def test_preview_uses_the_spanish_layout_and_shows_no_author(client_as):
    editor = client_as("editor")
    location = save_post(editor, title="Cena de gala", kind="event").headers["location"]
    html = editor.get(f"{location}/preview").text
    assert '<html lang="es">' in html
    assert "Cena de gala" in html
    assert "Evento" in html
    assert "Demo Editor" not in html


def test_post_list_shows_last_updated_in_lima_time(client_as):
    editor = client_as("editor")
    lima = ZoneInfo("America/Lima")
    before = datetime.now(lima).strftime("%Y-%m-%d %H:%M")
    save_post(editor)
    after = datetime.now(lima).strftime("%Y-%m-%d %H:%M")
    page = editor.get("/admin/posts").text
    assert before in page or after in page


def test_post_list_shows_every_post_to_every_editor(client_as):
    save_post(client_as("admin"), title="Del admin")
    save_post(client_as("editor"), title="De la editora")
    page = client_as("editor").get("/admin/posts").text
    assert "Del admin" in page and "De la editora" in page


def test_missing_title_and_unknown_kind_are_rejected(client_as):
    editor = client_as("editor")
    assert save_post(editor, title="   ").status_code == 422
    assert save_post(editor, kind="poem").status_code == 422


def test_preview_drops_images_that_are_not_http_or_https(client_as):
    editor = client_as("editor")
    body = "![a](mailto:x@example.com) ![b](data:text/plain,hi) ![c](foto.png)"
    location = save_post(editor, body=body).headers["location"]
    html = editor.get(f"{location}/preview").text
    assert "src=" not in html


def test_an_event_handler_attribute_is_stripped_from_preview_and_export(client_as, tmp_path):
    from tests.test_t03_publish_export import export, publish
    body = "Hola <img src=x onerror=alert(1)>\n\n![foto](https://example.com/foto.png)"
    editor = client_as("editor")
    location = save_post(editor, body=body).headers["location"]
    preview = editor.get(f"{location}/preview").text
    assert "onerror" not in preview and "alert(1)" not in preview
    assert '<img src="https://example.com/foto.png"' in preview  # real images still work

    publish(editor, kind="news", title="Imagen rota", body=body)
    page = (export(tmp_path) / "noticias" / "imagen-rota.html").read_text()
    assert "onerror" not in page and "alert(1)" not in page
