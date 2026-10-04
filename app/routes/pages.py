"""Page list, editor and Preview. Admin only: the router-level check covers every route."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import auth
from app import pages as store
from app.markdown import render_markdown
from app.web import templates

router = APIRouter(prefix="/pages", dependencies=[Depends(auth.require_admin)])

EDITOR_FIELDS = ("title", "slug", "body_md", "nav_order")
BLANK = {"title": "", "slug": "", "body_md": "", "nav_order": "0"}


def form_page(request: Request, user: sqlite3.Row, page: dict, *,
              error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "admin/page_form.html",
        {"title": "Edit page" if page.get("id") else "New page", "user": user,
         "page": page, "error": error},
        status_code=status_code)


def load(conn: sqlite3.Connection, page_id: int) -> sqlite3.Row:
    page = store.get_page(conn, page_id)
    if page is None:
        raise HTTPException(404, "Page not found")
    return page


async def pending_values(request: Request) -> dict | None:
    """The editor's values as submitted, or None if the form carried none."""
    form = await request.form()
    if "title" not in form:
        return None
    return {name: str(form.get(name) or "") for name in EDITOR_FIELDS}


def clean(conn: sqlite3.Connection, page: sqlite3.Row, values: dict) -> dict:
    """Validate the editor's values (everything but the body) without saving."""
    return store.clean_update(conn, page, **{k: v for k, v in values.items()
                                             if k != "body_md"})


def changes(page: sqlite3.Row, cleaned: dict, body_md: str) -> list[str]:
    """Plain-language list of what saving would change."""
    labels = {"title": "Title", "slug": "Slug", "nav_order": "Navigation order"}
    lines = [f"{label}: “{page[key]}” → “{cleaned[key]}”"
             for key, label in labels.items() if page[key] != cleaned[key]]
    if page["body_md"] != body_md:
        lines.append("Body: changed (see the preview below)")
    return lines or ["No changes."]


def article_context(page: dict) -> dict:
    """What public/_article.html needs to show a Page as Members will see it."""
    return {"post": page, "date_label": None, "kind_label": "", "event_label": "",
            "body_html": render_markdown(page["body_md"])}


def confirmation(request: Request, user: sqlite3.Row, page: sqlite3.Row, *, action: str,
                 heading: str, summary: list[str], pending: dict | None, button: str,
                 preview: dict | None = None):
    """The Confirmation screen: nothing has been changed yet (see routes/posts.py)."""
    return templates.TemplateResponse(
        request, "admin/confirm.html",
        {"title": heading, "user": user, "summary": summary, "pending": pending or {},
         "button": button,
         "action_url": request.app.url_path_for(action, page_id=page["id"]),
         "cancel_url": request.app.url_path_for("back_to_page_editor", page_id=page["id"]),
         "preview": preview and article_context(preview)})


def editor_page(request, user, page: sqlite3.Row, values: dict | None, error: str):
    return form_page(request, user, {**dict(page), **(values or {})}, error=error,
                     status_code=422)


@router.get("")
def page_list(request: Request, user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    return templates.TemplateResponse(
        request, "admin/page_list.html",
        {"title": "Pages", "user": user, "pages": store.list_pages(conn)})


@router.get("/new")
def new_page(request: Request, user: sqlite3.Row = Depends(auth.current_user)):
    return form_page(request, user, dict(BLANK))


@router.post("")
def create_page(request: Request, title: str = Form(""), slug: str = Form(""),
                body_md: str = Form(""), nav_order: str = Form("0"),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    values = {"title": title, "slug": slug, "body_md": body_md, "nav_order": nav_order}
    try:
        page_id = store.create_page(conn, author_id=user["id"], **values)
    except store.PostError as exc:
        return form_page(request, user, values, error=str(exc), status_code=422)
    auth.flash(request, "Page created as a Draft.")
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.get("/{page_id}")
def edit_page(request: Request, page_id: int,
              user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    return form_page(request, user, dict(load(conn, page_id)))


@router.post("/{page_id}")
def save_page(request: Request, page_id: int, confirm: str = Form(""),
              values: dict | None = Depends(pending_values),
              user: sqlite3.Row = Depends(auth.current_user),
              conn: sqlite3.Connection = Depends(auth.get_db)):
    page = load(conn, page_id)
    values = values or dict(BLANK)
    try:
        cleaned = clean(conn, page, values)
        if page["status"] == "published" and not confirm:
            return confirmation(
                request, user, page, action="save_page", button="Save changes",
                heading="Confirm changes to Published page", pending=values,
                summary=["This page is Published. Saving changes what Members see "
                         "at the next Export.", *changes(page, cleaned, values["body_md"])],
                preview={**dict(page), **cleaned, "body_md": values["body_md"]})
        store.update_page(conn, page, **values)
    except store.PostError as exc:
        return editor_page(request, user, page, values, str(exc))
    auth.flash(request, "Page saved.")
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.post("/{page_id}/edit")
def back_to_page_editor(request: Request, page_id: int,
                        values: dict | None = Depends(pending_values),
                        user: sqlite3.Row = Depends(auth.current_user),
                        conn: sqlite3.Connection = Depends(auth.get_db)):
    """Cancel on a Confirmation screen: the editor again, with the unsaved values."""
    return form_page(request, user, {**dict(load(conn, page_id)), **(values or {})})


@router.post("/{page_id}/publish")
def publish_page(request: Request, page_id: int, confirm: str = Form(""),
                 values: dict | None = Depends(pending_values),
                 user: sqlite3.Row = Depends(auth.current_user),
                 conn: sqlite3.Connection = Depends(auth.get_db)):
    page = load(conn, page_id)
    try:
        cleaned = clean(conn, page, values) if values is not None else {}
        if not confirm:
            shown = {**dict(page), **cleaned,
                     **({"body_md": values["body_md"]} if values is not None else {})}
            return confirmation(
                request, user, page, action="publish_page", button="Publish",
                heading="Confirm publishing", pending=values, preview=shown,
                summary=[f"Publish “{shown['title']}”? It stays a Draft until you confirm, "
                         "and reaches the public site at the next Export."])
        if values is not None:  # what's on the editor is what gets published
            store.update_page(conn, page, **values)
            page = load(conn, page_id)
    except store.PostError as exc:
        return editor_page(request, user, page, values, str(exc))
    store.publish_page(conn, page)
    auth.flash(request, "Page published. It reaches the public site at the next Export.")
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.post("/{page_id}/unpublish")
def unpublish_page(request: Request, page_id: int, confirm: str = Form(""),
                   values: dict | None = Depends(pending_values),
                   user: sqlite3.Row = Depends(auth.current_user),
                   conn: sqlite3.Connection = Depends(auth.get_db)):
    page = load(conn, page_id)
    if not confirm:
        return confirmation(
            request, user, page, action="unpublish_page", button="Unpublish",
            heading="Confirm unpublishing", pending=values,
            summary=[f"Unpublish “{page['title']}”? It returns to Draft and disappears "
                     "from the public site and its Navigation at the next Export. "
                     "Unsaved edits in the editor are not saved."])
    store.unpublish_page(conn, page)
    auth.flash(request, "Page unpublished. It is a Draft again.")
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.post("/{page_id}/delete")
def delete_page(request: Request, page_id: int, confirm: str = Form(""),
                values: dict | None = Depends(pending_values),
                user: sqlite3.Row = Depends(auth.current_user),
                conn: sqlite3.Connection = Depends(auth.get_db)):
    page = load(conn, page_id)
    if not confirm:
        return confirmation(
            request, user, page, action="delete_page", button="Delete permanently",
            heading="Confirm deleting", pending=values,
            summary=[f"Delete “{page['title']}”? Deletion is permanent: the page "
                     "can’t be recovered."]
            + (["It leaves the public site at the next Export."]
               if page["status"] == "published" else []))
    store.delete_page(conn, page)
    auth.flash(request, "Page deleted.")
    return RedirectResponse(request.app.url_path_for("page_list"), status_code=303)


@router.get("/{page_id}/preview")
def preview_page(request: Request, page_id: int,
                 conn: sqlite3.Connection = Depends(auth.get_db)):
    page = load(conn, page_id)
    return templates.TemplateResponse(
        request, "public/post.html",
        {"title": page["title"], "lang": "es", "css_path": "/style.css",
         "home_path": "/", **article_context(dict(page))})
