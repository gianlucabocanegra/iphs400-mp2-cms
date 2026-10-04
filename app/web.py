"""Shared Jinja environment for the console."""
from __future__ import annotations

import jinja2
from fastapi.templating import Jinja2Templates

from app import settings
from app.auth import csrf_token, pop_flash
from app.timeutil import lima

templates = Jinja2Templates(directory=str(settings.TEMPLATES))
templates.env.globals["csrf_token"] = csrf_token
templates.env.globals["pop_flash"] = pop_flash
templates.env.filters["lima"] = lima
# The console is at many depths (/admin, /admin/posts/3, ...), so a relative "style.css"
# 404s on all but the first. Console only: Export uses its own environment and stays relative.
templates.env.globals["css_path"] = "/style.css"


@jinja2.pass_context
def path_for(context, name: str, **params) -> str:
    """The path of a named console route, e.g. path_for('edit_post', post_id=3).

    Unlike Starlette's url_for it stays a path ("/admin/posts/3"), not a full URL.
    """
    return context["request"].app.url_path_for(name, **params)


templates.env.globals["path_for"] = path_for
