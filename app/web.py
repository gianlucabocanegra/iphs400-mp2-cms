"""Shared Jinja environment for the console."""
from __future__ import annotations

import jinja2
from fastapi.templating import Jinja2Templates

from app import settings
from app.auth import csrf_token
from app.timeutil import lima

templates = Jinja2Templates(directory=str(settings.TEMPLATES))
templates.env.globals["csrf_token"] = csrf_token
templates.env.filters["lima"] = lima


@jinja2.pass_context
def path_for(context, name: str, **params) -> str:
    """The path of a named console route, e.g. path_for('edit_post', post_id=3).

    Unlike Starlette's url_for it stays a path ("/admin/posts/3"), not a full URL.
    """
    return context["request"].app.url_path_for(name, **params)


templates.env.globals["path_for"] = path_for
