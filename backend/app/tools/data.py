from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import DailyLog, Measurement
from app.db.models import Profile as ProfileRow
from app.db.session import SessionLocal
from app.schemas import (
    DailyLogIn,
    DailyLogOut,
    HistoryRow,
    HistoryTable,
    MeasurementIn,
    MeasurementOut,
    Metric,
    Profile,
)
from app.settings import settings

# Metric (bagian 7) -> kolom daily_logs / kind measurements (bagian 9)
LOG_COLUMNS = {
    "steps": "steps",
    "sleep_hours": "sleep_hours",
    "water_l": "water_l",
    "calories": "calories_kcal",
    "smoked": "smoked",
    "alcohol": "alcohol",
}
MEASUREMENT_KINDS = {
    "systolic": "systolic",
    "diastolic": "diastolic",
    "resting_hr": "resting_hr",
    "weight_kg": "weight_kg",
    "cholesterol": "cholesterol_total",
}
_LOG_FIELDS = ("steps", "sleep_hours", "water_l", "calories_kcal", "smoked", "alcohol")


def today() -> date:
    return datetime.now(ZoneInfo(settings.TZ)).date()


async def save_daily_log(user_id: int, log: DailyLogIn) -> DailyLogOut:
    """Upsert daily log user untuk `log.log_date` (unik per user per tanggal)."""
    values = {"user_id": user_id, **log.model_dump()}
    stmt = insert(DailyLog).values(**values)
    # TODO(PRD): check-in kedua di hari yang sama menimpa field yang diisi saja (COALESCE),
    # field kosong mempertahankan nilai lama.
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "log_date"],
        set_={
            **{f: func.coalesce(stmt.excluded[f], DailyLog.__table__.c[f]) for f in _LOG_FIELDS},
            "source": stmt.excluded.source,
            "raw_text": func.coalesce(stmt.excluded.raw_text, DailyLog.raw_text),
        },
    ).returning(DailyLog)
    async with SessionLocal() as session:
        row = await session.scalar(stmt)
        await session.commit()
    return DailyLogOut.model_validate(row, from_attributes=True)


async def save_measurement(user_id: int, m: MeasurementIn) -> MeasurementOut:
    """Simpan satu pengukuran bertanggal."""
    row = Measurement(user_id=user_id, **m.model_dump())
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
    return MeasurementOut.model_validate(row, from_attributes=True)


async def get_profile(user_id: int) -> Profile:
    """Ambil profil statis user. LookupError kalau belum onboarding."""
    async with SessionLocal() as session:
        row = await session.get(ProfileRow, user_id)
    if row is None:
        raise LookupError(f"profile user {user_id} belum ada")
    return Profile.model_validate(row, from_attributes=True)


async def query_history(user_id: int, metrics: list[Metric], days: int = 7) -> HistoryTable:
    """Tabel histori harian user untuk metrik terpilih selama `days` hari terakhir (1..90).

    Satu baris per tanggal (termasuk hari tanpa data, nilainya None). Measurement
    dirata-rata per hari (zona waktu settings.TZ).

    Tool ★ untuk History Q&A agent.
    """
    days = max(1, min(days, 90))
    end = today()
    start = end - timedelta(days=days - 1)
    table = {start + timedelta(days=i): dict.fromkeys(metrics) for i in range(days)}

    log_metrics = [m for m in metrics if m in LOG_COLUMNS]
    kinds = {MEASUREMENT_KINDS[m]: m for m in metrics if m in MEASUREMENT_KINDS}
    async with SessionLocal() as session:
        if log_metrics:
            logs = await session.scalars(
                select(DailyLog).where(
                    DailyLog.user_id == user_id, DailyLog.log_date.between(start, end)
                )
            )
            for log in logs:
                for m in log_metrics:
                    v = getattr(log, LOG_COLUMNS[m])
                    table[log.log_date][m] = v if v is None or isinstance(v, bool) else float(v)
        if kinds:
            local_day = cast(func.timezone(settings.TZ, Measurement.measured_at), Date)
            rows = await session.execute(
                select(local_day, Measurement.kind, func.avg(Measurement.value))
                .where(
                    Measurement.user_id == user_id,
                    Measurement.kind.in_(kinds),
                    local_day.between(start, end),
                )
                .group_by(local_day, Measurement.kind)
            )
            for day, kind, avg in rows:
                table[day][kinds[kind]] = round(float(avg), 1)

    return HistoryTable(
        metrics=metrics,
        days=days,
        rows=[HistoryRow(date=d, values=v) for d, v in table.items()],
    )
