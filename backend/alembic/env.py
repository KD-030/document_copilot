from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.pool import NullPool

from alembic import context
from app.config import settings
from app.database.models import User

config = context.config

target_metadata = User.metadata


def database_url():
    try:
        url = make_url(settings.database_url)
    except ArgumentError:
        raise RuntimeError(
            "DATABASE_URL is malformed. URL-encode reserved characters in its credentials."
        ) from None

    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise RuntimeError(
            f"DATABASE_URL resolves to {url.drivername!r}, not PostgreSQL. "
            "An exported DATABASE_URL overrides backend/.env; unset the override "
            "or set it to a valid Supabase direct/session PostgreSQL URL."
        )

    try:
        port = url.port
    except ValueError:
        raise RuntimeError(
            "DATABASE_URL must contain a numeric port. URL-encode reserved characters "
            "in its credentials."
        ) from None

    if not url.host or port is None or not url.database:
        raise RuntimeError(
            "DATABASE_URL must include a valid hostname, port, and database name. "
            "URL-encode reserved characters in its credentials."
        )

    if "pooler.supabase.com" in (url.host or "") and url.port != 5432:
        raise RuntimeError(
            "Alembic requires a direct or session-mode database connection, not "
            "the Supabase transaction pooler. Set DATABASE_URL to the direct "
            "connection string from Supabase."
        )

    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")

    return url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url().render_as_string(hide_password=True),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        database_url(),
        poolclass=NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
