"""Form check-in (POST /api/checkin): validasi, jalur graph tanpa LLM, red flag dari tensi."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import DailyLog, Measurement, RedFlagEvent
from app.db.session import SessionLocal
from app.graph import llm, toolbox
from app.graph.nodes.assess import Interpretation, Queries, Rubric
from app.tools import mocks
from tests.test_api_chat import events
from tests.test_api_data import PROFILE, register
from tests.test_graph import plan

FORM = {"steps": 7000, "sleep_hours": 6.5, "water_l": 2, "smoked": False, "alcohol": False}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """LLM palsu yang mencatat schema yang diminta; ekstraksi/routing tidak boleh dipanggil."""
    called: list[str] = []
    responses = {
        "Interpretation": Interpretation(summary="Tidur sedikit di bawah target."),
        "Queries": Queries(queries=["physical activity"]),
        "PlanContent": plan(["WHO-PA-2020"]),
        "Rubric": Rubric(no_diagnosis_or_medication=True, risk_calibrated=True),
    }

    async def structured(schema: type, system: str, user: str, reasoning: bool = False) -> Any:
        called.append(schema.__name__)
        return responses.get(schema.__name__)

    monkeypatch.setattr(llm, "structured", structured)
    monkeypatch.setattr(toolbox, "predict_diabetes", mocks.predict_diabetes)
    monkeypatch.setattr(toolbox, "retrieve_guidelines", mocks.retrieve_guidelines)
    return called


async def rows(model: Any, uid: int) -> list[Any]:
    async with SessionLocal() as s:
        return list(await s.scalars(select(model).where(model.user_id == uid)))


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in FORM.items() if k != "smoked"},  # field wajib hilang
        {**FORM, "sleep_hours": 25},
        {**FORM, "measurements": [{"kind": "weight_kg", "value": 6}]},  # tidak masuk akal
        {**FORM, "measurements": [{"kind": "systolic", "value": 120}] * 2},  # dobel
        {**FORM, "measurements": [{"kind": "gula", "value": 100}]},
    ],
)
def test_checkin_validation(client: TestClient, body: dict) -> None:
    register(client)
    assert client.post("/api/checkin", json=body).status_code == 422


def test_checkin_runs_pipeline_without_extraction(
    client: TestClient, fake: list[str], run: Any
) -> None:
    uid = register(client)
    client.put("/api/profile", json=PROFILE)
    body = {**FORM, "measurements": [{"kind": "weight_kg", "value": 58.5}]}
    ev = events(client.post("/api/checkin", json=body).text)
    nodes = [d["node"] for e, d in ev if e == "node_start"]
    assert "supervisor" not in nodes and "intake" not in nodes
    assert nodes[:3] == ["load_context", "red_flag_precheck", "save_log"]
    assert {"risk_analyst", "coach", "safety_critic", "response"} <= set(nodes)
    assert "IntentOut" not in fake and "Extracted" not in fake
    assert ev[-1][0] == "final" and "WHO-PA-2020" in ev[-1][1]["text"]

    [log] = run(rows, DailyLog, uid)
    assert (log.source, log.steps, float(log.sleep_hours), log.smoked) == ("form", 7000, 6.5, False)
    assert [(m.kind, float(m.value)) for m in run(rows, Measurement, uid)] == [("weight_kg", 58.5)]
    history = client.get("/api/chat/history").json()["messages"]
    assert history[0]["text"].startswith("Check-in lewat form: langkah 7000")

    # Pesan chat berikutnya tidak boleh memakai ulang draft form.
    fake.clear()
    ev = events(client.post("/api/chat", json={"message": "halo"}).text)
    assert "supervisor" in [d["node"] for e, d in ev if e == "node_start"]


def test_checkin_bp_crisis_red_flag(client: TestClient, fake: list[str], run: Any) -> None:
    uid = register(client)
    client.put("/api/profile", json=PROFILE)
    body = {
        **FORM,
        "measurements": [
            {"kind": "weight_kg", "value": 60},
            {"kind": "systolic", "value": 185},
            {"kind": "diastolic", "value": 100},
        ],
    }
    final = events(client.post("/api/checkin", json=body).text)[-1]
    assert final[0] == "final" and "sangat tinggi" in final[1]["text"]  # template RF-BP-CRISIS
    assert "sedang ditinjau tenaga medis" in final[1]["text"]  # RF-BP-CRISIS -> review
    assert [e.code for e in run(rows, RedFlagEvent, uid)] == ["RF-BP-CRISIS"]
