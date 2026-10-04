"""The FastAPI application.

The console lives under /admin (plus /login and /logout); the public site
answers at /. Add routes in their own modules under app/routes/ and include
them here. Keep this file small.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware

from app import auth, db, publish, settings
from app.routes import auth as auth_routes
from app.routes import console
from app.web import templates


def create_app(database_path: Path | str | None = None) -> FastAPI:
    db_path = Path(database_path) if database_path else settings.DATABASE_PATH
    db.init_db(db_path)

    app = FastAPI(title="IPHS 400 MP2 CMS",
                  dependencies=[Depends(auth.csrf_protect)])
    app.state.db_path = db_path
    app.add_middleware(SessionMiddleware, secret_key=settings.check_secret_key(settings.SECRET_KEY),
                       session_cookie="cms_session", same_site="lax",
                       max_age=8 * 60 * 60)

    @app.exception_handler(auth.LoginRequired)
    def to_login(request: Request, exc: auth.LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.get("/style.css")
    def stylesheet():
        # Lets the console's Preview load the public stylesheet.
        return Response(publish.CSS, media_type="text/css")

    @app.get("/")
    def public_home(request: Request):
        return templates.TemplateResponse(
            request, "public/home.html",
            {"title": settings.SITE_TITLE, "news": []},
        )

    app.include_router(auth_routes.router)
    app.include_router(console.router)
    return app
