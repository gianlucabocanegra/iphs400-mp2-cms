"""The console refuses to start without a real CMS_SECRET_KEY, unless CMS_ENV=local."""
import importlib
import os

import pytest

from app import settings
from app.main import create_app

PLACEHOLDER = settings.SECRET_KEY_PLACEHOLDER


@pytest.mark.parametrize("env", ["", "production", "Local", "dev"])
@pytest.mark.parametrize("value", ["", "   ", PLACEHOLDER])
def test_the_app_refuses_to_start_without_a_real_key_unless_local(db_path, monkeypatch,
                                                                  env, value):
    monkeypatch.setattr(settings, "SECRET_KEY", value)
    monkeypatch.setattr(settings, "ENV", env)
    with pytest.raises(settings.SettingsError, match="CMS_SECRET_KEY"):
        create_app(db_path)


def test_local_env_allows_the_placeholder_with_a_warning(db_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "SECRET_KEY", PLACEHOLDER)
    monkeypatch.setattr(settings, "ENV", "local")
    assert create_app(db_path) is not None
    assert "WARNING" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["", "   "])
def test_local_env_still_refuses_an_empty_key(db_path, monkeypatch, value):
    monkeypatch.setattr(settings, "SECRET_KEY", value)
    monkeypatch.setattr(settings, "ENV", "local")
    with pytest.raises(settings.SettingsError):
        create_app(db_path)


def test_a_real_key_starts_the_app_without_a_warning(db_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "SECRET_KEY", "a-long-random-value-for-this-test")
    monkeypatch.setattr(settings, "ENV", "")
    assert create_app(db_path) is not None
    assert capsys.readouterr().err == ""


def test_there_is_no_public_default_key():
    saved = os.environ.pop("CMS_SECRET_KEY")
    try:
        assert importlib.reload(settings).SECRET_KEY == ""
    finally:
        os.environ["CMS_SECRET_KEY"] = saved
        importlib.reload(settings)
