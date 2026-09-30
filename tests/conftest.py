"""Shared test fixtures.

Each test gets its own temporary database, seeded with the demo Admin and
Editor, so tests never share state.

`client` gives you an anonymous client. `client_as(role)` gives you a client
that is signed in as a seeded user of that role, so access-control tests stay
one line:

    def test_editor_cannot_manage_users(client_as):
        assert client_as("editor").get("/admin/users").status_code == 403
"""
from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

# A developer's real .env must not change test behaviour.
os.environ.setdefault("CMS_ENV_FILE", os.devnull)

from app import settings  # noqa: E402
from app.accounts import seed_users  # noqa: E402
from app.main import create_app  # noqa: E402

# Matches scripts/seed_demo.py. Passwords come from the environment there; in
# tests they are fixed and meaningless.
DEMO_USERS = {
    "admin": {"email": "admin@example.test", "password": "test-admin-pw"},
    "editor": {"email": "editor@example.test", "password": "test-editor-pw"},
}

CSRF_FIELD = re.compile(r'name="csrf_token" value="([^"]+)"')


def csrf_from(response) -> str:
    """Pull the CSRF token out of a rendered form."""
    match = CSRF_FIELD.search(response.text)
    assert match, "no csrf_token field in the page"
    return match.group(1)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    seed_users(path, admin_password=DEMO_USERS["admin"]["password"],
               editor_password=DEMO_USERS["editor"]["password"])
    return path


@pytest.fixture(autouse=True)
def _configured_database(db_path, monkeypatch):
    """render_site reads the configured database; point it at this test's own."""
    monkeypatch.setattr(settings, "DATABASE_PATH", db_path)


@pytest.fixture
def client(db_path) -> TestClient:
    return TestClient(create_app(db_path))


@pytest.fixture
def client_as(db_path):
    """Return a factory: client_as("editor") -> a signed-in TestClient."""

    def _login(role: str) -> TestClient:
        user = DEMO_USERS[role]
        c = TestClient(create_app(db_path))
        token = csrf_from(c.get("/login"))
        response = c.post("/login", data={"email": user["email"],
                                          "password": user["password"],
                                          "csrf_token": token},
                          follow_redirects=False)
        assert response.status_code in (302, 303), (
            f"Login as {role} failed with {response.status_code}")
        return c

    return _login
