"""Post list, editor and Preview. Editors and Admins can do all of it."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import auth, content
from app.markdown import render_markdown
from app.web import templates

router = APIRouter(prefix="/posts")

KIND_LABELS = {"news": "News", "event": "Event", "menu": "Menu"}
KIND_LABELS_ES = {"news": "Noticia", "event": "Evento", "menu": "Menú de la semana"}


def form_page(request: Request, user: sqlite3.Row, post: dict, *,
              error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "admin/post_form.html",
        {"title": "Edit post" if post.get("id") else "New post", "user": user,
         "post": post, "error": error,
         "kind_labels": KIND_LABELS},
        status_code=status_code)


def load(conn: sqlite3.Connection, post_id: int) -> sqlite3.Row:
    post = content.get_post(conn, post_id)
    if post is None:
        raise HTTPException(404, "Post not found")
    return post


@router.get("")
def post_list(request: Request, user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    return templates.TemplateResponse(
        request, "admin/post_list.html",
        {"title": "Posts", "user": user, "posts": content.list_posts(conn),
         "kind_labels": KIND_LABELS})


@router.get("/new")
def new_post(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return form_page(request, user, {"kind": "news", "title": "", "slug": "",
                                     "body_md": ""})


@router.post("")
def create_post(request: Request, kind: str = Form(""), title: str = Form(""),
                slug: str = Form(""), body_md: str = Form(""),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    try:
        post_id = content.create_post(conn, kind=kind, title=title, slug=slug,
                                      body_md=body_md, author_id=user["id"])
    except content.PostError as exc:
        return form_page(request, user, {"kind": kind, "title": title,
                                         "slug": slug, "body_md": body_md},
                         error=str(exc), status_code=422)
    return RedirectResponse(f"/admin/posts/{post_id}", status_code=303)


@router.get("/{post_id}")
def edit_post(request: Request, post_id: int,
              user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    return form_page(request, user, dict(load(conn, post_id)))


@router.post("/{post_id}")
def save_post(request: Request, post_id: int, title: str = Form(""),
              slug: str = Form(""), body_md: str = Form(""),
              user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    try:
        content.update_post(conn, post, title=title, slug=slug, body_md=body_md)
    except content.PostError as exc:
        return form_page(request, user, {**dict(post), "title": title,
                                         "slug": slug, "body_md": body_md},
                         error=str(exc), status_code=422)
    return RedirectResponse(f"/admin/posts/{post_id}", status_code=303)


@router.get("/{post_id}/preview")
def preview(request: Request, post_id: int,
            conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    return templates.TemplateResponse(
        request, "public/post.html",
        {"title": post["title"], "lang": "es", "css_path": "/style.css",
         "home_path": "/", "post": post,
         "kind_label": KIND_LABELS_ES[post["kind"]],
         "body_html": render_markdown(post["body_md"])})
