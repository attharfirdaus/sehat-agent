"""Node deterministik: load_context, red_flag_precheck, emergency_response."""

import re
from datetime import timedelta
from typing import Any, get_args

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on

from app.db.models import DailyLog, Measurement, RedFlagEvent
from app.db.session import SessionLocal
from app.graph import toolbox
from app.graph.state import GraphState
from app.safety.templates import REFERRAL
from app.schemas import LatestValues, MeasurementValue, Metric
from app.tools.data import today

EMERGENCY_CODES = {"RF-SYMPTOM", "RF-SELFHARM"}  # bagian 13: graph berhenti

# Field per giliran: di-reset tiap pesan baru supaya checkpoint giliran lalu tidak bocor.
TURN_RESET: dict[str, Any] = {
    "red_flags": [],
    "draft_log": None,
    "meal_estimate": None,
    "log_complete": False,
    "flags": [],
    "framingham": {},
    "diabetes": {},
    "trends": {},
    "passages": [],
    "plan_draft": None,
    "critique": None,
    "revision_count": 0,
    "needs_clinician": False,
    "final_response": None,
    "chart_payload": None,
}


def last_user_text(state: GraphState) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def number_readings(token: str) -> set[float]:
    """Semua bacaan angka: "6.000" -> {6.0, 6000}, "5,8" -> {5.8, 58} (format ID dan EN)."""
    readings = {float(re.sub(r"[.,]", "", token))}
    if len(re.findall(r"[.,]", token)) == 1:
        readings.add(float(token.replace(",", ".")))
    return readings


def number_tokens(text: str) -> list[str]:
    return _NUMBER.findall(text)


def numbers_in(text: str) -> set[float]:
    return {r for t in number_tokens(text) for r in number_readings(t)}


def from_form(state: GraphState) -> dict | None:
    """Draft dari POST /api/checkin. Input chat selalu mengirim draft_log=None, jadi draft
    form giliran lalu tidak terbawa."""
    draft = state.get("draft_log")
    return draft if draft and draft.get("from_form") else None


def is_emergency(red_flags: list[dict]) -> bool:
    return any(f["code"] in EMERGENCY_CODES for f in red_flags)


async def latest_values(user_id: int) -> LatestValues:
    """Measurement terakhir per jenis + ringkasan log 7 hari terakhir."""
    since = today() - timedelta(days=6)
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Measurement.kind, Measurement.value, Measurement.measured_at)
            .where(Measurement.user_id == user_id)
            .ext(distinct_on(Measurement.kind))
            .order_by(Measurement.kind, Measurement.measured_at.desc())
        )
        latest = {k: MeasurementValue(value=float(v), measured_at=t) for k, v, t in rows}
        n, steps, sleep, smoked = (
            await session.execute(
                select(
                    func.count(),
                    func.avg(DailyLog.steps),
                    func.avg(DailyLog.sleep_hours),
                    func.count().filter(DailyLog.smoked.is_(True)),
                ).where(DailyLog.user_id == user_id, DailyLog.log_date >= since)
            )
        ).one()
    return LatestValues(
        **latest,
        avg_steps_7d=None if steps is None else float(steps),
        avg_sleep_7d=None if sleep is None else float(sleep),
        smoked_days_7d=smoked if n else None,
    )


async def load_context(state: GraphState) -> dict:
    uid = state["user_id"]
    try:
        profile = (await toolbox.get_profile(uid)).model_dump(mode="json")
    except LookupError:
        profile = {}
    history = await toolbox.query_history(uid, list(get_args(Metric)), 14)
    # TODO(PRD): plan aktif tidak punya field di GraphState; coach mengambilnya sendiri.
    form = from_form(state)
    return {
        **TURN_RESET,
        **({"draft_log": form, "intent": "log"} if form else {}),
        "profile": profile,
        "recent_logs": [r.model_dump(mode="json") for r in history.rows],
        "timings": {},
    }


async def red_flag_precheck(state: GraphState) -> dict:
    uid = state["user_id"]
    flags = await toolbox.red_flag_rules(await latest_values(uid), last_user_text(state))
    if flags:
        async with SessionLocal() as session:
            session.add_all(RedFlagEvent(user_id=uid, code=f.code, detail=f.detail) for f in flags)
            await session.commit()
    return {"red_flags": [f.model_dump(mode="json") for f in flags]}


async def emergency_response(state: GraphState) -> dict:
    codes = dict.fromkeys(f["code"] for f in state["red_flags"] if f["code"] in EMERGENCY_CODES)
    text = "\n\n".join(REFERRAL[c] for c in codes)
    return {"final_response": text, "messages": [AIMessage(text)]}
