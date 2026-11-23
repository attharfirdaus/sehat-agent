"""Dashboard, riwayat chat, hapus akun, clinician queue/keputusan, admin ingest."""

from datetime import UTC, date, datetime
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import insert, select, update

from app.db.models import Assessment, ClinicianReview, DailyLog, User
from app.db.models import Plan as PlanRow
from app.db.session import SessionLocal
from app.graph.build import thread_config
from app.schemas import PlanIn
from app.tools import mocks, plan
from tests.test_api_data import PROFILE, register


async def set_role(uid: int, role: str) -> None:
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.id == uid).values(role=role))
        await s.commit()


async def assessment_dict() -> dict:
    p, latest = mocks.SAMPLE_PROFILE, mocks.SAMPLE_LATEST
    return {
        "flags": [f.model_dump(mode="json") for f in await mocks.guideline_flags(p, latest)],
        "framingham": (await mocks.framingham_nonlab(p, latest)).model_dump(mode="json"),
        "diabetes": (await mocks.predict_diabetes(mocks.SAMPLE_FEATURES)).model_dump(mode="json"),
        "trends": (await mocks.compute_trends(1)).model_dump(mode="json"),
    }


def test_auth_me_and_roles(client: TestClient, run: Any) -> None:
    uid = register(client)
    assert client.get("/api/auth/me").json()["role"] == "user"
    assert client.get("/api/clinician/queue").status_code == 403
    assert client.post("/api/admin/ingest").status_code == 403
    run(set_role, uid, "clinician")
    assert client.get("/api/clinician/queue").status_code == 200
    assert client.post("/api/admin/ingest").status_code == 403


def test_dashboard(client: TestClient, run: Any) -> None:
    uid = register(client)
    empty = client.get("/api/dashboard").json()
    assert empty["assessment"] is None and empty["plan"] is None and empty["chart"]["data"] == []
    assert client.get("/api/dashboard", params={"days": 31}).status_code == 422

    async def seed() -> None:
        async with SessionLocal() as s:
            s.add(DailyLog(user_id=uid, log_date=date.today(), steps=5000, source="web"))
            await s.execute(
                insert(Assessment).values(user_id=uid, thread_id="t", **await assessment_dict())
            )
            await s.commit()

    run(seed)
    body = client.get("/api/dashboard", params={"days": 30}).json()
    assert body["trends"]["days"] == 30 and body["assessment"]["diabetes"]["band"] == "moderate"
    assert "steps" in body["chart"]["series"]


def test_chat_history(client: TestClient, run: Any) -> None:
    uid = register(client)
    assert client.get("/api/chat/history").json() == {"messages": [], "pending": None}
    graph = client.app.state.graph  # type: ignore[attr-defined]
    run(
        graph.aupdate_state,
        thread_config(uid),
        {"messages": [HumanMessage("halo"), AIMessage("Hai!")]},
        "response",
    )
    assert client.get("/api/chat/history").json()["messages"] == [
        {"role": "user", "text": "halo"},
        {"role": "assistant", "text": "Hai!"},
    ]


def test_delete_account(client: TestClient, run: Any) -> None:
    uid = register(client)
    client.put("/api/profile", json=PROFILE)
    graph = client.app.state.graph  # type: ignore[attr-defined]
    run(graph.aupdate_state, thread_config(uid), {"messages": [HumanMessage("x")]}, "response")
    run(plan.save_plan, uid, PlanIn(content=mocks.SAMPLE_PLAN_CONTENT, starts_on=date.today()))
    assert client.delete("/api/account").status_code == 204

    async def gone() -> tuple[Any, Any]:
        async with SessionLocal() as s:
            return await s.get(User, uid), await s.scalar(
                select(PlanRow.id).where(PlanRow.user_id == uid)
            )

    assert run(gone) == (None, None)
    assert not run(graph.aget_state, thread_config(uid)).values
    assert client.get("/api/profile").status_code == 401


def test_clinician_flow(client: TestClient, run: Any) -> None:
    patient = register(client)
    client.cookies.clear()
    reviewer = register(client)
    run(set_role, reviewer, "clinician")
    review_graph = client.app.state.graph.review_graph  # type: ignore[attr-defined]

    async def create_review() -> int:
        p = await plan.save_plan(
            patient, PlanIn(content=mocks.SAMPLE_PLAN_CONTENT, starts_on=date.today())
        )
        async with SessionLocal() as s:
            rid = await s.scalar(
                insert(ClinicianReview)
                .values(plan_id=p.id, thread_id=f"review-{p.id}")
                .returning(ClinicianReview.id)
            )
            await s.commit()
        await review_graph.ainvoke(
            {
                "review_id": rid,
                "plan_id": p.id,
                "user_id": patient,
                "assessment": await assessment_dict(),
            },
            {"configurable": {"thread_id": f"review-{p.id}"}},
        )
        return rid

    rid = run(create_review)
    queue = client.get("/api/clinician/queue").json()
    mine = [q for q in queue if q["review_id"] == rid]
    assert mine and mine[0]["payload"]["type"] == "clinician_review"
    edited = mocks.SAMPLE_PLAN_CONTENT.model_dump()
    edited["weeks"][0]["actions"][0]["text"] = "Jalan kaki 15 menit."
    bad = client.post(f"/api/clinician/reviews/{rid}", json={"decision": "edit"})
    assert bad.status_code == 422
    r = client.post(
        f"/api/clinician/reviews/{rid}",
        json={"decision": "edit", "edited_content": edited, "note": "lebih ringan"},
    )
    assert r.json() == {"plan_status": "active"}
    assert (
        client.post(f"/api/clinician/reviews/{rid}", json={"decision": "approve"}).status_code
        == 409
    )
    assert all(q["review_id"] != rid for q in client.get("/api/clinician/queue").json())

    async def stored() -> tuple[Any, Any]:
        async with SessionLocal() as s:
            rev = await s.get(ClinicianReview, rid)
            p = await s.get(PlanRow, rev.plan_id)
            return rev, p

    rev, p = run(stored)
    assert (rev.decision, rev.reviewer_id, rev.note) == ("edit", reviewer, "lebih ringan")
    assert (
        rev.decided_at <= datetime.now(UTC)
        and p.content["weeks"][0]["actions"][0]["text"] == "Jalan kaki 15 menit."
    )
