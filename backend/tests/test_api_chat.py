import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeListChatModel
from sqlalchemy import select

from app.db.models import AgentRun
from app.db.session import SessionLocal
from app.graph import llm, toolbox
from app.graph.nodes.intake import Extracted, IntentOut
from app.tools import mocks
from tests.test_api_data import register


def events(body: str) -> list[tuple[str, Any]]:
    out, event = [], None
    for line in body.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            out.append((event, json.loads(line.split(":", 1)[1])))
    return out


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    responses: dict[str, Any] = {}

    async def structured(schema: type, system: str, user: str, reasoning: bool = False) -> Any:
        return responses.get(schema.__name__)

    monkeypatch.setattr(llm, "structured", structured)
    # Tool berat diganti mock: model diabetes (`make train`) dan korpus (`make ingest`) tidak
    # tersedia di DB test.
    monkeypatch.setattr(toolbox, "predict_diabetes", mocks.predict_diabetes)
    monkeypatch.setattr(toolbox, "retrieve_guidelines", mocks.retrieve_guidelines)
    monkeypatch.setattr(toolbox, "estimate_meal_from_image", mocks.estimate_meal_from_image)
    monkeypatch.setattr(llm, "chat", lambda reasoning: FakeListChatModel(responses=["Halo!"]))
    return responses


def test_chat_requires_auth(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/chat", json={"message": "hai"}).status_code == 401


def test_chat_smalltalk_sse(client: TestClient, fake: dict, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="smalltalk")
    uid = register(client)
    assert client.post("/api/chat", json={"message": " "}).status_code == 422
    r = client.post("/api/chat", json={"message": "halo"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = events(r.text)
    assert ("node_start", {"node": "load_context"}) in ev
    assert ev[-1] == ("final", {"text": "Halo!"})
    assert any(e == "token" for e, _ in ev)

    async def runs() -> list[AgentRun]:
        async with SessionLocal() as s:
            return list(await s.scalars(select(AgentRun).where(AgentRun.user_id == uid)))

    [agent_run] = run(runs)
    assert agent_run.intent == "smalltalk" and agent_run.llm_calls == 1 and agent_run.total_ms


def test_chat_interrupt_and_resume(client: TestClient, fake: dict) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate({"log": {"steps": 6000}})
    register(client)
    assert client.post("/api/chat/resume", json={"value": "x"}).status_code == 409

    ev = events(client.post("/api/chat", json={"message": "jalan 6rb"}).text)
    assert ev[-1][0] == "interrupt" and ev[-1][1]["type"] == "clarify"
    # pesan biasa saat clarify menunggu = jawaban clarify
    ev = events(client.post("/api/chat", json={"message": "lupa"}).text)
    assert ev[-1][1]["type"] == "clarify"
    ev = events(client.post("/api/chat/resume", json={"value": "tidak tahu"}).text)
    assert ev[-1][1]["type"] == "confirm_log"

    bad = client.post("/api/chat/resume", json={"value": {"action": "edit"}})
    assert bad.status_code == 422
    ev = events(client.post("/api/chat/resume", json={"value": {"action": "confirm"}}).text)
    assert ev[-1][0] == "final" and "Belum lengkap" in ev[-1][1]["text"]
