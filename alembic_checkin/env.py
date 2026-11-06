"""Migrationen der Zwischendatenbank der Check-in-App, getrennt von der Haupt-DB (alembic/)."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import checkinDbSettings
from app.db.checkin import CheckinBase

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = CheckinBase.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=checkinDbSettings.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not checkinDbSettings.host:
        raise RuntimeError("CHECKIN_DB_HOST ist nicht gesetzt")
    connectable = create_engine(checkinDbSettings.url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
