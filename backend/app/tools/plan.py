from sqlalchemy import select, update

from app.db.models import Plan as PlanRow
from app.db.session import SessionLocal
from app.schemas import Plan, PlanIn


async def get_active_plan(user_id: int) -> Plan | None:
    """Plan berstatus `active` milik user, atau None.

    Tool ★ untuk History Q&A agent.
    """
    async with SessionLocal() as session:
        row = await session.scalar(
            select(PlanRow)
            .where(PlanRow.user_id == user_id, PlanRow.status == "active")
            .order_by(PlanRow.created_at.desc())
            .limit(1)
        )
    return None if row is None else Plan.model_validate(row, from_attributes=True)


async def save_plan(user_id: int, plan: PlanIn) -> Plan:
    """Simpan plan baru. Kalau statusnya `active`, plan aktif sebelumnya jadi `superseded`."""
    async with SessionLocal() as session:
        if plan.status == "active":
            await session.execute(
                update(PlanRow)
                .where(PlanRow.user_id == user_id, PlanRow.status == "active")
                .values(status="superseded")
            )
        row = PlanRow(
            user_id=user_id,
            **plan.model_dump(exclude={"content"}),
            content=plan.content.model_dump(mode="json"),
        )
        session.add(row)
        await session.commit()
    return Plan.model_validate(row, from_attributes=True)
