import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

from app.db.base import Base
from app.models import graph, governance, job_run, optimization, pr_review, standardization, user, organization, workflow_run, remediation

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    # Same reasoning as run_async_migrations: read the env var directly
    # rather than through config, which re-parses alembic.ini's raw
    # "%(DATABASE_URL)s" placeholder on every file_config access.
    url = database_url or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations using an async engine."""
    # Built directly rather than via config.get_section(), which calls
    # ConfigParser's .items() on the raw ini section — that re-interpolates
    # the literal "%(DATABASE_URL)s" placeholder in alembic.ini (it's meant
    # to be filled from the DATABASE_URL env var, not a ConfigParser option)
    # and throws InterpolationMissingOptionError before set_main_option's
    # override ever comes into play. alembic.ini defines no other
    # sqlalchemy.* options, so this is the complete configuration.
    connectable = async_engine_from_config(
        {"sqlalchemy.url": database_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
