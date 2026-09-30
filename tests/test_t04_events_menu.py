"""T04: Event dates and the Menu on the public site. Seam 1 (console) and Seam 2 (render_site)."""
from datetime import date

from app import content
from app.publish import render_site
from tests.conftest import csrf_from
from tests.test_t03_publish_export import all_html, post_action


def save_event(client, *, title="Torneo", kind="event", start="", time="", end="",
               body="Hola"):
    token = csrf_from(client.get("/admin/posts/new"))
    return client.post("/admin/posts", data={
        "csrf_token": token, "kind": kind, "title": title, "slug": "", "body_md": body,
        "event_start_date": start, "event_start_time": time, "event_end_date": end},
        follow_redirects=False)


def publish_event(client, **kw):
    response = save_event(client, **kw)
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert post_action(client, location, "publish").status_code == 303
    return location


def publish_menu(client, title, body="Sopa"):
    return publish_event(client, kind="menu", title=title, body=body)


def export(tmp_path, day):
    return render_site(tmp_path / "site", export_date=day)


def main_of(path):
    return path.read_text().split("<main>")[1]


def sections(text):
    """The Events index split into (Upcoming part, past part)."""
    upcoming, past = text.split("Eventos pasados")
    return upcoming, past


# --- Event date validation (console) --------------------------------------

def test_event_without_a_start_date_is_a_form_error(client_as):
    editor = client_as("editor")
    response = save_event(editor, title="Sin fecha")
    assert response.status_code == 422
    assert "start date" in response.text
    assert "Sin fecha" not in editor.get("/admin/posts").text


def test_end_date_before_start_date_is_a_clear_form_error(client_as):
    response = save_event(client_as("editor"), start="2026-10-04", end="2026-10-03")
    assert response.status_code == 422
    assert "end date can’t be earlier than the start date" in response.text


def test_event_date_fields_are_rejected_on_news_and_menu(client_as):
    editor = client_as("editor")
    for kind in ("news", "menu"):
        response = save_event(editor, kind=kind, title=f"Un {kind}", start="2026-10-03")
        assert response.status_code == 422, kind
        assert "only apply to Events" in response.text
    assert "Un news" not in editor.get("/admin/posts").text


def test_event_with_start_time_and_end_date_is_saved_and_shown_again(client_as):
    editor = client_as("editor")
    response = save_event(editor, start="2026-10-03", time="08:30", end="2026-10-04")
    assert response.status_code == 303
    form = editor.get(response.headers["location"]).text
    assert 'value="2026-10-03"' in form and 'value="08:30"' in form
    assert 'value="2026-10-04"' in form


def test_editing_an_event_validates_its_dates_too(client_as):
    editor = client_as("editor")
    location = save_event(editor, start="2026-10-03").headers["location"]
    token = csrf_from(editor.get(location))
    response = editor.post(location, data={
        "csrf_token": token, "title": "Torneo", "slug": "", "body_md": "x",
        "event_start_date": "2026-10-03", "event_end_date": "2026-10-01"})
    assert response.status_code == 422
    assert "earlier than the start date" in response.text


# --- Upcoming (Export) ------------------------------------------------------

SATURDAY, SUNDAY, MONDAY = date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)


def test_weekend_tournament_is_upcoming_on_its_sunday_but_not_on_monday(client_as, tmp_path):
    publish_event(client_as("editor"), title="Copa Fin de Semana",
                  start="2026-10-03", end="2026-10-04")

    sunday = export(tmp_path, SUNDAY)
    upcoming, past = sections((sunday / "eventos" / "index.html").read_text())
    assert "Copa Fin de Semana" in upcoming and "Copa Fin de Semana" not in past
    assert "Copa Fin de Semana" in (sunday / "index.html").read_text()

    monday = export(tmp_path, MONDAY)
    upcoming, past = sections((monday / "eventos" / "index.html").read_text())
    assert "Copa Fin de Semana" not in upcoming and "Copa Fin de Semana" in past
    assert "Copa Fin de Semana" not in (monday / "index.html").read_text()


def test_one_day_event_is_upcoming_on_its_own_day_only(client_as, tmp_path):
    publish_event(client_as("editor"), title="Cena", start="2026-10-03")
    upcoming, _ = sections((export(tmp_path, SATURDAY) / "eventos" / "index.html").read_text())
    assert "Cena" in upcoming
    upcoming, past = sections((export(tmp_path, SUNDAY) / "eventos" / "index.html").read_text())
    assert "Cena" not in upcoming and "Cena" in past


def test_home_shows_at_most_three_upcoming_events_soonest_first(client_as, tmp_path):
    editor = client_as("editor")
    for title, start in [("Cuarto", "2026-10-20"), ("Segundo", "2026-10-08"),
                         ("Primero", "2026-10-06"), ("Tercero", "2026-10-09")]:
        publish_event(editor, title=title, start=start)
    home = main_of(export(tmp_path, MONDAY) / "index.html")
    assert "Cuarto" not in home
    assert home.index("Primero") < home.index("Segundo") < home.index("Tercero")


def test_events_index_lists_upcoming_soonest_first_then_past_most_recent_first(client_as, tmp_path):
    editor = client_as("editor")
    for title, start in [("Futuro lejano", "2026-11-01"), ("Futuro cercano", "2026-10-10"),
                         ("Pasado viejo", "2026-08-01"), ("Pasado reciente", "2026-09-20")]:
        publish_event(editor, title=title, start=start)
    upcoming, past = sections(main_of(export(tmp_path, MONDAY) / "eventos" / "index.html"))
    assert upcoming.index("Futuro cercano") < upcoming.index("Futuro lejano")
    assert past.index("Pasado reciente") < past.index("Pasado viejo")


def test_each_event_shows_its_date_first_in_spanish_with_time_when_set(client_as, tmp_path):
    editor = client_as("editor")
    publish_event(editor, title="Cena de gala", start="2026-10-10", time="20:00")
    publish_event(editor, title="Copa", start="2026-10-03", end="2026-10-04")
    out = export(tmp_path, SATURDAY)

    gala = main_of(out / "eventos" / "cena-de-gala.html")
    assert "10 de octubre de 2026" in gala and "20:00" in gala
    assert gala.index("10 de octubre de 2026") < gala.index("Cena de gala")

    copa = main_of(out / "eventos" / "copa.html")
    assert "3 de octubre de 2026" in copa and "4 de octubre de 2026" in copa
    assert "20:00" not in copa

    feed = main_of(out / "eventos" / "index.html")
    assert feed.index("10 de octubre de 2026") < feed.index("Cena de gala")
    assert feed.index("3 de octubre de 2026") < feed.index("Copa")
    home = main_of(out / "index.html")
    assert home.index("10 de octubre de 2026") < home.index("Cena de gala")


# --- The Menu (Export) ------------------------------------------------------

def test_home_shows_only_the_current_menu_and_older_ones_go_to_the_archive(
        client_as, tmp_path, monkeypatch):
    editor = client_as("editor")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-21T15:00:00+00:00")
    publish_menu(editor, "Menú semana 38", body="Lomo saltado S/ 30")
    out = export(tmp_path, MONDAY)
    assert "Menú semana 38" in main_of(out / "index.html")
    assert "Menú semana 38" not in main_of(out / "menus" / "index.html")

    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-28T15:00:00+00:00")
    publish_menu(editor, "Menú semana 39", body="Ají de gallina S/ 32")
    out = export(tmp_path, MONDAY)
    home = main_of(out / "index.html")
    assert "Menú semana 39" in home and "Ají de gallina S/ 32" in home
    assert "Menú semana 38" not in home and "Lomo saltado" not in home
    archive = main_of(out / "menus" / "index.html")
    assert "Menú semana 38" in archive and "Menú semana 39" not in archive
    assert (out / "menus" / "menu-semana-38.html").exists()


def test_menu_archive_is_newest_first(client_as, tmp_path, monkeypatch):
    editor = client_as("editor")
    for day, title in [(14, "Semana A"), (21, "Semana B"), (28, "Semana C"), (5, "Semana D")]:
        month = 10 if day == 5 else 9
        monkeypatch.setattr(content, "utc_now",
                            lambda month=month, day=day: f"2026-{month:02d}-{day:02d}T15:00:00+00:00")
        publish_menu(editor, title)
    archive = main_of(export(tmp_path, MONDAY) / "menus" / "index.html")
    assert "Semana D" not in archive  # the Current menu
    assert archive.index("Semana C") < archive.index("Semana B") < archive.index("Semana A")


def test_current_menu_follows_first_published_time_not_latest_edit(client_as, tmp_path, monkeypatch):
    editor = client_as("editor")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-21T15:00:00+00:00")
    old = publish_menu(editor, "Vieja")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-28T15:00:00+00:00")
    publish_menu(editor, "Nueva")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-29T15:00:00+00:00")
    post_action(editor, old, "unpublish")
    post_action(editor, old, "publish")
    home = main_of(export(tmp_path, MONDAY) / "index.html")
    assert "Nueva" in home and "Vieja" not in home


def test_menu_archive_entries_show_their_first_published_date(client_as, tmp_path, monkeypatch):
    editor = client_as("editor")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-21T15:00:00+00:00")
    publish_menu(editor, "Semana 38")
    monkeypatch.setattr(content, "utc_now", lambda: "2026-09-28T15:00:00+00:00")
    publish_menu(editor, "Semana 39")
    archive = main_of(export(tmp_path, MONDAY) / "menus" / "index.html")
    assert "21 de septiembre de 2026" in archive


# --- Drafts and navigation ---------------------------------------------------

def test_draft_events_and_menus_never_appear_in_the_site(client_as, tmp_path):
    editor = client_as("editor")
    save_event(editor, title="Evento secreto", start="2026-10-10")
    save_event(editor, kind="menu", title="Menú secreto")
    publish_event(editor, title="Evento público", start="2026-10-11")
    publish_menu(editor, "Menú público")
    out = export(tmp_path, MONDAY)
    html = all_html(out)
    assert "Evento secreto" not in html and "Menú secreto" not in html
    assert not (out / "eventos" / "evento-secreto.html").exists()
    assert not (out / "menus" / "menu-secreto.html").exists()


def test_navigation_links_the_events_and_menu_archive_relatively(client_as, tmp_path):
    publish_event(client_as("editor"), title="Cena", start="2026-10-10")
    out = export(tmp_path, MONDAY)
    home = (out / "index.html").read_text()
    assert 'href="eventos/index.html"' in home and 'href="menus/index.html"' in home
    event = (out / "eventos" / "cena.html").read_text()
    assert 'href="../eventos/index.html"' in event and 'href="../menus/index.html"' in event
    for path in out.rglob("*.html"):
        text = path.read_text()
        assert 'href="/' not in text and 'src="/' not in text, path


def test_a_database_made_before_t04_still_takes_events(tmp_path):
    import sqlite3
    from fastapi.testclient import TestClient
    from app.accounts import seed_users
    from app.main import create_app
    from tests.conftest import DEMO_USERS

    old = tmp_path / "old.db"
    seed_users(old, admin_password="a", editor_password=DEMO_USERS["editor"]["password"])
    conn = sqlite3.connect(old)  # drop the Event columns to mimic the T03 schema
    conn.executescript("""
        CREATE TABLE posts_old AS SELECT id, kind, title, slug, body_md, status,
            author_id, created_at, updated_at, first_published_at FROM posts;
        DROP TABLE posts;
        ALTER TABLE posts_old RENAME TO posts;""")
    conn.commit()
    conn.close()

    client = TestClient(create_app(old))
    token = csrf_from(client.get("/login"))
    client.post("/login", data={"email": DEMO_USERS["editor"]["email"],
                                "password": DEMO_USERS["editor"]["password"],
                                "csrf_token": token})
    assert save_event(client, start="2026-10-03").status_code == 303
