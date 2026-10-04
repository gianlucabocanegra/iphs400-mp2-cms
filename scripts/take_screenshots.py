#!/usr/bin/env python3
"""Throwaway: take the 12 submission screenshots of the running console.

    uv run --with playwright python scripts/take_screenshots.py http://127.0.0.1:8123

Playwright is not a project dependency. Passwords come from the environment
(CMS_ADMIN_PASSWORD / CMS_EDITOR_PASSWORD), never hard-coded.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
WIDTHS = {1280: 800, 390: 844}


def login(page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE}/admin*")


def shot(browser, width: int, name: str, email: str | None, password: str | None,
         path: str, *, nth_post: bool = False, expect: int = 200) -> None:
    context = browser.new_context(viewport={"width": width, "height": WIDTHS[width]})
    page = context.new_page()
    if email:
        login(page, email, password)
    if nth_post:
        page.goto(f"{BASE}/admin/posts")
        page.click('table a[href^="/admin/posts/"]')
    else:
        status = page.goto(f"{BASE}{path}").status
        assert status == expect, f"{path}: expected {expect}, got {status}"
    page.screenshot(path=str(OUT / f"{name}-{width}.png"), full_page=True)
    context.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    admin = ("admin@example.test", os.environ["CMS_ADMIN_PASSWORD"])
    editor = ("editor@example.test", os.environ["CMS_EDITOR_PASSWORD"])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in WIDTHS:
            shot(browser, width, "login", None, None, "/login")
            shot(browser, width, "dashboard", *admin, "/admin")
            shot(browser, width, "content-list", *admin, "/admin/posts")
            shot(browser, width, "editor", *admin, "", nth_post=True)
            shot(browser, width, "users", *admin, "/admin/users")
            shot(browser, width, "editor-denied", *editor, "/admin/users", expect=403)
        browser.close()


if __name__ == "__main__":
    main()
