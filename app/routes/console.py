"""The console: every route here requires a signed-in User.

The router-level dependency is what guarantees that, so a new route can't
forget it. Users is an Admin-only placeholder until T07.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from app import auth, content
from app.routes import pages, posts
from app.web import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(auth.current_user)])
# Before the catch-all 404 at the bottom of this file.
router.include_router(posts.router)
router.include_router(pages.router)


def page(request: Request, template: str, user: sqlite3.Row, title: str, **ctx):
    return templates.TemplateResponse(request, template,
                                      {"title": title, "user": user, **ctx})


@router.get("")
def dashboard(request: Request, user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    return page(request, "admin/dashboard.html", user, "Dashboard",
                not_live=content.changes_not_live(conn))


@router.get("/users", dependencies=[Depends(auth.require_admin)])
def users(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return page(request, "admin/placeholder.html", user, "Users")


@router.get("/{path:path}")
def not_found(path: str):
    # Signed-out visitors were already redirected; this is a real 404.
    raise HTTPException(404, "Not found")
