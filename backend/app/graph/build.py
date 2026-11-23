"""Graph utama (bagian 6), subgraph review clinician, dan runner untuk channel web/Telegram."""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypedDict

from langchain_core.callbacks import AsyncCallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from sqlalchemy import update

from app.db.models import AgentRun, ClinicianReview
from app.db.models import Plan as PlanRow
from app.db.session import SessionLocal
from app.graph.nodes import answer, assess, context, intake
from app.graph.state import GraphState
from app.schemas import Assessment, ClinicianDecision, ClinicianReviewPayload, Plan

TOTAL_TIMEOUT_S = 240  # bagian 14: total check-in 4 menit

Node = Callable[[Any], Awaitable[dict]]


def timed(name: str, fn: Node) -> Node:
    """Catat durasi node ke `timings` (ms) untuk agent_runs."""

    async def wrapper(state: GraphState) -> dict:
        start = time.perf_counter()
        result = await fn(state)
        base = result.get("timings", state.get("timings") or {})
        return {**result, "timings": {**base, name: round((time.perf_counter() - start) * 1000)}}

    return wrapper


# --- subgraph review (thread review-{plan_id}) --------------------------------


class ReviewState(TypedDict, total=False):
    review_id: int
    plan_id: int
    user_id: int
    assessment: dict
    decision: dict


async def await_review(state: ReviewState) -> dict:
    async with SessionLocal() as session:
        row = await session.get(PlanRow, state["plan_id"])
        plan = Plan.model_validate(row, from_attributes=True)
    payload = ClinicianReviewPayload(
        review_id=state["review_id"],
        plan=plan,
        assessment=Assessment.model_validate(state["assessment"]),
    )
    decision = ClinicianDecision.model_validate(interrupt(payload.model_dump(mode="json")))
    return {"decision": decision.model_dump(mode="json")}


async def apply_review(state: ReviewState) -> dict:
    d = ClinicianDecision.model_validate(state["decision"])
    async with SessionLocal() as session:
        if d.decision == "reject":
            await session.execute(
                update(PlanRow).where(PlanRow.id == state["plan_id"]).values(status="rejected")
            )
        else:
            await session.execute(
                update(PlanRow)
                .where(PlanRow.user_id == state["user_id"], PlanRow.status == "active")
                .values(status="superseded")
            )
            values: dict[str, Any] = {"status": "active"}
            if d.decision == "edit" and d.edited_content:
                values["content"] = d.edited_content.model_dump(mode="json")
            await session.execute(
                update(PlanRow).where(PlanRow.id == state["plan_id"]).values(**values)
            )
        await session.execute(
            update(ClinicianReview)
            .where(ClinicianReview.id == state["review_id"])
            .values(
                decision=d.decision,
                note=d.note,
                decided_at=datetime.now(UTC),
                edited_content=d.edited_content.model_dump(mode="json")
                if d.edited_content
                else None,
            )
        )
        await session.commit()
    # TODO(PRD): notifikasi user (web + Telegram) setelah keputusan: M6/M7.
    return {}


def build_review_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    g = StateGraph(ReviewState)
    g.add_node("await_review", await_review)
    g.add_node("apply_review", apply_review)
    g.add_edge(START, "await_review")
    g.add_edge("await_review", "apply_review")
    g.add_edge("apply_review", END)
    return g.compile(checkpointer=checkpointer)


# --- graph utama ---------------------------------------------------------------


def route_after_precheck(s: GraphState) -> str:
    if context.is_emergency(s["red_flags"]):
        return "emergency_response"
    # Form check-in sudah terstruktur dan dikonfirmasi user: tanpa supervisor/intake (tanpa LLM).
    return "save_log" if context.from_form(s) else "supervisor"


def route_intent(s: GraphState) -> str:
    if s.get("final_response"):  # supervisor fallback
        return "response"
    return {
        "log": "intake",
        "photo": "nutrition",
        "history_question": "history_qa",
        "health_info": "knowledge_info",
        "smalltalk": "response",
    }[s["intent"]]


def route_after_save(s: GraphState) -> str:
    return "risk_analyst" if s["log_complete"] else "response"


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    review_graph = build_review_graph(checkpointer)
    nodes: dict[str, Node] = {
        "load_context": context.load_context,
        "red_flag_precheck": context.red_flag_precheck,
        "emergency_response": context.emergency_response,
        "supervisor": intake.supervisor,
        "intake": intake.intake,
        "intake_clarify": intake.intake_clarify,
        "intake_confirm": intake.intake_confirm,
        "nutrition": intake.nutrition,
        "nutrition_confirm": intake.nutrition_confirm,
        "save_log": intake.save_log,
        "risk_analyst": assess.risk_analyst,
        "knowledge": assess.knowledge,
        "coach": assess.coach,
        "safety_critic": assess.safety_critic,
        "safe_fallback": assess.safe_fallback,
        "create_review": assess.make_create_review(review_graph),
        "history_qa": answer.history_qa,
        "knowledge_info": answer.knowledge_info,
        "response": answer.response,
    }
    g = StateGraph(GraphState)
    for name, fn in nodes.items():
        g.add_node(name, timed(name, fn))
    g.add_edge(START, "load_context")
    g.add_edge("load_context", "red_flag_precheck")
    g.add_conditional_edges("red_flag_precheck", route_after_precheck)
    g.add_edge("emergency_response", END)
    g.add_conditional_edges("supervisor", route_intent)
    g.add_conditional_edges("intake", intake.route_after_intake)
    g.add_conditional_edges("intake_clarify", intake.route_after_clarify)
    g.add_conditional_edges("intake_confirm", intake.route_after_confirm)
    g.add_conditional_edges("nutrition", intake.route_after_nutrition)
    g.add_conditional_edges("nutrition_confirm", intake.route_after_confirm)
    g.add_conditional_edges("save_log", route_after_save)
    g.add_conditional_edges("risk_analyst", assess.route_after_risk)
    g.add_edge("knowledge", "coach")
    g.add_edge("coach", "safety_critic")
    g.add_conditional_edges("safety_critic", assess.route_after_critic)
    g.add_edge("safe_fallback", "response")
    g.add_edge("create_review", "response")
    g.add_edge("history_qa", "response")
    g.add_edge("knowledge_info", "response")
    g.add_edge("response", END)
    graph = g.compile(checkpointer=checkpointer)
    graph.review_graph = review_graph  # type: ignore[attr-defined]  # dipakai endpoint clinician
    return graph


# --- runner ----------------------------------------------------------------------


class _LLMCounter(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.calls = 0

    async def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
        self.calls += 1


def thread_config(user_id: int) -> dict:
    return {"configurable": {"thread_id": f"user-{user_id}"}}


async def stream_turn(
    graph: CompiledStateGraph, graph_input: Any, user_id: int, channel: str
) -> AsyncIterator[dict]:
    """Jalankan satu giliran dan hasilkan event SSE bagian 10:
    node_start, token, interrupt, chart, final, error. Mencatat agent_runs di akhir."""
    counter = _LLMCounter()
    config = {**thread_config(user_id), "callbacks": [counter]}
    start = time.perf_counter()
    interrupted = False
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT_S):
            async for mode, chunk in graph.astream(
                graph_input, config, stream_mode=["tasks", "messages", "updates"]
            ):
                if mode == "tasks" and "input" in chunk:
                    yield {"event": "node_start", "data": {"node": chunk["name"]}}
                elif mode == "messages":
                    msg, meta = chunk
                    if meta.get("langgraph_node") == "response" and msg.content:
                        yield {"event": "token", "data": {"text": msg.content}}
                elif mode == "updates" and "__interrupt__" in chunk:
                    interrupted = True
                    for i in chunk["__interrupt__"]:
                        yield {"event": "interrupt", "data": i.value}
        state = (await graph.aget_state(thread_config(user_id))).values
        if not interrupted:
            if state.get("chart_payload"):
                yield {"event": "chart", "data": state["chart_payload"]}
            yield {"event": "final", "data": {"text": state.get("final_response") or ""}}
    except TimeoutError:
        state = (await graph.aget_state(thread_config(user_id))).values
        flags = ", ".join(f["code"] for f in state.get("flags", [])) or "tidak ada"
        yield {
            "event": "final",
            "data": {
                "text": f"Analisis melewati batas waktu. Data Anda sudah tersimpan. Flags: {flags}."
            },
        }
    except Exception as e:
        state = {}
        yield {"event": "error", "data": {"message": type(e).__name__}}
    async with SessionLocal() as session:
        session.add(
            AgentRun(
                thread_id=f"user-{user_id}",
                user_id=user_id,
                channel=channel,
                intent=state.get("intent"),
                node_timings=state.get("timings"),
                llm_calls=counter.calls,
                total_ms=round((time.perf_counter() - start) * 1000),
            )
        )
        await session.commit()
