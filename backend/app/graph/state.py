# app/graph/state.py
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

Intent = Literal["log", "photo", "history_question", "health_info", "smalltalk"]


class GraphState(TypedDict, total=False):
    # input
    user_id: int
    channel: Literal["web", "telegram"]
    messages: Annotated[list, add_messages]
    image_b64: str | None
    # context (load_context)
    profile: dict
    recent_logs: list[dict]  # 14 hari terakhir
    # routing
    red_flags: list[dict]
    intent: Intent
    # intake / nutrition
    draft_log: dict | None
    meal_estimate: dict | None
    log_complete: bool
    # assessment
    flags: list[dict]
    framingham: dict
    diabetes: dict
    trends: dict
    passages: list[dict]
    plan_draft: dict | None
    critique: dict | None
    revision_count: int
    needs_clinician: bool
    # output
    final_response: str
    chart_payload: dict | None
    timings: dict[str, int]  # ms per node → agent_runs
