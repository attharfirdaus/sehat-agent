import os

os.environ.setdefault("EMBED_DIM", "1024")  # nilai test, bukan pilihan model; sebelum import app
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, inspect, make_url, text  # noqa: E402

from alembic import command  # noqa: E402
from app.settings import settings  # noqa: E402

# Test migrasi menjalankan downgrade (drop semua tabel), jadi selalu pakai DB terpisah.
settings.DATABASE_URL = (
    make_url(settings.DATABASE_URL).set(database="sehat_test").render_as_string(hide_password=False)
)


def alembic_config() -> Config:
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    command.upgrade(alembic_config(), "head")
    # Checkpoint LangGraph tidak ikut migrasi; id user bisa terpakai ulang setelah test
    # downgrade, jadi thread lama dihapus supaya tidak ada interrupt basi.
    engine = create_engine(settings.DATABASE_URL)
    tables = {"checkpoints", "checkpoint_blobs", "checkpoint_writes"}
    if tables <= set(inspect(engine).get_table_names()):
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE " + ", ".join(sorted(tables))))
    engine.dispose()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Satu TestClient (satu event loop) untuk semua test: pool async engine terikat ke loop."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def run(client: TestClient):  # type: ignore[no-untyped-def]
    """Jalankan coroutine function di event loop yang sama dengan client."""
    return client.portal.call
