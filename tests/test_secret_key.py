"""The console refuses to start without a real CMS_SECRET_KEY."""
import pytest

from app import settings
from app.main import create_app


@pytest.mark.parametrize("value", ["", "   ", settings.SECRET_KEY_PLACEHOLDER])
def test_the_app_refuses_to_start_without_a_real_secret_key(db_path, monkeypatch, value):
    monkeypatch.setattr(settings, "SECRET_KEY", value)
    with pytest.raises(settings.SettingsError, match="CMS_SECRET_KEY"):
        create_app(db_path)


def test_a_real_secret_key_starts_the_app(db_path, monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "a-long-random-value-for-this-test")
    assert create_app(db_path) is not None


def test_there_is_no_public_default_key():
    # With nothing in the environment the key is empty, not a guessable string.
    import importlib
    import os
    saved = os.environ.pop("CMS_SECRET_KEY")
    try:
        assert importlib.reload(settings).SECRET_KEY == ""
    finally:
        os.environ["CMS_SECRET_KEY"] = saved
        importlib.reload(settings)
