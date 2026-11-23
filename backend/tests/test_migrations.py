from sqlalchemy import create_engine, inspect

from alembic import command
from app.db.models import Base
from app.settings import settings
from tests.conftest import alembic_config


def test_upgrade_downgrade_upgrade() -> None:
    cfg = alembic_config()
    engine = create_engine(settings.DATABASE_URL)

    command.upgrade(cfg, "head")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    command.downgrade(cfg, "base")
    # tabel checkpoint LangGraph bukan milik Alembic, jadi hanya tabel bagian 9 yang dicek
    assert not set(Base.metadata.tables) & set(inspect(engine).get_table_names())
    command.upgrade(cfg, "head")
    cols = {c["name"]: c for c in inspect(engine).get_columns("kb_chunks")}
    assert str(cols["embedding"]["type"]) == "VECTOR(1024)"
    engine.dispose()
