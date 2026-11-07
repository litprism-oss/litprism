"""Deployment settings — Postgres URL normalisation, CORS origins, pooler-safe engine."""

import pytest
from config import Settings
from db.engine import _engine_kwargs


@pytest.mark.parametrize(
    "raw",
    [
        "postgres://u:p@db.example.com:6543/postgres",
        "postgresql://u:p@db.example.com:6543/postgres",
    ],
)
def test_plain_postgres_url_gets_asyncpg_driver(raw):
    s = Settings(database_url=raw)
    assert s.database_url == "postgresql+asyncpg://u:p@db.example.com:6543/postgres"


def test_asyncpg_and_sqlite_urls_are_left_alone():
    asyncpg_url = "postgresql+asyncpg://u:p@localhost/litprism"
    assert Settings(database_url=asyncpg_url).database_url == asyncpg_url
    sqlite_url = "sqlite+aiosqlite:///./litprism.db"
    assert Settings(database_url=sqlite_url).database_url == sqlite_url


def test_cors_origins_default_is_wildcard():
    assert Settings().cors_origin_list == ["*"]


def test_cors_origins_parses_comma_separated_list():
    s = Settings(cors_origins=" https://a.example.com , https://b.example.com ,")
    assert s.cors_origin_list == ["https://a.example.com", "https://b.example.com"]


def test_pooler_safe_kwargs_only_for_asyncpg():
    assert _engine_kwargs("sqlite+aiosqlite:///./x.db") == {}
    kwargs = _engine_kwargs("postgresql+asyncpg://u:p@h/db")
    assert kwargs["connect_args"]["statement_cache_size"] == 0
    assert kwargs["connect_args"]["prepared_statement_name_func"]() != (
        kwargs["connect_args"]["prepared_statement_name_func"]()
    )
