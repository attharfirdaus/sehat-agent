import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sse_starlette import EventSourceResponse

from app.api.auth import CurrentUser
from app.graph.build import stream_turn, thread_config
from app.schemas import (
    ChatHistory,
    ChatMessage,
    CheckinIn,
    ClarifyResume,
    ConfirmLogResume,
    ConfirmMealResume,
)
from app.tools.data import today

router = APIRouter()

RESUME_TYPES: dict[str, TypeAdapter[Any]] = {
    "clarify": TypeAdapter(ClarifyResume),
    "confirm_log": TypeAdapter(ConfirmLogResume),
    "confirm_meal": TypeAdapter(ConfirmMealResume),
}


class ChatIn(BaseModel):
    message: str = Field("", max_length=4000)
    image_b64: str | None = Field(None, max_length=15_000_000)


class ResumeIn(BaseModel):
    value: Any


async def _sse(events: AsyncIterator[dict]) -> AsyncIterator[dict]:
    async for e in events:
        yield {"event": e["event"], "data": json.dumps(e["data"], ensure_ascii=False)}


async def _pending(graph: CompiledStateGraph, user_id: int) -> dict | None:
    snap = await graph.aget_state(thread_config(user_id))
    return snap.interrupts[0].value if snap.interrupts else None


@router.post("/chat")
async def chat(body: ChatIn, user: CurrentUser, request: Request) -> EventSourceResponse:
    if not body.message.strip() and not body.image_b64:
        raise HTTPException(422, "message atau image_b64 wajib diisi")
    graph = request.app.state.graph
    pending = await _pending(graph, user.id)
    if pending and pending["type"] == "clarify" and body.message.strip():
        graph_input: Any = Command(resume=body.message)
    else:  # interrupt lain ditinggalkan: pesan baru memulai giliran baru
        graph_input = {
            "user_id": user.id,
            "channel": "web",
            "image_b64": body.image_b64,
            "draft_log": None,  # jangan membawa draft form giliran lalu
            "messages": [HumanMessage(body.message)],
        }
    return EventSourceResponse(_sse(stream_turn(graph, graph_input, user.id, "web")))


@router.post("/chat/resume")
async def resume(body: ResumeIn, user: CurrentUser, request: Request) -> EventSourceResponse:
    graph = request.app.state.graph
    pending = await _pending(graph, user.id)
    if pending is None or pending["type"] not in RESUME_TYPES:
        raise HTTPException(409, "tidak ada interrupt yang menunggu jawaban")
    try:
        value = RESUME_TYPES[pending["type"]].validate_python(body.value)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from None
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return EventSourceResponse(_sse(stream_turn(graph, Command(resume=value), user.id, "web")))


@router.get("/chat/history")
async def history(user: CurrentUser, request: Request) -> ChatHistory:
    """Pesan di checkpoint thread user + interrupt yang menunggu (untuk reload halaman)."""
    snap = await request.app.state.graph.aget_state(thread_config(user.id))
    messages = [
        ChatMessage(
            role="user" if isinstance(m, HumanMessage) else "assistant", text=str(m.content)
        )
        for m in snap.values.get("messages", [])
        if isinstance(m, HumanMessage | AIMessage) and m.content
    ]
    return ChatHistory(
        messages=messages, pending=snap.interrupts[0].value if snap.interrupts else None
    )


KIND_LABEL = {
    "weight_kg": "berat",
    "systolic": "sistolik",
    "diastolic": "diastolik",
    "resting_hr": "nadi istirahat",
    "cholesterol_total": "kolesterol total",
}


def _summary(body: CheckinIn) -> str:
    parts = [
        f"langkah {body.steps}",
        f"tidur {body.sleep_hours:g} jam",
        f"air {body.water_l:g} liter",
        "merokok" if body.smoked else "tidak merokok",
        "minum alkohol" if body.alcohol else "tidak minum alkohol",
    ]
    if body.calories_kcal is not None:
        parts.append(f"kalori {body.calories_kcal} kkal")
    parts += [f"{KIND_LABEL[m.kind]} {m.value:g}" for m in body.measurements]
    return "Check-in lewat form: " + ", ".join(parts)


@router.post("/checkin")
async def checkin(body: CheckinIn, user: CurrentUser, request: Request) -> EventSourceResponse:
    """Form check-in harian: langsung disimpan lalu dinilai (tanpa LLM untuk ekstraksi).
    Memakai thread yang sama dengan chat, jadi hasilnya ikut di riwayat chat."""
    text = _summary(body)
    now = datetime.now(UTC).isoformat()
    draft = {
        "log": {
            **body.model_dump(
                include={"steps", "sleep_hours", "water_l", "smoked", "alcohol", "calories_kcal"}
            ),
            "log_date": today().isoformat(),
            "source": "form",
            "raw_text": text,
        },
        "measurements": [{**m.model_dump(), "measured_at": now} for m in body.measurements],
        "clarify_count": 0,
        "confirmed": True,
        "from_form": True,
    }
    graph_input = {
        "user_id": user.id,
        "channel": "web",
        "image_b64": None,
        "draft_log": draft,
        "messages": [HumanMessage(text)],
    }
    return EventSourceResponse(
        _sse(stream_turn(request.app.state.graph, graph_input, user.id, "web"))
    )
