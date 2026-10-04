"""Every console route sends a signed-out visitor to the login screen."""
import re
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def console_routes():
    """(method, path) for every GET and POST the console answers, read from the app's
    own OpenAPI schema so a new route is covered without anyone remembering to list it."""
    app = create_app(Path(tempfile.mkdtemp()) / "routes.db")
    found = set()
    for path, operations in app.openapi()["paths"].items():
        if path == "/admin" or path.startswith("/admin/"):
            for method in operations:
                if method.upper() in ("GET", "POST"):
                    found.add((method.upper(), re.sub(r"\{[^}]+\}", "1", path)))
    return sorted(found)


ROUTES = console_routes()


def test_the_route_list_is_not_empty_and_includes_the_important_ones():
    paths = {path for _, path in ROUTES}
    for expected in ("/admin", "/admin/posts/new", "/admin/posts/1", "/admin/posts/1/preview",
                     "/admin/pages/new", "/admin/pages/1", "/admin/pages/1/preview",
                     "/admin/users", "/admin/users/new"):
        assert expected in paths, expected


@pytest.mark.parametrize("method, path", ROUTES)
def test_a_signed_out_visitor_is_sent_to_login(client, method, path):
    response = client.request(method, path, follow_redirects=False)
    assert response.status_code == 303, f"{method} {path} -> {response.status_code}"
    assert response.headers["location"] == "/login"
