"""Shared Jinja environment for the console."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app import settings
from app.auth import csrf_token
from app.timeutil import lima

templates = Jinja2Templates(directory=str(settings.TEMPLATES))
templates.env.globals["csrf_token"] = csrf_token
templates.env.filters["lima"] = lima
