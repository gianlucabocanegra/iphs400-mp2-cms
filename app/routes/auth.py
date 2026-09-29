"""Login and logout."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import accounts, auth
from app.web import templates

router = APIRouter()

GENERIC_ERROR = "Wrong email or password."


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "admin/login.html",
                                      {"title": "Sign in", "error": None})


@router.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form(""),
          conn: sqlite3.Connection = Depends(auth.get_db)):
    user = accounts.authenticate(conn, email, password)
    if user is None:
        return templates.TemplateResponse(
            request, "admin/login.html",
            {"title": "Sign in", "error": GENERIC_ERROR}, status_code=401)
    auth.sign_in(request, user)
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout")
def logout(request: Request, user: sqlite3.Row = Depends(auth.current_user),
           conn: sqlite3.Connection = Depends(auth.get_db)):
    accounts.end_sessions(conn, user["id"])
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
