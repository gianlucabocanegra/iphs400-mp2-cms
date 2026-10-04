"""T08: demo content, the dashboard and the Post list filters."""
import re
from datetime import date

from app.demo import seed_content
from app.publish import render_site
from tests.conftest import csrf_from
from tests.test_t03_publish_export import all_html, new_post, publish
from tests.test_t05_confirmation import not_live
from tests.test_t06_pages import new_page, publish_page


def count(client, key):
    html = client.get("/admin").text
    return int(re.search(rf'data-count="{key}">(\d+)<', html).group(1))


def titles(client, query=""):
    html = client.get(f"/admin/posts{query}").text
    return re.findall(r'<td><a href="/admin/posts/\d+">([^<]+)</a></td>', html)


# --- Seed ----------------------------------------------------------------

def test_seed_creates_a_draft_and_a_published_post_of_every_kind(db_path, client_as):
    seed_content(db_path)
    admin = client_as("admin")
    for kind in ("news", "event", "menu"):
        assert count(admin, f"{kind}-draft") >= 1
        assert count(admin, f"{kind}-published") >= 1
    assert count(admin, "page-draft") >= 1
    assert count(admin, "page-published") >= 1


def test_seed_has_a_saturday_sunday_tournament(db_path, tmp_path):
    seed_content(db_path)
    out = render_site(tmp_path / "site", export_date=date(2026, 9, 29))
    html = (out / "eventos" / "index.html").read_text()
    assert " al " in html  # a multi-day Event date


def test_seeding_twice_does_not_duplicate_anything(db_path, client_as):
    seed_content(db_path)
    admin = client_as("admin")
    before = {k: count(admin, k) for k in ("news-draft", "event-published", "menu-draft",
                                           "page-published")}
    seed_content(db_path)
    after = {k: count(admin, k) for k in before}
    assert before == after
    assert len(titles(admin)) == len(set(titles(admin)))


# --- Dashboard -----------------------------------------------------------

def test_dashboard_counts_posts_by_kind_and_status(client_as):
    editor = client_as("editor")
    assert count(editor, "news-draft") == 0
    new_post(editor, kind="news", title="Uno")
    new_post(editor, kind="news", title="Dos")
    publish(editor, kind="menu", title="Menú")
    assert count(editor, "news-draft") == 2
    assert count(editor, "menu-published") == 1
    assert count(editor, "event-draft") == 0


def test_page_counts_are_for_admins_only(client_as):
    admin = client_as("admin")
    new_page(admin, title="Borrador")
    publish_page(admin, title="Reglas")
    assert count(admin, "page-draft") == 1
    assert count(admin, "page-published") == 1
    assert 'data-count="page-' not in client_as("editor").get("/admin").text


def test_dashboard_says_never_before_the_first_export(client_as):
    assert "Last Export: never" in client_as("editor").get("/admin").text


def test_dashboard_shows_the_last_export_in_lima_time(client_as, tmp_path, monkeypatch):
    from app import publish as publish_module
    monkeypatch.setattr(publish_module, "utc_now", lambda: "2026-09-30T01:05:00+00:00")
    render_site(tmp_path / "site", export_date=date(2026, 9, 29))
    assert "Last Export: 2026-09-29 20:05" in client_as("editor").get("/admin").text


def test_every_published_item_is_not_yet_live_before_any_export(client_as):
    admin = client_as("admin")
    publish(admin, kind="news", title="Noticia")
    publish_page(admin, title="Reglas")
    new_post(admin, kind="news", title="Borrador")
    assert not_live(admin) == 2


def test_after_an_export_nothing_is_not_yet_live(client_as, tmp_path):
    admin = client_as("admin")
    publish(admin, kind="news", title="Noticia")
    publish_page(admin, title="Reglas")
    render_site(tmp_path / "site", export_date=date(2026, 9, 29))
    assert not_live(admin) == 0


# --- Post list filters ---------------------------------------------------

def make_mix(editor):
    new_post(editor, kind="news", title="Noticia borrador")
    publish(editor, kind="news", title="Noticia publicada")
    new_post(editor, kind="menu", title="Menú borrador")


def test_filter_by_kind(client_as):
    editor = client_as("editor")
    make_mix(editor)
    assert sorted(titles(editor, "?kind=menu")) == ["Menú borrador"]
    assert len(titles(editor, "?kind=news")) == 2


def test_filter_by_status(client_as):
    editor = client_as("editor")
    make_mix(editor)
    assert titles(editor, "?status=published") == ["Noticia publicada"]


def test_filters_combine(client_as):
    editor = client_as("editor")
    make_mix(editor)
    assert titles(editor, "?kind=news&status=draft") == ["Noticia borrador"]


def test_filters_that_match_nothing_are_still_shown_with_zero(client_as):
    editor = client_as("editor")
    make_mix(editor)
    html = editor.get("/admin/posts").text
    assert "Event (0)" in html
    html = editor.get("/admin/posts?kind=event").text
    assert "Event (0)" in html
    assert "News (2)" in html and "Menu (1)" in html
    assert "Published (0)" in html


def test_an_unknown_filter_value_is_ignored(client_as):
    editor = client_as("editor")
    make_mix(editor)
    assert len(titles(editor, "?kind=bogus&status=nope")) == 3


def test_the_seed_script_runs_from_the_env_example_values(tmp_path):
    import subprocess
    import sys
    env = {"PATH": "/usr/bin:/bin", "CMS_ENV_FILE": "/dev/null",
           "CMS_DATABASE": str(tmp_path / "fresh.db"),
           "CMS_ADMIN_PASSWORD": "change-me-admin", "CMS_EDITOR_PASSWORD": "change-me-editor"}
    for _ in range(2):
        done = subprocess.run([sys.executable, "scripts/seed_demo.py"], env=env,
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
