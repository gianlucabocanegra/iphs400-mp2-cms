"""Permissions and CSRF: the checks shared by every route.

- `csrf_protect` runs on every state-changing request in the app.
- `current_user` is what makes a console route require login, and refuses a
  Deactivated User on every request.
- `require_admin` is the role check for Admin-only areas. Refusal is a 403.
"""
from __future__ import annotations

import hmac
import secrets
import sqlite3
from typing import Iterator

from fastapi import Depends, HTTPException, Request

from app import accounts, db

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class LoginRequired(Exception):
    """Raised when a request needs a signed-in User and has none."""


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def csrf_token(request: Request) -> str:
    """This session's CSRF token, created on first use."""
    token = request.session.get("csrf")
    if not token:
        token = request.session["csrf"] = secrets.token_urlsafe(32)
    return token


async def csrf_protect(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    if request.url.path.startswith("/admin") and not request.session.get("user_id"):
        raise LoginRequired()  # a signed-out visitor is sent to login, not told "bad token"
    sent = request.headers.get("x-csrf-token")
    if sent is None:
        sent = (await request.form()).get("csrf_token")
    expected = request.session.get("csrf")
    if (not expected or not isinstance(sent, str)
            or not hmac.compare_digest(sent, expected)):
        raise HTTPException(403, "Invalid or missing CSRF token.")


def sign_in(request: Request, user: sqlite3.Row) -> None:
    # Fresh session and token on login, so nothing set before it carries over.
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["session_version"] = user["session_version"]
    request.session["csrf"] = secrets.token_urlsafe(32)


def current_user(request: Request,
                 conn: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row:
    user_id = request.session.get("user_id")
    user = accounts.get_user(conn, user_id) if user_id else None
    if (user is None or not user["active"]
            or user["session_version"] != request.session.get("session_version")):
        request.session.clear()
        raise LoginRequired()
    return user


def require_admin(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
    if user["role"] != "admin":
        raise HTTPException(403, "This area is for Admins only.")
    return user
