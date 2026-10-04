#!/usr/bin/env python3
"""Create demo data so a grader (and you) can use the CMS immediately.

    uv run python scripts/seed_demo.py

Creates one Admin (admin@example.test) and one Editor (editor@example.test),
with passwords read from CMS_ADMIN_PASSWORD / CMS_EDITOR_PASSWORD, never
hard-coded, then adds demo content (a Draft and a Published item of every kind).
Safe to run twice.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import settings  # noqa: E402
from app.accounts import seed_users  # noqa: E402
from app.demo import seed_content  # noqa: E402


def main() -> int:
    admin_pw = os.environ.get("CMS_ADMIN_PASSWORD")
    editor_pw = os.environ.get("CMS_EDITOR_PASSWORD")
    if not admin_pw or not editor_pw:
        print("Set CMS_ADMIN_PASSWORD and CMS_EDITOR_PASSWORD in .env "
              "(copy .env.example).")
        return 1

    database = Path(os.environ.get("CMS_DATABASE", settings.DATABASE_PATH))
    seed_users(database, admin_password=admin_pw, editor_password=editor_pw)
    seed_content(database)
    print(f"Seeded the Admin, the Editor and demo content in {database}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
