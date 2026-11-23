"""Graph dengan LLM di-mock (bagian 15): routing, resume interrupt, red flag, revisi, review."""

import base64
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import select

from app.db.models import DailyLog, FoodEntry, Measurement, RedFlagEvent, User
from app.db.models import Plan as PlanRow
from app.db.models import Profile as ProfileRow
from app.db.session import SessionLocal
from app.graph import llm, toolbox
from app.graph.build import build_graph, thread_config
from app.graph.nodes import assess, intake
from app.graph.nodes.answer import KnowledgeAnswer
from app.graph.nodes.assess import Interpretation, Queries, Rubric
from app.graph.nodes.intake import Extracted, IntentOut
from app.safety.templates import DISCLAIMER
from app.schemas import (
    DiabetesPrediction,
    PlanAction,
    PlanContent,
    PlanTarget,
    PlanWeek,
    RedFlag,
)
from app.tools import mocks
from app.tools.data import today

CATAT = "catat: jalan 6rb, tidur 5 jam, air 2 liter, tidak merokok, tidak minum alkohol"
FULL_LOG = {
    "log": {"steps": 6000, "sleep_hours": 5, "water_l": 2, "smoked": False, "alcohol": False}
}


def plan(citations: list[str]) -> PlanContent:
    return PlanContent(
        weeks=[
            PlanWeek(
                range=f"minggu {i}",
                targets=[PlanTarget(metric="steps", target=7000)],
                actions=[PlanAction(text="Jalan kaki setelah makan siang.", citations=citations)],
            )
            for i in range(1, 5)
        ]
    )


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """responses[NamaSchema] = nilai, atau list nilai yang dipakai berurutan."""
    responses: dict[str, Any] = {}

    async def structured(schema: type, system: str, user: str, reasoning: bool = False) -> Any:
        r = responses.get(schema.__name__)
        r = r.pop(0) if isinstance(r, list) else r
        return schema.model_validate(r) if isinstance(r, dict) else r

    monkeypatch.setattr(llm, "structured", structured)
    # Tool berat diganti mock: model diabetes (`make train`) dan korpus (`make ingest`) tidak
    # tersedia di DB test.
    monkeypatch.setattr(toolbox, "predict_diabetes", mocks.predict_diabetes)
    monkeypatch.setattr(toolbox, "retrieve_guidelines", mocks.retrieve_guidelines)
    monkeypatch.setattr(toolbox, "estimate_meal_from_image", mocks.estimate_meal_from_image)
    monkeypatch.setattr(llm, "chat", lambda reasoning: FakeListChatModel(responses=["Halo juga!"]))
    return responses


@pytest.fixture
def graph() -> Any:
    return build_graph(InMemorySaver())


async def make_user(with_profile: bool = True) -> int:
    async with SessionLocal() as s:
        user = User(email=f"g{uuid.uuid4().hex}@x.id", password_hash="x", name="G")
        s.add(user)
        await s.flush()
        if with_profile:
            s.add(
                ProfileRow(
                    user_id=user.id,
                    birth_date=today().replace(year=1990),
                    sex="male",
                    height_cm=170,
                )
            )
            s.add(
                Measurement(
                    user_id=user.id, kind="weight_kg", value=72, measured_at=datetime.now(UTC)
                )
            )
        await s.commit()
        return user.id


async def turn(graph: Any, graph_input: Any, uid: int) -> tuple[list[str], list[dict], dict]:
    nodes, interrupts = [], []
    async for update in graph.astream(graph_input, thread_config(uid), stream_mode="updates"):
        for name, value in update.items():
            if name == "__interrupt__":
                interrupts += [i.value for i in value]
            else:
                nodes.append(name)
    return nodes, interrupts, (await graph.aget_state(thread_config(uid))).values


def msg(uid: int, text: str, image: str | None = None) -> dict:
    return {
        "user_id": uid,
        "channel": "web",
        "image_b64": image,
        "draft_log": None,
        "messages": [HumanMessage(text)],
    }


async def db_rows(model: Any, uid: int) -> list[Any]:
    async with SessionLocal() as s:
        return list(await s.scalars(select(model).where(model.user_id == uid)))


def pipeline(fake: dict, citations: list[str] | None = None) -> None:
    fake["Interpretation"] = Interpretation(summary="Tidur kurang dari target.")
    fake["Queries"] = Queries(queries=["physical activity adults"])
    fake["PlanContent"] = plan(["WHO-PA-2020"] if citations is None else citations)
    fake["Rubric"] = Rubric(no_diagnosis_or_medication=True, risk_calibrated=True)


@pytest.mark.parametrize(
    ("intent", "node"),
    [
        ("smalltalk", "response"),
        ("health_info", "knowledge_info"),
        ("history_question", "history_qa"),
    ],
)
def test_routing(fake: dict, graph: Any, run: Any, intent: str, node: str) -> None:
    fake["IntentOut"] = IntentOut(intent=intent)  # type: ignore[arg-type]
    fake["KnowledgeAnswer"] = KnowledgeAnswer(
        answer="Aktif 150 menit/minggu.", citations=["WHO-PA-2020"], found=True
    )
    uid = run(make_user)
    nodes, interrupts, state = run(turn, graph, msg(uid, "halo"), uid)
    assert node in nodes and "coach" not in nodes and not interrupts
    assert state["final_response"]
    if intent == "health_info":
        assert "WHO-PA-2020" in state["final_response"]


def test_supervisor_fallback(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = None
    uid = run(make_user)
    _, _, state = run(turn, graph, msg(uid, "???"), uid)
    assert state["final_response"].startswith("Maaf, saya belum menangkap")


def test_log_clarify_confirm_full_pipeline(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = [
        Extracted.model_validate({"log": {"steps": 6000, "sleep_hours": 5}}),
        Extracted.model_validate({"log": {"water_l": 2, "smoked": False, "alcohol": False}}),
    ]
    pipeline(fake)
    uid = run(make_user)

    _, interrupts, _ = run(turn, graph, msg(uid, "jalan 6rb, tidur 5 jam"), uid)
    assert interrupts[0]["type"] == "clarify"
    assert set(interrupts[0]["missing"]) == {"water_l", "smoked", "alcohol"}

    _, interrupts, _ = run(turn, graph, Command(resume="air 2 liter, tidak rokok, no alkohol"), uid)
    assert interrupts[0]["type"] == "confirm_log" and interrupts[0]["log"]["water_l"] == 2

    nodes, interrupts, state = run(turn, graph, Command(resume={"action": "confirm"}), uid)
    assert not interrupts
    assert nodes[-5:] == ["risk_analyst", "knowledge", "coach", "safety_critic", "response"]
    assert DISCLAIMER in state["final_response"] and "WHO-PA-2020" in state["final_response"]
    assert state["chart_payload"]["series"]
    assert set(state["timings"]) >= {"load_context", "coach", "response"}
    [log] = run(db_rows, DailyLog, uid)
    assert (log.steps, float(log.water_l), log.smoked) == (6000, 2.0, False)
    assert [p.status for p in run(db_rows, PlanRow, uid)] == ["active"]


def test_intake_drops_measurement_not_in_text(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate(
        {
            **FULL_LOG,
            "measurements": [
                {"kind": "systolic", "value": 130},
                {"kind": "weight_kg", "value": 70.5},
                {"kind": "weight_kg", "value": 6},
                {"kind": "resting_hr", "value": 70.5},
            ],
        }
    )
    uid = run(make_user)
    text = "berat 70,5 kg, tidur 6 jam, tidak merokok, tidak minum alkohol"
    _, interrupts, _ = run(turn, graph, msg(uid, text), uid)
    assert [m["kind"] for m in interrupts[0]["measurements"]] == ["weight_kg"]


def test_intake_drops_unmentioned_smoking_alcohol(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate(FULL_LOG)  # LLM mengisi smoked/alcohol=false
    uid = run(make_user)
    _, interrupts, _ = run(turn, graph, msg(uid, "jalan 6rb, tidur 5 jam, air 2 liter"), uid)
    assert interrupts[0]["type"] == "clarify"
    assert interrupts[0]["missing"] == ["smoked", "alcohol"]


def test_confirm_edit(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate(FULL_LOG)
    pipeline(fake)
    uid = run(make_user)
    run(turn, graph, msg(uid, CATAT), uid)
    edited = {"log_date": today().isoformat(), "source": "web", **FULL_LOG["log"], "steps": 9000}
    run(turn, graph, Command(resume={"action": "edit", "log": edited}), uid)
    assert run(db_rows, DailyLog, uid)[0].steps == 9000


def test_critic_fails_twice_then_safe_fallback(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate(FULL_LOG)
    pipeline(fake, citations=[])  # aksi tanpa sitasi selalu gagal cek kode
    uid = run(make_user)
    run(turn, graph, msg(uid, CATAT), uid)
    nodes, _, state = run(turn, graph, Command(resume={"action": "confirm"}), uid)
    assert nodes.count("coach") == 2 and "safe_fallback" in nodes
    assert state["revision_count"] == 2 and state["critique"]["fallback"]
    assert "Saran umum" in state["final_response"]
    assert run(db_rows, PlanRow, uid) == []  # versi fallback tidak disimpan sebagai plan


def test_number_without_basis_rejected(run: Any) -> None:
    bad = PlanContent(
        weeks=[
            PlanWeek(
                range="minggu 1",
                targets=[],
                actions=[
                    PlanAction(text="Jalan 9999 langkah tambahan.", citations=["WHO-PA-2020"])
                ],
            )
        ]
    )
    state = {"passages": [{"source_id": "WHO-PA-2020", "text": "150 menit"}], "flags": []}
    assert any("9999" in i for i in assess.deterministic_issues(state, bad))  # type: ignore[arg-type]
    ok = bad.model_copy(deep=True)
    ok.weeks[0].actions[0].text = "Naikkan dari rata-rata 5.300 ke 6.000 langkah, tidur 5,8 jam."
    ok.weeks[0].targets = [PlanTarget(metric="steps", target=6000)]
    state["trends"] = {"steps": 5300, "sleep": 5.8}
    ok.weeks = [w.model_copy(deep=True) for w in ok.weeks * 4]
    assert assess.deterministic_issues(state, ok) == []  # type: ignore[arg-type]
    ok.weeks[1].actions[0].text = "Hindari penurunan yang наблюдается."
    one_week = ok.model_copy(update={"weeks": ok.weeks[:1]})
    assert len(assess.deterministic_issues(state, ok)) == 1  # type: ignore[arg-type]
    assert "4 minggu" in assess.deterministic_issues(state, one_week)[0]  # type: ignore[arg-type]


def test_rf_symptom_never_reaches_coach(
    fake: dict, graph: Any, run: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def rules(latest: Any, text: str) -> list[RedFlag]:
        return [RedFlag(code="RF-SYMPTOM", detail={"keyword": "nyeri dada"})]

    monkeypatch.setattr(toolbox, "red_flag_rules", rules)
    uid = run(make_user)
    nodes, _, state = run(turn, graph, msg(uid, "dada sakit banget"), uid)
    assert nodes[-1] == "emergency_response"
    assert not {"supervisor", "coach", "response"} & set(nodes)
    assert "119" in state["final_response"]
    assert [e.code for e in run(db_rows, RedFlagEvent, uid)] == ["RF-SYMPTOM"]


def test_high_risk_goes_to_clinician_review(
    fake: dict, graph: Any, run: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def high(features: Any) -> DiabetesPrediction:
        return (await mocks.predict_diabetes(features)).model_copy(update={"band": "high"})

    monkeypatch.setattr(toolbox, "predict_diabetes", high)
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate(FULL_LOG)
    pipeline(fake)
    uid = run(make_user)
    run(turn, graph, msg(uid, CATAT), uid)
    nodes, interrupts, state = run(turn, graph, Command(resume={"action": "confirm"}), uid)
    assert "create_review" in nodes and not interrupts  # thread user tidak terblokir
    assert "sedang ditinjau" in state["final_response"]
    [pending] = run(db_rows, PlanRow, uid)
    assert pending.status == "pending_review"

    review = graph.review_graph
    cfg = {"configurable": {"thread_id": f"review-{pending.id}"}}
    snap = run(review.aget_state, cfg)
    assert snap.interrupts[0].value["type"] == "clinician_review"
    run(review.ainvoke, Command(resume={"decision": "approve", "note": "ok"}), cfg)
    assert [p.status for p in run(db_rows, PlanRow, uid)] == ["active"]


def test_meal_photo_confirm(
    fake: dict, graph: Any, run: Any, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(intake, "UPLOAD_DIR", tmp_path)
    uid = run(make_user)
    image = base64.b64encode(b"\xff\xd8fakejpeg").decode()
    nodes, interrupts, _ = run(turn, graph, msg(uid, "", image), uid)
    assert "supervisor" in nodes and interrupts[0]["type"] == "confirm_meal"
    _, _, state = run(turn, graph, Command(resume={"action": "confirm"}), uid)
    [entry] = run(db_rows, FoodEntry, uid)
    assert entry.confirmed and entry.kcal_estimate == 490 and list(tmp_path.iterdir())
    assert run(db_rows, DailyLog, uid)[0].calories_kcal == 490
    assert state["final_response"].startswith("Catatan tersimpan")


def test_meal_cancel(fake: dict, graph: Any, run: Any) -> None:
    uid = run(make_user)
    run(turn, graph, msg(uid, "", base64.b64encode(b"x").decode()), uid)
    _, _, state = run(turn, graph, Command(resume={"action": "cancel"}), uid)
    assert state["final_response"].startswith("Baik, makanan tidak disimpan")
    assert run(db_rows, FoodEntry, uid) == []


def test_profile_missing_skips_risk(fake: dict, graph: Any, run: Any) -> None:
    fake["IntentOut"] = IntentOut(intent="log")
    fake["Extracted"] = Extracted.model_validate(FULL_LOG)
    uid = run(make_user, False)
    run(turn, graph, msg(uid, CATAT), uid)
    nodes, _, state = run(turn, graph, Command(resume={"action": "confirm"}), uid)
    assert "knowledge" not in nodes and "/onboarding" in state["final_response"]
