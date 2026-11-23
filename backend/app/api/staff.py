"""Endpoint clinician (HITL, bagian 6.3) dan admin (bagian 10)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from langgraph.types import Command
from sqlalchemy import select

from app.api.auth import CurrentUser, Session, require_role
from app.db.models import ClinicianReview, User
from app.db.models import Plan as PlanRow
from app.rag.ingest import ingest
from app.schemas import ClinicianDecision, ClinicianReviewPayload, ReviewItem

clinician = APIRouter(
    prefix="/clinician", dependencies=[Depends(require_role("clinician", "admin"))]
)
admin = APIRouter(prefix="/admin", dependencies=[Depends(require_role("admin"))])


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@clinician.get("/queue")
async def queue(session: Session, request: Request) -> list[ReviewItem]:
    review_graph = request.app.state.graph.review_graph
    rows = await session.execute(
        select(ClinicianReview, User.name)
        .join(PlanRow, PlanRow.id == ClinicianReview.plan_id)
        .join(User, User.id == PlanRow.user_id)
        .where(ClinicianReview.decision.is_(None))
        .order_by(ClinicianReview.created_at)
    )
    items = []
    for review, name in rows:
        snap = await review_graph.aget_state(_config(review.thread_id))
        if snap.interrupts:
            items.append(
                ReviewItem(
                    review_id=review.id,
                    plan_id=review.plan_id,
                    user_name=name,
                    created_at=review.created_at,
                    payload=ClinicianReviewPayload.model_validate(snap.interrupts[0].value),
                )
            )
    return items


@clinician.post("/reviews/{review_id}")
async def decide(
    review_id: int, body: ClinicianDecision, user: CurrentUser, session: Session, request: Request
) -> dict[str, str]:
    review = await session.get(ClinicianReview, review_id)
    if review is None:
        raise HTTPException(404, "review not found")
    if review.decision is not None:
        raise HTTPException(409, "review sudah diputuskan")
    review.reviewer_id = user.id
    await session.commit()
    await request.app.state.graph.review_graph.ainvoke(
        Command(resume=body.model_dump(mode="json")), _config(review.thread_id)
    )
    status = await session.scalar(select(PlanRow.status).where(PlanRow.id == review.plan_id))
    return {"plan_status": str(status)}


@admin.post("/ingest")
async def run_ingest() -> dict[str, str]:
    return await ingest()
