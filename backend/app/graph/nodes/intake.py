"""supervisor, intake (+ clarify/confirm), nutrition (+ confirm), save_log.

`interrupt` sengaja ada di node terpisah tanpa LLM: node yang di-resume dijalankan ulang dari
awal, jadi panggilan LLM tidak ikut terulang.
"""

import base64
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import DailyLog, FoodEntry, RedFlagEvent
from app.db.session import SessionLocal
from app.graph import llm, prompts, toolbox
from app.graph.nodes.context import is_emergency, last_user_text, latest_values, numbers_in
from app.graph.state import GraphState, Intent
from app.schemas import (
    MEASUREMENT_RANGE,
    ClarifyPayload,
    ConfirmLogPayload,
    ConfirmLogResume,
    ConfirmMealPayload,
    ConfirmMealResume,
    DailyLogIn,
    LatestValues,
    MealEstimate,
    MeasurementIn,
    MeasurementKind,
)
from app.tools.data import today

MENTION = {
    "smoked": r"rokok|smok|cigar|batang|bungkus|vape|vaping|sebat",
    "alcohol": r"alkohol|alcohol|\bbir\b|beer|wine|anggur|booze|miras|tuak|arak|soju|vodka|whisk",
}
_BP = r"tensi|tekanan darah|\btd\b|mmhg|blood pressure|\bbp\b|\d+\s*/\s*\d+"
MEASUREMENT_MENTION = {  # measurement hanya diterima jika jenisnya disebut user
    "weight_kg": r"berat|\bbb\b|\bkg\b|\d\s*kg|timbang|weight",
    "systolic": _BP,
    "diastolic": _BP,
    "resting_hr": r"nadi|denyut|detak|jantung|\bbpm\b|\bhr\b|heart",
    "cholesterol_total": r"kolesterol|cholesterol",
}
REQUIRED = ("steps", "sleep_hours", "water_l", "smoked", "alcohol")  # bagian 6.2 save_log
MAX_CLARIFY = 2
UPLOAD_DIR = Path(__file__).resolve().parents[4] / "data" / "uploads"


class IntentOut(BaseModel):
    intent: Literal["log", "history_question", "health_info", "smalltalk"]


class ExtractedLog(BaseModel):
    steps: int | None = Field(None, ge=0)
    sleep_hours: float | None = Field(None, ge=0, le=24)
    water_l: float | None = Field(None, ge=0, le=20)
    calories_kcal: int | None = Field(None, ge=0)
    smoked: bool | None = None
    alcohol: bool | None = None


class ExtractedMeasurement(BaseModel):
    kind: MeasurementKind
    value: float = Field(ge=0, lt=100_000)


class Extracted(BaseModel):
    log: ExtractedLog
    measurements: list[ExtractedMeasurement] = []


def ground(out: Extracted, text: str) -> tuple[ExtractedLog, list[ExtractedMeasurement]]:
    """Buang hasil ekstraksi yang tidak berdasar teks user (groundedness, bagian 2)."""
    said, lower = numbers_in(text), text.lower()
    measurements = [
        m
        for m in out.measurements
        if m.value in said
        and re.search(MEASUREMENT_MENTION[m.kind], lower)
        and MEASUREMENT_RANGE[m.kind][0] <= m.value <= MEASUREMENT_RANGE[m.kind][1]
    ]
    # LLM cenderung mengisi false untuk hal yang tidak disebut; terima hanya jika topiknya ada.
    log = out.log.model_copy(
        update={f: None for f, p in MENTION.items() if not re.search(p, text.lower())}
    )
    return log, measurements


async def supervisor(state: GraphState) -> dict:
    if state.get("image_b64"):
        return {"intent": "photo"}
    out = await llm.structured(IntentOut, prompts.SUPERVISOR, last_user_text(state))
    if out is None:
        return {"intent": "smalltalk", "final_response": prompts.CLARIFY_FALLBACK}
    intent: Intent = out.intent
    return {"intent": intent}


async def intake(state: GraphState) -> dict:
    draft = state.get("draft_log") or {"log": {}, "measurements": [], "clarify_count": 0}
    out = await llm.structured(
        Extracted,
        prompts.INTAKE,
        llm.compact({"teks": last_user_text(state), "sudah_terisi": draft["log"]}),
    )
    if out is None:
        return {"draft_log": None, "final_response": prompts.INTAKE_FALLBACK}
    now = datetime.now(UTC).isoformat()
    # Groundedness: measurement hanya diterima kalau angkanya tertulis di teks user.
    log, measurements = ground(out, last_user_text(state))
    return {
        "draft_log": {
            **draft,
            "log": {**draft["log"], **log.model_dump(exclude_none=True)},
            "measurements": draft["measurements"]
            + [{**m.model_dump(), "measured_at": now} for m in measurements],
        }
    }


def missing_fields(draft: dict) -> list[str]:
    return [f for f in REQUIRED if draft["log"].get(f) is None]


def route_after_intake(state: GraphState) -> str:
    draft = state.get("draft_log")
    if not draft:
        return "response"
    if missing_fields(draft) and draft["clarify_count"] < MAX_CLARIFY:
        return "intake_clarify"
    return "intake_confirm"


async def intake_clarify(state: GraphState) -> dict:
    draft = state["draft_log"]
    missing = missing_fields(draft)
    answer = interrupt(
        ClarifyPayload(question=prompts.clarify_question(missing), missing=missing).model_dump()
    )
    # Jawaban clarify tidak melewati red_flag_precheck, jadi dicek di sini (bagian 13).
    flags = await toolbox.red_flag_rules(LatestValues(), str(answer))
    await _save_red_flags(state["user_id"], [f.model_dump(mode="json") for f in flags])
    return {
        "draft_log": {**draft, "clarify_count": draft["clarify_count"] + 1},
        "messages": [HumanMessage(str(answer))],
        "red_flags": [*state.get("red_flags", []), *(f.model_dump(mode="json") for f in flags)],
    }


def route_after_clarify(state: GraphState) -> str:
    return "emergency_response" if is_emergency(state.get("red_flags", [])) else "intake"


async def _save_red_flags(user_id: int, flags: list[dict]) -> None:
    if flags:
        async with SessionLocal() as session:
            session.add_all(
                RedFlagEvent(user_id=user_id, code=f["code"], detail=f["detail"]) for f in flags
            )
            await session.commit()


async def intake_confirm(state: GraphState) -> dict:
    draft = state["draft_log"]
    log = DailyLogIn(
        log_date=today(), source=state["channel"], raw_text=last_user_text(state), **draft["log"]
    )
    measurements = [MeasurementIn(**m) for m in draft["measurements"]]
    resume = interrupt(
        ConfirmLogPayload(log=log, measurements=measurements).model_dump(mode="json")
    )
    decision = ConfirmLogResume.model_validate(resume)
    if decision.action == "edit" and decision.log is not None:
        log = decision.log
    return {"draft_log": {**draft, "log": log.model_dump(mode="json"), "confirmed": True}}


async def nutrition(state: GraphState) -> dict:
    try:
        est = await toolbox.estimate_meal_from_image(
            state["image_b64"] or "", last_user_text(state) or None
        )
    except Exception:
        return {"meal_estimate": None, "final_response": prompts.MEAL_FALLBACK}
    return {"meal_estimate": est.model_dump(mode="json")}


def route_after_nutrition(state: GraphState) -> str:
    return "nutrition_confirm" if state.get("meal_estimate") else "response"


async def nutrition_confirm(state: GraphState) -> dict:
    est = MealEstimate.model_validate(state["meal_estimate"])
    resume = interrupt(ConfirmMealPayload(estimate=est).model_dump(mode="json"))
    decision = ConfirmMealResume.model_validate(resume)
    if decision.action == "cancel":
        return {"meal_estimate": None, "final_response": "Baik, makanan tidak disimpan."}
    if decision.action == "edit" and decision.items:
        est = est.model_copy(update={"items": decision.items})
    return {"meal_estimate": {**est.model_dump(mode="json"), "confirmed": True}}


def route_after_confirm(state: GraphState) -> str:
    confirmed = (state.get("draft_log") or {}).get("confirmed") or (
        state.get("meal_estimate") or {}
    ).get("confirmed")
    return "save_log" if confirmed else "response"


def _save_image(image_b64: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{secrets.token_hex(16)}.jpg"  # nama acak (bagian 13)
    path.write_bytes(base64.b64decode(image_b64))
    return str(path)


async def save_log(state: GraphState) -> dict:
    uid, source, day = state["user_id"], state["channel"], today()
    draft, meal = state.get("draft_log") or {}, state.get("meal_estimate") or {}
    saved = None
    if draft.get("confirmed"):
        saved = await toolbox.save_daily_log(uid, DailyLogIn.model_validate(draft["log"]))
        for m in draft["measurements"]:
            await toolbox.save_measurement(uid, MeasurementIn.model_validate(m))
    if meal.get("confirmed"):
        est = MealEstimate.model_validate(meal)
        kcal = round(sum((i.kcal_low + i.kcal_high) / 2 for i in est.items))
        async with SessionLocal() as session:
            session.add(
                FoodEntry(
                    user_id=uid,
                    log_date=day,
                    items=[i.model_dump() for i in est.items],
                    kcal_estimate=kcal,
                    confirmed=True,
                    image_path=_save_image(state["image_b64"]) if state.get("image_b64") else None,
                )
            )
            existing = await session.scalar(
                select(DailyLog.calories_kcal).where(
                    DailyLog.user_id == uid, DailyLog.log_date == day
                )
            )
            await session.commit()
        saved = await toolbox.save_daily_log(
            uid, DailyLogIn(log_date=day, source=source, calories_kcal=(existing or 0) + kcal)
        )
    complete = saved is not None and all(getattr(saved, f) is not None for f in REQUIRED)
    # Cek ulang setelah ekstraksi LLM: tensi/nadi yang baru disimpan bisa memicu red flag.
    known = {f["code"] for f in state.get("red_flags", [])}
    new = [
        f.model_dump(mode="json")
        for f in await toolbox.red_flag_rules(await latest_values(uid), "")
        if f.code not in known
    ]
    await _save_red_flags(uid, new)
    return {"log_complete": complete, "red_flags": [*state.get("red_flags", []), *new]}
