from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import make_url

from app.api import auth, chat, data, health, staff
from app.graph.build import build_graph
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conninfo = make_url(settings.DATABASE_URL).set(drivername="postgresql")
    # ponytail: satu koneksi untuk checkpointer (akses diserialisasi), ganti AsyncConnectionPool
    # kalau banyak user bersamaan.
    async with AsyncPostgresSaver.from_conn_string(
        conninfo.render_as_string(hide_password=False)
    ) as saver:
        await saver.setup()  # tabel checkpoint dibuat oleh LangGraph (bagian 9)
        app.state.graph = build_graph(saver)
        yield


app = FastAPI(title="SehatAgent", lifespan=lifespan)
for router in (health.router, auth.router, data.router, chat.router, staff.clinician, staff.admin):
    app.include_router(router, prefix="/api")
