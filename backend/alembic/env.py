from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.db.models import Base
from app.settings import settings

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

# Test mengoper URL lewat config; selain itu pakai settings.
url = context.config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL


def run_migrations_online() -> None:
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
