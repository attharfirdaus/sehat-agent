import pytest
from fastapi.testclient import TestClient

from app.api import health
from app.settings import settings


def _get(client: TestClient, monkeypatch: pytest.MonkeyPatch, models: list[str] | None) -> dict:
    async def fake() -> list[str] | None:
        return models

    monkeypatch.setattr(health, "ollama_models", fake)
    r = client.get("/api/health")
    assert r.status_code == 200
    return r.json()


def test_health_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _get(client, monkeypatch, ["bge-m3:latest", settings.LLM_MODEL])
    assert body == {
        "status": "ok",
        "db": True,
        "ollama": True,
        "llm_model": settings.LLM_MODEL,
        "llm_model_available": True,
    }


def test_health_model_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _get(client, monkeypatch, ["qwen3:8b"])
    assert body["status"] == "degraded" and body["llm_model_available"] is False


def test_health_ollama_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    body = _get(client, monkeypatch, None)
    assert body["ollama"] is False and body["status"] == "degraded"
