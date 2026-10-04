"""T07: User management (Admin only). Seam 1: the console over HTTP."""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import DEMO_USERS, csrf_from
from tests.test_t03_publish_export import new_post, publish

USERS = "/admin/users"


def add_user(client, *, name="Rosa Quispe", email="rosa@example.test",
             role="editor", password="initial-pw-1"):
    token = csrf_from(client.get(f"{USERS}/new"))
    return client.post(USERS, data={"csrf_token": token, "name": name, "email": email,
                                    "role": role, "password": password},
                       follow_redirects=False)


def user_id(client, email):
    """The id in the row's action URLs, read from the rendered list."""
    html = client.get(USERS).text
    row = next(r for r in html.split("<tr>") if email in r)
    return int(re.search(r"/users/(\d+)/", row).group(1))


def act(client, uid, action, **data):
    token = csrf_from(client.get(USERS))
    return client.post(f"{USERS}/{uid}/{action}", data={"csrf_token": token, **data},
                       follow_redirects=False)


def sign_in(email, password, db_path):
    c = TestClient(create_app(db_path))
    token = csrf_from(c.get("/login"))
    r = c.post("/login", data={"email": email, "password": password,
                               "csrf_token": token}, follow_redirects=False)
    return c, r


# --- Permissions ---------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("get", USERS), ("get", f"{USERS}/new"), ("post", USERS),
    ("post", f"{USERS}/1/role"), ("post", f"{USERS}/1/deactivate"),
    ("post", f"{USERS}/1/reactivate"),
])
def test_an_editor_gets_403_on_every_users_route(client_as, method, path):
    editor = client_as("editor")
    token = csrf_from(editor.get("/admin/posts/new"))
    response = getattr(editor, method)(path, **(
        {"data": {"csrf_token": token, "role": "admin", "name": "x",
                  "email": "x@example.test", "password": "long-enough-pw"}}
        if method == "post" else {}), follow_redirects=False)
    assert response.status_code == 403


def test_a_post_without_a_csrf_token_is_refused(client_as):
    assert client_as("admin").post(USERS, data={
        "name": "x", "email": "x@example.test", "role": "editor",
        "password": "long-enough-pw"}).status_code == 403


# --- Listing and creating --------------------------------------------------

def test_an_admin_sees_every_user_with_role_and_status(client_as):
    html = client_as("admin").get(USERS).text
    assert "admin@example.test" in html and "editor@example.test" in html
    assert "Demo Admin" in html and "Demo Editor" in html
    assert "Active" in html


def test_a_created_user_can_sign_in_with_the_initial_password(client_as, db_path):
    assert add_user(client_as("admin")).status_code == 303
    _, response = sign_in("rosa@example.test", "initial-pw-1", db_path)
    assert response.status_code == 303


def test_the_initial_password_is_stored_only_as_an_argon2_hash(client_as, db_path):
    add_user(client_as("admin"))
    assert b"initial-pw-1" not in db_path.read_bytes()
    assert b"$argon2" in db_path.read_bytes()


@pytest.mark.parametrize("email", ["admin@example.test", "ADMIN@Example.Test"])
def test_an_email_already_in_use_is_a_form_error(client_as, email):
    response = add_user(client_as("admin"), email=email)
    assert response.status_code == 422
    assert "already used" in response.text


@pytest.mark.parametrize("override", [
    {"name": " "}, {"email": "not-an-email"}, {"role": "owner"}, {"password": "short"}])
def test_an_invalid_user_form_is_an_error_and_creates_nothing(client_as, override):
    admin = client_as("admin")
    assert add_user(admin, **override).status_code == 422
    assert "rosa@example.test" not in admin.get(USERS).text


# --- Roles ---------------------------------------------------------------

def test_a_role_change_applies_on_the_users_next_request(client_as, db_path):
    admin = client_as("admin")
    editor = client_as("editor")
    assert editor.get("/admin/pages").status_code == 403
    uid = user_id(admin, DEMO_USERS["editor"]["email"])
    assert act(admin, uid, "role", role="admin").status_code == 303
    assert editor.get("/admin/pages").status_code == 200
    assert editor.get(USERS).status_code == 200
    act(admin, uid, "role", role="editor")
    assert editor.get("/admin/pages").status_code == 403
    assert editor.get(USERS).status_code == 403


def test_an_admin_cannot_demote_themselves(client_as):
    admin = client_as("admin")
    uid = user_id(admin, DEMO_USERS["admin"]["email"])
    response = act(admin, uid, "role", role="editor")
    assert response.status_code == 422
    assert "yourself" in response.text
    assert admin.get("/admin/pages").status_code == 200


# --- Deactivation ----------------------------------------------------------

def test_a_deactivated_user_loses_access_and_reactivation_restores_it(client_as, db_path):
    admin = client_as("admin")
    editor = client_as("editor")
    uid = user_id(admin, DEMO_USERS["editor"]["email"])
    assert act(admin, uid, "deactivate").status_code == 303
    assert "Deactivated" in admin.get(USERS).text
    assert editor.get("/admin", follow_redirects=False).status_code == 303
    _, response = sign_in(DEMO_USERS["editor"]["email"],
                          DEMO_USERS["editor"]["password"], db_path)
    assert response.status_code == 401
    assert act(admin, uid, "reactivate").status_code == 303
    _, response = sign_in(DEMO_USERS["editor"]["email"],
                          DEMO_USERS["editor"]["password"], db_path)
    assert response.status_code == 303


def test_an_admin_cannot_deactivate_themselves(client_as):
    admin = client_as("admin")
    uid = user_id(admin, DEMO_USERS["admin"]["email"])
    response = act(admin, uid, "deactivate")
    assert response.status_code == 422
    assert "yourself" in response.text
    assert admin.get(USERS).status_code == 200


def test_a_deactivated_users_posts_keep_status_and_author(client_as):
    admin = client_as("admin")
    editor = client_as("editor")
    new_post(editor, title="Torneo de apertura")
    act(admin, user_id(admin, DEMO_USERS["editor"]["email"]), "deactivate")
    html = admin.get("/admin/posts").text
    assert "Torneo de apertura" in html and "Demo Editor" in html and "Draft" in html


def test_a_deactivated_users_published_post_stays_published(client_as):
    admin = client_as("admin")
    editor = client_as("editor")
    publish(editor, title="Cena de gala")
    act(admin, user_id(admin, DEMO_USERS["editor"]["email"]), "deactivate")
    row = next(r for r in admin.get("/admin/posts").text.split("<tr>")
               if "Cena de gala" in r)
    assert "Published" in row and "Demo Editor" in row


def test_there_is_no_way_to_delete_a_user(client_as):
    admin = client_as("admin")
    uid = user_id(admin, DEMO_USERS["editor"]["email"])
    assert "delete" not in admin.get(USERS).text.lower()
    token = csrf_from(admin.get(USERS))
    for method in ("post", "delete"):
        response = admin.request(method.upper(), f"{USERS}/{uid}/delete",
                                 headers={"x-csrf-token": token})
        assert response.status_code in (404, 405)
    assert DEMO_USERS["editor"]["email"] in admin.get(USERS).text
