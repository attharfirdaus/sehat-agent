import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.settings import settings

router = APIRouter()


async def check_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def ollama_models() -> list[str] | None:
    """Nama model dari Ollama /api/tags, atau None kalau Ollama tidak bisa dihubungi."""
    try:
        async with httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=3) as client:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
        return [m["name"] for m in resp.json()["models"]]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def _norm(tag: str) -> str:
    return tag if ":" in tag else f"{tag}:latest"


@router.get("/health")
async def health() -> dict[str, object]:
    db = await check_db()
    models = await ollama_models()
    model_ok = models is not None and _norm(settings.LLM_MODEL) in {_norm(m) for m in models}
    return {
        "status": "ok" if db and model_ok else "degraded",
        "db": db,
        "ollama": models is not None,
        "llm_model": settings.LLM_MODEL,
        "llm_model_available": model_ok,
    }
