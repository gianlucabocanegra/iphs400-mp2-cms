"""After a successful save the next console page says so, once."""
import re

from tests.conftest import csrf_from
from tests.test_t02_posts import save_post
from tests.test_t06_pages import new_page, save_page

USERS = "/admin/users"


def messages(response):
    return re.findall(r'<p role="status" class="flash">([^<]+)</p>', response.text)


def save_form(client, location, **fields):
    token = csrf_from(client.get(location))
    return client.post(location, data={"csrf_token": token, **fields}, follow_redirects=False)


def test_creating_a_post_says_so_once(client_as):
    editor = client_as("editor")
    location = save_post(editor, title="Aviso").headers["location"]
    assert messages(editor.get(location)) == ["Post created as a Draft."]
    assert messages(editor.get(location)) == []  # gone on the next page


def test_saving_a_post_says_so(client_as):
    editor = client_as("editor")
    location = save_post(editor, title="Aviso").headers["location"]
    editor.get(location)  # reads the "created" message
    saved = save_form(editor, location, title="Aviso", slug="aviso", body_md="nuevo")
    assert saved.status_code == 303
    assert messages(editor.get(saved.headers["location"])) == ["Post saved."]


def test_creating_and_saving_a_page_say_so(client_as):
    admin = client_as("admin")
    location = new_page(admin, title="Reglas")
    assert messages(admin.get(location)) == ["Page created as a Draft."]
    saved = save_form(admin, location, title="Reglas", slug="reglas", body_md="x", nav_order="2")
    assert messages(admin.get(saved.headers["location"])) == ["Page saved."]


def test_creating_a_user_and_changing_a_role_say_so(client_as):
    admin = client_as("admin")
    token = csrf_from(admin.get(f"{USERS}/new"))
    created = admin.post(USERS, data={"csrf_token": token, "name": "Nueva", "role": "editor",
                                      "email": "nueva@example.test", "password": "long-enough-pw"},
                         follow_redirects=False)
    assert messages(admin.get(created.headers["location"])) == ["User created."]
    new_id = max(map(int, re.findall(r"/admin/users/(\d+)/role", admin.get(USERS).text)))
    changed = admin.post(f"{USERS}/{new_id}/role", follow_redirects=False,
                         data={"csrf_token": csrf_from(admin.get(USERS)), "role": "admin"})
    assert messages(admin.get(changed.headers["location"])) == ["Role updated."]


def test_a_failed_save_shows_an_error_and_no_success_message(client_as):
    admin = client_as("admin")
    response = save_page(admin, title="")
    assert response.status_code == 422 and 'role="alert"' in response.text
    assert messages(admin.get("/admin/pages")) == []


def test_every_console_page_loads_the_stylesheet_from_the_site_root(client_as):
    admin = client_as("admin")
    for path in ("/admin", "/admin/posts", "/admin/posts/new", "/admin/users", "/admin/pages"):
        assert 'href="/style.css"' in admin.get(path).text, path
    assert admin.get("/style.css").status_code == 200
