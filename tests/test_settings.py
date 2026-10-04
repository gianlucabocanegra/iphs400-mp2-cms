"""settings.load_dotenv: .env fills the environment but never overrides it."""
import os

from app import settings


def load(tmp_path, monkeypatch, text, **existing):
    monkeypatch.setattr(os, "environ", dict(existing))  # nothing leaks out
    env = tmp_path / ".env"
    env.write_text(text, encoding="utf-8")
    settings.load_dotenv(env)
    return os.environ


def test_dotenv_fills_missing_variables_only(tmp_path, monkeypatch):
    env = load(tmp_path, monkeypatch,
               "# comment\nCMS_SITE_TITLE=Golf & Country Club of Trujillo\n"
               "CMS_A=\"con acentos: áé\"\nCMS_KEPT=from-file\n",
               CMS_KEPT="from-environment")
    assert env["CMS_SITE_TITLE"] == "Golf & Country Club of Trujillo"
    assert env["CMS_A"] == "con acentos: áé"
    assert env["CMS_KEPT"] == "from-environment"


def test_only_matching_quotes_are_stripped(tmp_path, monkeypatch):
    env = load(tmp_path, monkeypatch, "CMS_A=\"a'\nCMS_B=it's\nCMS_C='x'\n")
    assert env["CMS_A"] == "\"a'" and env["CMS_B"] == "it's" and env["CMS_C"] == "x"


def test_missing_dotenv_is_fine(tmp_path):
    settings.load_dotenv(tmp_path / "absent.env")


def test_env_example_sets_the_clubs_name_as_the_site_title():
    """T08: CMS_SITE_TITLE in .env.example is the club's name."""
    example = (settings.ROOT / ".env.example").read_text(encoding="utf-8")
    title = [line.partition("=")[2] for line in example.splitlines()
             if line.startswith("CMS_SITE_TITLE=")]
    assert title == ["Golf & Country Club of Trujillo"]
