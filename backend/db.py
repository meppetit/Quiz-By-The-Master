import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _build_url_and_args(raw: str):
    """Normalise any Postgres URL (local, Neon, Supabase pooler) for asyncpg."""
    url = raw.strip()
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    # asyncpg does not understand libpq's sslmode / channel_binding query params.
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    query.pop("options", None)
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    connect_args = {}
    host = (parts.hostname or "").lower()
    is_local = host in ("localhost", "127.0.0.1", "")
    if not is_local and (sslmode is None or sslmode not in ("disable", "allow")):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx
    # Transaction-pooled hosts (Supabase pooler, PgBouncer) cannot use prepared statement caching.
    if "pooler" in host or "pgbouncer" in host:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
        connect_args["server_settings"] = {"jit": "off"}
    return url, connect_args


def _raw_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required (a PostgreSQL connection string)")
    return url


DATABASE_URL, _CONNECT_ARGS = _build_url_and_args(_raw_url())

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args=_CONNECT_ARGS,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as session:
        yield session
