from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert

from app.api.auth import COOKIE, CurrentUser, Session
from app.db.models import AgentRun, ClinicianReview, DailyLog, FoodEntry, RedFlagEvent, User
from app.db.models import Assessment as AssessmentRow
from app.db.models import Plan as PlanRow
from app.db.models import Profile as ProfileRow
from app.schemas import (
    Assessment,
    DailyLogOut,
    Dashboard,
    MeasurementIn,
    MeasurementOut,
    Plan,
    Profile,
    ProfileIn,
    RedFlagEventOut,
)
from app.tools import analytics, charts, data, plan

router = APIRouter()


@router.get("/profile")
async def read_profile(user: CurrentUser) -> Profile:
    try:
        return await data.get_profile(user.id)
    except LookupError:
        raise HTTPException(404, "profile not found") from None


@router.put("/profile")
async def write_profile(body: ProfileIn, user: CurrentUser, session: Session) -> Profile:
    values = body.model_dump()
    stmt = insert(ProfileRow).values(user_id=user.id, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id"], set_={**values, "updated_at": stmt.excluded.updated_at}
    )
    await session.execute(stmt)
    await session.commit()
    return Profile(user_id=user.id, **values)


@router.get("/logs")
async def list_logs(
    user: CurrentUser,
    session: Session,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> list[DailyLogOut]:
    # TODO(PRD): default rentang tidak dirinci; pakai 30 hari terakhir sampai hari ini.
    to = to or data.today()
    from_ = from_ or to - timedelta(days=29)
    rows = await session.scalars(
        select(DailyLog)
        .where(DailyLog.user_id == user.id, DailyLog.log_date.between(from_, to))
        .order_by(DailyLog.log_date)
    )
    return [DailyLogOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/measurements", status_code=201)
async def add_measurement(body: MeasurementIn, user: CurrentUser) -> MeasurementOut:
    return await data.save_measurement(user.id, body)


@router.get("/plans/active")
async def active_plan(user: CurrentUser) -> Plan | None:
    return await plan.get_active_plan(user.id)


@router.get("/dashboard")
async def dashboard(
    user: CurrentUser, session: Session, days: Annotated[int, Query(ge=1, le=30)] = 7
) -> Dashboard:
    trends = await analytics.compute_trends(user.id, days)
    row = await session.scalar(
        select(AssessmentRow)
        .where(AssessmentRow.user_id == user.id)
        .order_by(AssessmentRow.created_at.desc())
        .limit(1)
    )
    events = await session.scalars(
        select(RedFlagEvent)
        .where(RedFlagEvent.user_id == user.id)
        .order_by(RedFlagEvent.created_at.desc())
        .limit(20)
    )
    return Dashboard(
        trends=trends,
        chart=await charts.build_chart_payload(trends),
        assessment=Assessment.model_validate(row, from_attributes=True) if row else None,
        assessment_at=row.created_at if row else None,
        plan=await plan.get_active_plan(user.id),
        red_flags=[RedFlagEventOut.model_validate(e, from_attributes=True) for e in events],
    )


@router.delete("/account", status_code=204)
async def delete_account(
    user: CurrentUser, session: Session, request: Request, response: Response
) -> None:
    """Hapus akun = semua baris user + file foto + checkpoint thread (bagian 13)."""
    photos = list(
        await session.scalars(
            select(FoodEntry.image_path).where(
                FoodEntry.user_id == user.id, FoodEntry.image_path.is_not(None)
            )
        )
    )
    plan_ids = select(PlanRow.id).where(PlanRow.user_id == user.id)
    review_threads = list(
        await session.scalars(
            select(ClinicianReview.thread_id).where(ClinicianReview.plan_id.in_(plan_ids))
        )
    )
    await session.execute(delete(ClinicianReview).where(ClinicianReview.plan_id.in_(plan_ids)))
    await session.execute(
        update(ClinicianReview)
        .where(ClinicianReview.reviewer_id == user.id)
        .values(reviewer_id=None)
    )
    await session.execute(delete(AgentRun).where(AgentRun.user_id == user.id))
    await session.execute(delete(User).where(User.id == user.id))  # sisanya ON DELETE CASCADE
    await session.commit()
    for p in photos:
        Path(p).unlink(missing_ok=True)
    saver = request.app.state.graph.checkpointer
    for thread in [f"user-{user.id}", *review_threads]:
        await saver.adelete_thread(thread)
    response.delete_cookie(COOKIE)
