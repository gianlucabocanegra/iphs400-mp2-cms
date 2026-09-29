"""Shared Jinja environment for the console."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app import settings
from app.auth import csrf_token

templates = Jinja2Templates(directory=str(settings.TEMPLATES))
templates.env.globals["csrf_token"] = csrf_token
