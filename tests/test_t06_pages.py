"""T06: Pages and Navigation. Seam 1 (console over HTTP) and Seam 2 (render_site)."""
import re
from datetime import date

import pytest

from app.publish import render_site
from tests.conftest import csrf_from
from tests.test_t03_publish_export import all_html, confirm, new_post, post_action
from tests.test_t05_confirmation import ask, not_live

NEW = "/admin/pages/new"
FIXED = ["Inicio", "Noticias", "Eventos", "Menús anteriores"]


def save_page(client, *, title="Reglamento", slug="", body="Reglas", nav_order="0"):
    token = csrf_from(client.get(NEW))
    return client.post("/admin/pages", data={
        "csrf_token": token, "title": title, "slug": slug, "body_md": body,
        "nav_order": nav_order}, follow_redirects=False)


def new_page(client, **kw):
    response = save_page(client, **kw)
    assert response.status_code == 303, response.text
    return response.headers["location"]


def publish_page(client, **kw):
    location = new_page(client, **kw)
    assert post_action(client, location, "publish").status_code == 303
    return location


def export(tmp_path, day=date(2026, 9, 29)):
    return render_site(tmp_path / "site", export_date=day)


def nav_of(path):
    """The (href, label) links of the Navigation in a written page."""
    header = path.read_text().split("<nav>")[1].split("</nav>")[0]
    return re.findall(r'<a href="([^"]+)">([^<]+)</a>', header)


def labels_of(path):
    return [label for _, label in nav_of(path)]


# --- Permissions ---------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("get", "/admin/pages"), ("get", NEW), ("get", "/admin/pages/1"),
    ("post", "/admin/pages"), ("post", "/admin/pages/1"),
    ("post", "/admin/pages/1/publish"), ("post", "/admin/pages/1/unpublish"),
    ("post", "/admin/pages/1/delete"), ("post", "/admin/pages/1/edit"),
    ("get", "/admin/pages/1/preview"),
])
def test_an_editor_gets_403_on_every_page_route(client_as, method, path):
    editor = client_as("editor")
    token = csrf_from(editor.get("/admin/posts/new"))
    response = (editor.get(path) if method == "get" else
                editor.post(path, data={"csrf_token": token, "title": "x"}))
    assert response.status_code == 403


def test_an_editor_creating_a_page_by_direct_post_creates_nothing(client_as):
    editor, admin = client_as("editor"), client_as("admin")
    token = csrf_from(editor.get("/admin/posts/new"))
    editor.post("/admin/pages", data={"csrf_token": token, "title": "Intruso",
                                      "body_md": "x"})
    assert "Intruso" not in admin.get("/admin/pages").text


# --- Lifecycle -----------------------------------------------------------

def test_admin_creates_a_draft_page_and_sees_it_listed_with_its_author(client_as):
    admin = client_as("admin")
    location = new_page(admin, title="Reglamento", nav_order="2")
    assert "Draft" in admin.get(location).text
    listing = admin.get("/admin/pages").text
    assert "Reglamento" in listing and "Draft" in listing and "Author" in listing


def test_admin_publishes_and_unpublishes_a_page_with_confirmation(client_as):
    admin = client_as("admin")
    location = new_page(admin)
    screen = ask(admin, location, "publish", title="Reglamento", slug="reglamento",
                 body_md="Reglas", nav_order="0")
    assert screen.status_code == 200 and "Confirm" in screen.text
    assert "Status: Draft" in admin.get(location).text  # nothing changed yet
    assert confirm(admin, screen).status_code == 303
    assert "Status: Published" in admin.get(location).text
    assert post_action(admin, location, "unpublish").status_code == 303
    assert "Status: Draft" in admin.get(location).text


def test_saving_a_published_page_needs_confirmation_and_a_draft_does_not(client_as):
    admin = client_as("admin")
    location = new_page(admin, body="Antes")
    values = dict(title="Reglamento", slug="reglamento", nav_order="0")
    assert ask(admin, location, "", body_md="Draft edit", **values).status_code == 303
    assert post_action(admin, location, "publish").status_code == 303
    screen = ask(admin, location, "", body_md="Despues", **values)
    assert screen.status_code == 200 and "Despues" in screen.text
    assert "Draft edit" in admin.get(location).text  # stored page unchanged
    assert confirm(admin, screen).status_code == 303
    assert "Despues" in admin.get(location).text


def test_cancel_on_a_page_confirmation_returns_to_the_editor_with_the_values(client_as):
    admin = client_as("admin")
    location = publish_page(admin)
    screen = ask(admin, location, "", title="Reglamento", slug="reglamento",
                 body_md="Sin guardar", nav_order="0")
    back = admin.post(f"{location}/edit", data={
        "csrf_token": csrf_from(screen), "title": "Reglamento", "slug": "reglamento",
        "body_md": "Sin guardar", "nav_order": "0"})
    assert back.status_code == 200 and "Sin guardar" in back.text


def test_deleting_a_page_needs_confirmation_that_says_permanent(client_as):
    admin = client_as("admin")
    location = new_page(admin)
    screen = ask(admin, location, "delete")
    assert screen.status_code == 200 and "permanent" in screen.text
    assert admin.get(location).status_code == 200
    assert confirm(admin, screen).status_code == 303
    assert admin.get(location).status_code == 404


def test_preview_shows_the_page_sanitized_for_members(client_as):
    admin = client_as("admin")
    location = new_page(admin, title="Acerca", body="<script>alert(1)</script>Hola")
    preview = admin.get(f"{location}/preview")
    assert preview.status_code == 200
    assert "Acerca" in preview.text and "Hola" in preview.text
    assert "<script>alert" not in preview.text


def test_nav_order_must_be_a_whole_number(client_as):
    response = save_page(client_as("admin"), nav_order="primero")
    assert response.status_code == 422 and "order" in response.text.lower()


# --- Slugs ---------------------------------------------------------------

@pytest.mark.parametrize("reserved", ["index", "noticias", "eventos", "menus", "style"])
def test_a_reserved_page_slug_is_rejected(client_as, reserved):
    admin = client_as("admin")
    typed = save_page(admin, title="Algo", slug=reserved)
    assert typed.status_code == 422 and "reserved" in typed.text
    generated = save_page(admin, title=reserved.capitalize())
    assert generated.status_code == 422 and "reserved" in generated.text


def test_the_slug_is_generated_from_the_title_with_accents_stripped(client_as):
    admin = client_as("admin")
    location = new_page(admin, title="Cómo asociarse")
    assert 'value="como-asociarse"' in admin.get(location).text


def test_a_generated_slug_clash_gets_a_number_and_a_typed_clash_is_an_error(client_as):
    admin = client_as("admin")
    new_page(admin, title="Reglamento")
    second = new_page(admin, title="Reglamento")
    assert 'value="reglamento-2"' in admin.get(second).text
    clash = save_page(admin, title="Otra", slug="reglamento")
    assert clash.status_code == 422 and "already used" in clash.text


def test_the_slug_is_locked_after_first_publish_even_when_unpublished(client_as):
    admin = client_as("admin")
    location = publish_page(admin, title="Reglamento")
    values = dict(title="Reglamento", body_md="x", nav_order="0", slug="otro")
    assert confirm(admin, ask(admin, location, "", **values)).status_code == 303
    assert 'value="reglamento"' in admin.get(location).text
    assert post_action(admin, location, "unpublish").status_code == 303
    assert ask(admin, location, "", **values).status_code == 303
    assert 'value="reglamento"' in admin.get(location).text


def test_the_slug_can_be_edited_before_first_publish(client_as):
    admin = client_as("admin")
    location = new_page(admin, title="Reglamento")
    response = ask(admin, location, "", title="Reglamento", slug="reglas",
                   body_md="x", nav_order="0")
    assert response.status_code == 303
    assert 'value="reglas"' in admin.get(location).text


# --- Export and Navigation -----------------------------------------------

def test_a_published_page_is_written_to_the_site_root_and_a_draft_is_not(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, title="Reglamento", body="Reglas del club")
    new_page(admin, title="Borrador secreto", body="Nadie lo ve")
    out = export(tmp_path)
    assert "Reglas del club" in (out / "reglamento.html").read_text()
    assert not (out / "borrador-secreto.html").exists()
    assert "Borrador secreto" not in all_html(out)


def test_an_unpublished_page_leaves_the_site_and_the_navigation(client_as, tmp_path):
    admin = client_as("admin")
    location = publish_page(admin, title="Reglamento")
    assert post_action(admin, location, "unpublish").status_code == 303
    out = export(tmp_path)
    assert not (out / "reglamento.html").exists()
    assert "Reglamento" not in all_html(out)


def test_a_deleted_page_leaves_the_site(client_as, tmp_path):
    admin = client_as("admin")
    location = publish_page(admin, title="Reglamento")
    assert post_action(admin, location, "delete").status_code == 303
    assert not (export(tmp_path) / "reglamento.html").exists()


def test_navigation_lists_the_fixed_entries_then_pages_by_order_then_title(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, title="Sobre nosotros", nav_order="2")
    publish_page(admin, title="Zeta", nav_order="1")
    publish_page(admin, title="Alfa", nav_order="1")
    publish_page(admin, title="Primero", nav_order="-5")
    new_page(admin, title="Oculta", nav_order="0")
    out = export(tmp_path)
    assert labels_of(out / "index.html") == FIXED + ["Primero", "Alfa", "Zeta",
                                                      "Sobre nosotros"]


def test_navigation_ties_sort_by_title_ignoring_accents_and_case(client_as, tmp_path):
    admin = client_as("admin")
    for title in ("Zeta", "Órdenes", "beta", "Álbum"):
        publish_page(admin, title=title)
    labels = labels_of(export(tmp_path) / "index.html")
    assert labels[len(FIXED):] == ["Álbum", "beta", "Órdenes", "Zeta"]


def test_navigation_is_the_fixed_entries_alone_when_no_page_is_published(client_as, tmp_path):
    assert labels_of(export(tmp_path) / "index.html") == FIXED


def test_every_public_page_shows_the_same_navigation_with_working_relative_links(client_as, tmp_path):
    admin, editor = client_as("admin"), client_as("editor")
    publish_page(admin, title="Reglamento")
    news = new_post(editor, kind="news", title="Noticia")
    assert post_action(editor, news, "publish").status_code == 303
    out = export(tmp_path)
    expected = labels_of(out / "index.html")
    assert "Reglamento" in expected
    pages = list(out.rglob("*.html"))
    assert len(pages) > 5
    for path in pages:
        assert labels_of(path) == expected, path
        for href, _ in nav_of(path):
            assert not href.startswith("/"), (path, href)
            assert (path.parent / href).resolve().exists(), (path, href)


def test_page_links_from_inside_a_feed_folder_go_up_a_level(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, title="Reglamento")
    out = export(tmp_path)
    inside = {label: href for href, label in nav_of(out / "noticias" / "index.html")}
    assert inside["Reglamento"] == "../reglamento.html"
    assert inside["Inicio"] == "../index.html"
    top = {label: href for href, label in nav_of(out / "index.html")}
    assert top["Reglamento"] == "reglamento.html"


def test_page_html_has_no_author_and_no_root_absolute_paths(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, title="Reglamento")
    text = (export(tmp_path) / "reglamento.html").read_text()
    assert "admin@" not in text
    assert not re.search(r'(?:href|src)="/', text)


# --- Not yet Live --------------------------------------------------------

def test_a_page_change_counts_as_not_yet_live_until_the_next_export(client_as, tmp_path):
    admin = client_as("admin")
    publish_page(admin, title="Reglamento")
    assert not_live(admin) == 1
    export(tmp_path)
    assert not_live(admin) == 0


def test_a_page_post_without_a_csrf_token_is_refused(client_as):
    admin = client_as("admin")
    location = new_page(admin)
    form = {"title": "Reglamento", "slug": "", "body_md": "x", "nav_order": "0"}
    assert admin.post("/admin/pages", data=form).status_code == 403
    assert admin.post(location, data=form).status_code == 403
    assert admin.post(f"{location}/publish", data=form).status_code == 403
    assert admin.post(f"{location}/delete", data=form).status_code == 403
    assert admin.get(location).status_code == 200  # nothing was deleted
