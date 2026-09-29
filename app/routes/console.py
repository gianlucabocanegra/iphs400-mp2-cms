"""The console: every route here requires a signed-in User.

The router-level dependency is what guarantees that, so a new route can't
forget it. Pages and Users are Admin-only placeholders until T06 and T07.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from app import auth
from app.routes import posts
from app.web import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(auth.current_user)])
# Before the catch-all 404 at the bottom of this file.
router.include_router(posts.router)


def page(request: Request, template: str, user: sqlite3.Row, title: str):
    return templates.TemplateResponse(request, template,
                                      {"title": title, "user": user})


@router.get("")
def dashboard(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return page(request, "admin/dashboard.html", user, "Dashboard")


@router.get("/pages", dependencies=[Depends(auth.require_admin)])
def pages(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return page(request, "admin/placeholder.html", user, "Pages")


@router.get("/users", dependencies=[Depends(auth.require_admin)])
def users(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return page(request, "admin/placeholder.html", user, "Users")


@router.get("/{path:path}")
def not_found(path: str):
    # Signed-out visitors were already redirected; this is a real 404.
    raise HTTPException(404, "Not found")
