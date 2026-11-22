from app.db import _engine_url


def test_provider_postgres_urls_use_installed_psycopg_driver():
    for raw_url in (
        "postgres://demo:secret@db.example.test/app",
        "postgresql://demo:secret@db.example.test/app",
    ):
        url = _engine_url(raw_url)

        assert url.drivername == "postgresql+psycopg"
        assert url.host == "db.example.test"
        assert url.database == "app"


def test_explicit_psycopg_url_is_preserved():
    url = _engine_url("postgresql+psycopg://demo:secret@db.example.test/app")

    assert url.drivername == "postgresql+psycopg"


def test_sqlite_url_is_preserved():
    url = _engine_url("sqlite:///./demo.db")

    assert url.drivername == "sqlite"
    assert url.database == "./demo.db"
