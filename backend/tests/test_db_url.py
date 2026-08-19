"""Unit tests for db._build_url_and_args URL normalisation."""
import os
import sys

# Ensure DATABASE_URL exists so importing db does not fail at module load.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/mepquiz")
sys.path.insert(0, "/app/backend")

from db import _build_url_and_args  # noqa: E402


def test_postgresql_scheme_rewritten():
    url, args = _build_url_and_args("postgresql://user:pw@example.com:5432/db")
    assert url.startswith("postgresql+asyncpg://")
    assert "ssl" in args  # remote host


def test_postgres_scheme_rewritten():
    url, _ = _build_url_and_args("postgres://user:pw@example.com/db")
    assert url.startswith("postgresql+asyncpg://")


def test_psycopg2_scheme_rewritten():
    url, _ = _build_url_and_args("postgresql+psycopg2://user:pw@example.com/db")
    assert url.startswith("postgresql+asyncpg://")
    assert "psycopg2" not in url


def test_sslmode_and_channel_binding_stripped():
    url, args = _build_url_and_args(
        "postgresql://u:p@remote.example.com/db?sslmode=require&channel_binding=require"
    )
    assert "sslmode" not in url
    assert "channel_binding" not in url
    assert "ssl" in args  # remote + sslmode=require -> ssl context added


def test_local_host_no_ssl():
    url, args = _build_url_and_args("postgresql://postgres@localhost:5432/mepquiz")
    assert "ssl" not in args
    _, args2 = _build_url_and_args("postgresql://postgres@127.0.0.1:5432/mepquiz")
    assert "ssl" not in args2


def test_remote_host_gets_ssl():
    _, args = _build_url_and_args("postgresql://u:p@db.something.supabase.co/postgres")
    assert "ssl" in args


def test_pooler_host_disables_statement_cache():
    _, args = _build_url_and_args(
        "postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    assert args.get("statement_cache_size") == 0
    assert args.get("prepared_statement_cache_size") == 0
    assert "ssl" in args


def test_pgbouncer_host_disables_statement_cache():
    _, args = _build_url_and_args("postgresql://u:p@my-pgbouncer.example.com/db")
    assert args.get("statement_cache_size") == 0


def test_asyncpg_localhost_unchanged():
    raw = "postgresql+asyncpg://postgres@localhost:5432/mepquiz"
    url, args = _build_url_and_args(raw)
    assert url == raw
    assert args == {}


def test_no_mongo_env_or_deps():
    # Guard: MONGO_URL / DB_NAME must not be required at runtime
    assert "MONGO_URL" not in open("/app/backend/.env").read()
    assert "DB_NAME" not in open("/app/backend/.env").read()
    reqs = open("/app/backend/requirements.txt").read().lower()
    assert "motor" not in reqs
    assert "pymongo" not in reqs
