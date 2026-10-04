"""User list, creation, role changes and Deactivation. Admin only.

Users are never deleted, so there is deliberately no delete route.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import accounts, auth
from app.web import templates

router = APIRouter(prefix="/users", dependencies=[Depends(auth.require_admin)])

BLANK = {"name": "", "email": "", "role": "editor"}


def user_list(request: Request, user: sqlite3.Row, conn: sqlite3.Connection, *,
              error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "admin/user_list.html",
        {"title": "Users", "user": user, "users": accounts.list_users(conn),
         "error": error}, status_code=status_code)


def load(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    target = accounts.get_user(conn, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    return target


def refuse_self(user: sqlite3.Row, target: sqlite3.Row, what: str) -> None:
    """The club always keeps an Admin: nobody deactivates or demotes themselves."""
    if user["id"] == target["id"]:
        raise accounts.UserError(
            f"You can’t {what} yourself. Ask another Admin, so the club always has an Admin.")


@router.get("")
def users(request: Request, user: sqlite3.Row = Depends(auth.current_user),
          conn: sqlite3.Connection = Depends(auth.get_db)):
    return user_list(request, user, conn)


@router.get("/new")
def new_user(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return templates.TemplateResponse(
        request, "admin/user_form.html",
        {"title": "New user", "user": user, "form": BLANK, "error": None})


@router.post("")
def create_user(request: Request, name: str = Form(""), email: str = Form(""),
                role: str = Form(""), password: str = Form(""),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    try:
        accounts.add_user(conn, name=name, email=email, role=role, password=password)
    except accounts.UserError as exc:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            {"title": "New user", "user": user, "error": str(exc),
             "form": {"name": name, "email": email, "role": role}}, status_code=422)
    return RedirectResponse(request.app.url_path_for("users"), status_code=303)


@router.post("/{user_id}/role")
def change_role(request: Request, user_id: int, role: str = Form(""),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    target = load(conn, user_id)
    try:
        if role != target["role"]:
            refuse_self(user, target, "change the role of")
        accounts.change_role(conn, user_id, role)
    except accounts.UserError as exc:
        return user_list(request, user, conn, error=str(exc), status_code=422)
    return RedirectResponse(request.app.url_path_for("users"), status_code=303)


@router.post("/{user_id}/deactivate")
def deactivate(request: Request, user_id: int,
               user: sqlite3.Row = Depends(auth.current_user),
               conn: sqlite3.Connection = Depends(auth.get_db)):
    target = load(conn, user_id)
    try:
        refuse_self(user, target, "deactivate")
    except accounts.UserError as exc:
        return user_list(request, user, conn, error=str(exc), status_code=422)
    accounts.set_user_active(conn, user_id, False)
    return RedirectResponse(request.app.url_path_for("users"), status_code=303)


@router.post("/{user_id}/reactivate")
def reactivate(request: Request, user_id: int,
               user: sqlite3.Row = Depends(auth.current_user),
               conn: sqlite3.Connection = Depends(auth.get_db)):
    load(conn, user_id)
    accounts.set_user_active(conn, user_id, True)
    return RedirectResponse(request.app.url_path_for("users"), status_code=303)
