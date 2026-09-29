"""T01: login, logout, the two roles, and CSRF — all through the console over HTTP."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import accounts
from app.main import create_app
from tests.conftest import DEMO_USERS, csrf_from

ROOT = Path(__file__).resolve().parents[1]
ADMIN = DEMO_USERS["admin"]


def sign_in(client, email, password):
    token = csrf_from(client.get("/login"))
    return client.post("/login", data={"email": email, "password": password,
                                       "csrf_token": token},
                       follow_redirects=False)


def test_login_redirects_into_the_console(client):
    response = sign_in(client, ADMIN["email"], ADMIN["password"])
    assert response.status_code == 303
    assert client.get("/admin").status_code == 200


def test_email_is_case_insensitive(client):
    response = sign_in(client, ADMIN["email"].upper(), ADMIN["password"])
    assert response.status_code == 303


def test_wrong_email_and_wrong_password_look_identical(client):
    unknown = sign_in(client, "nobody@example.test", "whatever")
    wrong_pw = sign_in(client, ADMIN["email"], "not-the-password")
    assert unknown.status_code == wrong_pw.status_code == 401
    for response in (unknown, wrong_pw):
        assert "wrong email or password" in response.text.lower()
    assert "wrong email or password" not in client.get("/login").text.lower()


def test_password_never_appears_in_response_or_logs(client, caplog):
    caplog.set_level("DEBUG")
    bad = "hunter2-very-secret"
    response = sign_in(client, ADMIN["email"], bad)
    assert bad not in response.text
    assert bad not in caplog.text
    ok = sign_in(client, ADMIN["email"], ADMIN["password"])
    assert ADMIN["password"] not in ok.text
    assert ADMIN["password"] not in caplog.text


def test_passwords_are_stored_as_argon2_hashes(db_path):
    # The one place a test reads storage: the criterion is about storage itself.
    rows = sqlite3.connect(db_path).execute(
        "SELECT password_hash FROM users").fetchall()
    assert rows
    for (stored,) in rows:
        assert stored.startswith("$argon2")
        assert "test-admin-pw" not in stored and "test-editor-pw" not in stored


def test_logout_ends_the_session(client_as):
    c = client_as("admin")
    assert c.get("/admin").status_code == 200
    token = csrf_from(c.get("/admin"))
    assert c.post("/logout", data={"csrf_token": token},
                  follow_redirects=False).status_code == 303
    later = c.get("/admin", follow_redirects=False)
    assert later.status_code == 303 and later.headers["location"] == "/login"


def test_logout_invalidates_a_copied_session_cookie(client_as, db_path):
    c = client_as("admin")
    stolen = dict(c.cookies)
    c.post("/logout", data={"csrf_token": csrf_from(c.get("/admin"))})
    replay = TestClient(create_app(db_path), cookies=stolen)
    assert replay.get("/admin", follow_redirects=False).status_code == 303


@pytest.mark.parametrize("path", ["/admin", "/admin/pages", "/admin/users",
                                  "/admin/anything-else"])
def test_signed_out_visitor_is_sent_to_login(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_deactivated_user_cannot_sign_in(client, db_path):
    accounts.set_active(db_path, DEMO_USERS["editor"]["email"], False)
    response = sign_in(client, DEMO_USERS["editor"]["email"],
                       DEMO_USERS["editor"]["password"])
    assert response.status_code == 401
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_user_deactivated_while_signed_in_is_refused_next_request(client_as, db_path):
    c = client_as("editor")
    assert c.get("/admin").status_code == 200
    accounts.set_active(db_path, DEMO_USERS["editor"]["email"], False)
    response = c.get("/admin", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"


@pytest.mark.parametrize("path", ["/admin/pages", "/admin/users"])
def test_editor_is_refused_from_admin_areas_and_admin_is_not(client_as, path):
    assert client_as("editor").get(path).status_code == 403
    assert client_as("admin").get(path).status_code == 200


def test_editor_can_reach_the_dashboard(client_as):
    assert client_as("editor").get("/admin").status_code == 200


def test_editor_does_not_see_admin_navigation(client_as):
    html = client_as("editor").get("/admin").text
    assert "/admin/users" not in html and "/admin/pages" not in html


def test_login_without_a_valid_csrf_token_is_rejected(client):
    creds = {"email": ADMIN["email"], "password": ADMIN["password"]}
    assert client.post("/login", data=creds).status_code == 403
    client.get("/login")
    assert client.post("/login", data={**creds, "csrf_token": "forged"}
                       ).status_code == 403
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_logout_without_a_valid_csrf_token_is_rejected(client_as):
    c = client_as("admin")
    assert c.post("/logout").status_code == 403
    assert c.post("/logout", data={"csrf_token": "forged"}).status_code == 403
    assert c.get("/admin").status_code == 200  # still signed in


def test_a_token_from_another_session_is_rejected(client_as, db_path):
    other = TestClient(create_app(db_path))
    foreign = csrf_from(other.get("/login"))
    c = client_as("admin")
    assert c.post("/logout", data={"csrf_token": foreign}).status_code == 403


def test_each_app_gets_its_own_database(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    accounts.seed_users(a, admin_password="pw-a", editor_password="pw-e")
    ca, cb = TestClient(create_app(a)), TestClient(create_app(b))
    assert sign_in(ca, ADMIN["email"], "pw-a").status_code == 303
    assert sign_in(cb, ADMIN["email"], "pw-a").status_code == 401


def run_seed(tmp_path, **env):
    clean = {k: v for k, v in os.environ.items()
             if k not in ("CMS_ADMIN_PASSWORD", "CMS_EDITOR_PASSWORD")}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_demo.py")],
        env={**clean, "CMS_DATABASE": str(tmp_path / "seeded.db"),
             "CMS_ENV_FILE": str(tmp_path / "no.env"), **env},
        capture_output=True, text=True, cwd=ROOT)


def test_seed_refuses_without_passwords(tmp_path):
    result = run_seed(tmp_path)
    assert result.returncode != 0
    assert not (tmp_path / "seeded.db").exists()


def test_seed_creates_admin_and_editor_from_environment(tmp_path):
    result = run_seed(tmp_path, CMS_ADMIN_PASSWORD="seed-admin-pw",
                      CMS_EDITOR_PASSWORD="seed-editor-pw")
    assert result.returncode == 0, result.stderr
    assert "seed-admin-pw" not in result.stdout + result.stderr
    app = create_app(tmp_path / "seeded.db")
    assert sign_in(TestClient(app), ADMIN["email"], "seed-admin-pw").status_code == 303
    assert sign_in(TestClient(app), DEMO_USERS["editor"]["email"],
                   "seed-editor-pw").status_code == 303
    # Running it twice is harmless.
    again = run_seed(tmp_path, CMS_ADMIN_PASSWORD="seed-admin-pw",
                     CMS_EDITOR_PASSWORD="seed-editor-pw")
    assert again.returncode == 0
