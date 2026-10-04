"""Post list, editor and Preview. Editors and Admins can do all of it."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import auth, content
from app.markdown import render_markdown
from app.timeutil import fecha_evento
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


EDITOR_FIELDS = ("title", "slug", "body_md", "event_start_date", "event_start_time",
                 "event_end_date")


async def pending_values(request: Request) -> dict | None:
    """The editor's values as submitted, or None if the form carried none.

    Read from the raw form: FastAPI turns an empty optional Form field into
    None, which would make a blank title look like "no values sent".
    """
    form = await request.form()
    if "title" not in form:
        return None
    return {name: str(form.get(name) or "") for name in EDITOR_FIELDS}


def clean(conn: sqlite3.Connection, post: sqlite3.Row, values: dict) -> dict:
    """Validate the editor's values (everything but the body) without saving."""
    return content.clean_update(conn, post, **{k: v for k, v in values.items()
                                               if k != "body_md"})


def article_context(post: dict) -> dict:
    """What public/_article.html needs to show a Post as Members will see it."""
    return {"post": post, "date_label": None, "kind_label": KIND_LABELS_ES[post["kind"]],
            "event_label": fecha_evento(post["event_start_date"], post["event_start_time"],
                                        post["event_end_date"]),
            "body_html": render_markdown(post["body_md"])}


def changes(post: sqlite3.Row, cleaned: dict, body_md: str) -> list[str]:
    """Plain-language list of what saving would change."""
    labels = {"title": "Title", "slug": "Slug", "event_start_date": "Start date",
              "event_start_time": "Start time", "event_end_date": "End date"}
    lines = [f"{label}: “{post[key] or ''}” → “{cleaned[key] or ''}”"
             for key, label in labels.items() if (post[key] or "") != (cleaned[key] or "")]
    if post["body_md"] != body_md:
        lines.append("Body: changed (see the preview below)")
    return lines or ["No changes."]


def confirmation(request: Request, user: sqlite3.Row, post: sqlite3.Row, *, action: str,
                 heading: str, summary: list[str], pending: dict | None,
                 button: str, preview: dict | None = None):
    """The Confirmation screen: nothing has been changed yet.

    It carries the pending values in hidden fields. Only a second POST with the
    confirm flag applies the change; Cancel reopens the editor with the values.
    """
    return templates.TemplateResponse(
        request, "admin/confirm.html",
        {"title": heading, "user": user, "post": post, "summary": summary,
         "pending": pending or {}, "action": action, "button": button,
         "preview": preview and article_context(preview)})


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
                                     "body_md": "", "event_start_date": "",
                                     "event_start_time": "", "event_end_date": ""})


@router.post("")
def create_post(request: Request, kind: str = Form(""), title: str = Form(""),
                slug: str = Form(""), body_md: str = Form(""),
                event_start_date: str = Form(""), event_start_time: str = Form(""),
                event_end_date: str = Form(""),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    event = dict(event_start_date=event_start_date, event_start_time=event_start_time,
                 event_end_date=event_end_date)
    try:
        post_id = content.create_post(conn, kind=kind, title=title, slug=slug,
                                      body_md=body_md, author_id=user["id"], **event)
    except content.PostError as exc:
        return form_page(request, user, {"kind": kind, "title": title,
                                         "slug": slug, "body_md": body_md, **event},
                         error=str(exc), status_code=422)
    return RedirectResponse(f"/admin/posts/{post_id}", status_code=303)


@router.get("/{post_id}")
def edit_post(request: Request, post_id: int,
              user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    return form_page(request, user, dict(load(conn, post_id)))


def editor_page(request, user, post: sqlite3.Row, values: dict | None, error: str,
                status_code: int = 422):
    return form_page(request, user, {**dict(post), **(values or {})}, error=error,
                     status_code=status_code)


@router.post("/{post_id}")
def save_post(request: Request, post_id: int, confirm: str = Form(""),
              values: dict | None = Depends(pending_values),
              user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    values = values or {k: "" for k in EDITOR_FIELDS}
    try:
        cleaned = clean(conn, post, values)
        if post["status"] == "published" and not confirm:
            return confirmation(
                request, user, post, action="save_post", button="Save changes",
                heading="Confirm changes to Published post", pending=values,
                summary=["This post is Published. Saving changes what Members see "
                         "at the next Export.", *changes(post, cleaned, values["body_md"])],
                preview={**dict(post), **cleaned, "body_md": values["body_md"]})
        content.update_post(conn, post, **values)
    except content.PostError as exc:
        return editor_page(request, user, post, values, str(exc))
    return RedirectResponse(f"/admin/posts/{post_id}", status_code=303)


@router.post("/{post_id}/edit")
def back_to_editor(request: Request, post_id: int,
                   values: dict | None = Depends(pending_values),
                   user: sqlite3.Row = Depends(auth.current_user),
                   conn: sqlite3.Connection = Depends(auth.get_db)):
    """Cancel on a Confirmation screen: the editor again, with the unsaved values."""
    return form_page(request, user, {**dict(load(conn, post_id)), **(values or {})})


@router.post("/{post_id}/publish")
def publish_post(request: Request, post_id: int, confirm: str = Form(""),
                 values: dict | None = Depends(pending_values),
                 user: sqlite3.Row = Depends(auth.current_user),
                 conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    try:
        if values is not None:  # what's on the editor is what gets published
            cleaned = clean(conn, post, values)
        if not confirm:
            shown = {**dict(post), **(cleaned if values is not None else {}),
                     **({"body_md": values["body_md"]} if values is not None else {})}
            return confirmation(
                request, user, post, action="publish_post", button="Publish",
                heading="Confirm publishing", pending=values, preview=shown,
                summary=[f"Publish “{shown['title']}”? It stays a Draft until you confirm, "
                         "and reaches the public site at the next Export."])
        if values is not None:
            content.update_post(conn, post, **values)
            post = load(conn, post_id)
    except content.PostError as exc:
        return editor_page(request, user, post, values, str(exc))
    content.publish_post(conn, post)
    return RedirectResponse(f"/admin/posts/{post_id}", status_code=303)


@router.post("/{post_id}/unpublish")
def unpublish_post(request: Request, post_id: int, confirm: str = Form(""),
                   values: dict | None = Depends(pending_values),
                   user: sqlite3.Row = Depends(auth.current_user),
                   conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    if not confirm:
        return confirmation(
            request, user, post, action="unpublish_post", button="Unpublish",
            heading="Confirm unpublishing", pending=values,
            summary=[f"Unpublish “{post['title']}”? It returns to Draft and disappears "
                     "from the public site at the next Export. Unsaved edits in the "
                     "editor are not saved."])
    content.unpublish_post(conn, post)
    return RedirectResponse(f"/admin/posts/{post_id}", status_code=303)


@router.post("/{post_id}/delete")
def delete_post(request: Request, post_id: int, confirm: str = Form(""),
                values: dict | None = Depends(pending_values),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    if not confirm:
        return confirmation(
            request, user, post, action="delete_post", button="Delete permanently",
            heading="Confirm deleting", pending=values,
            summary=[f"Delete “{post['title']}”? Deletion is permanent: the post "
                     "can’t be recovered."]
            + (["It leaves the public site at the next Export."]
               if post["first_published_at"] else []))
    content.delete_post(conn, post)
    return RedirectResponse(request.app.url_path_for("post_list"), status_code=303)


@router.get("/{post_id}/preview")
def preview(request: Request, post_id: int,
            conn: sqlite3.Connection = Depends(auth.get_db)):
    post = load(conn, post_id)
    return templates.TemplateResponse(
        request, "public/post.html",
        {"title": post["title"], "lang": "es", "css_path": "/style.css",
         "home_path": "/", **article_context(dict(post))})
