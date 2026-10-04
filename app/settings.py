"""Configuration, read from the environment (never hard-code secrets)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    """Fill os.environ from a .env file without overriding real variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


load_dotenv(Path(os.environ.get("CMS_ENV_FILE", ROOT / ".env")))

TEMPLATES = ROOT / "templates"
SITE = ROOT / "site"

# The key that signs session cookies (and so the CSRF token). There is no default:
# a public one would let anyone forge a signed-in session. See check_secret_key.
SECRET_KEY = os.environ.get("CMS_SECRET_KEY", "")
SECRET_KEY_PLACEHOLDER = "change-me-to-a-long-random-string"  # from .env.example
# "local" lets the placeholder key run, with a warning. Anything else does not.
ENV = os.environ.get("CMS_ENV", "")
DATABASE_PATH = Path(os.environ.get("CMS_DATABASE", ROOT / "cms.db"))
SITE_TITLE = os.environ.get("CMS_SITE_TITLE", "My CMS")
# Set this to your Pages URL once you deploy, e.g.
# https://yourname.github.io/iphs400-mp2-cms/
BASE_PATH = os.environ.get("CMS_BASE_PATH", "")


class SettingsError(RuntimeError):
    """A setting is missing or unsafe. The message says how to fix it."""


def check_secret_key(value: str, env: str | None = None) -> str:
    """The key itself, or a SettingsError if it is unset or still the placeholder.

    With CMS_ENV=local the placeholder is allowed (so a fresh clone runs), with a
    warning. An empty key never is, and anything but "local" gets no leniency.
    """
    env = ENV if env is None else env
    if not value.strip():
        raise SettingsError(_KEY_HELP.format(problem="CMS_SECRET_KEY is not set"))
    if value == SECRET_KEY_PLACEHOLDER:
        if env != "local":
            raise SettingsError(_KEY_HELP.format(
                problem="CMS_SECRET_KEY is still the .env.example placeholder"))
        print("WARNING: CMS_ENV=local and CMS_SECRET_KEY is the public placeholder. "
              "Fine on your own computer; never use it anywhere else.", file=sys.stderr)
    return value


_KEY_HELP = ("{problem}. Put a long random value in .env, for example: "
             "python3 -c 'import secrets; print(secrets.token_hex(32))'. "
             "(For a throwaway local demo only, set CMS_ENV=local to allow the placeholder.)")
