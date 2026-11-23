"""history_qa, knowledge_info, response."""

import asyncio
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from app.graph import llm, prompts, toolbox
from app.graph.nodes.context import last_user_text
from app.graph.state import GraphState
from app.safety.templates import DIABETES_CAVEAT, DISCLAIMER, FRAMINGHAM_CAVEAT, REFERRAL
from app.schemas import Metric, PlanContent, PlanIn, TrendReport
from app.settings import settings
from app.tools.data import today

MAX_TOOL_CALLS = 4
HISTORY_WINDOW = 12  # bagian 14: hanya pesan terakhir yang dikirim ke LLM


def _history_tools(user_id: int, passages: list[dict]) -> list[StructuredTool]:
    """4 tool ★ (bagian 7) dengan user_id terikat; LLM tidak bisa memilih user lain."""

    async def query_history(metrics: list[Metric], days: int = 7) -> dict:
        """Tabel histori harian user untuk metrik terpilih, days 1..90."""
        return (await toolbox.query_history(user_id, metrics, days)).model_dump(mode="json")

    async def compute_trends(days: int = 7) -> dict:
        """Tren per metrik: mean, min, max, delta vs periode sebelumnya, slope, kepatuhan."""
        report = (await toolbox.compute_trends(user_id, days)).model_dump(mode="json")
        return {
            m: {k: v for k, v in t.items() if k != "series"} for m, t in report["metrics"].items()
        }

    async def retrieve_guidelines(query: str) -> list[dict]:
        """Cari passage pedoman kesehatan di korpus."""
        found = [p.model_dump(mode="json") for p in await toolbox.retrieve_guidelines(query)]
        passages.extend(found)
        return [{k: p[k] for k in ("source_id", "title", "text")} for p in found]

    async def get_active_plan() -> dict | None:
        """Rencana aktif user beserta target mingguannya."""
        plan = await toolbox.get_active_plan(user_id)
        return plan.content.model_dump() if plan else None

    return [
        StructuredTool.from_function(coroutine=f)
        for f in (query_history, compute_trends, retrieve_guidelines, get_active_plan)
    ]


async def history_qa(state: GraphState) -> dict:
    uid = state["user_id"]
    passages: list[dict] = []
    tools = {t.name: t for t in _history_tools(uid, passages)}
    messages: list[Any] = [SystemMessage(prompts.HISTORY_QA), HumanMessage(last_user_text(state))]
    calls = 0
    try:
        model = llm.chat(reasoning=llm.THINKING).bind_tools(list(tools.values()))
        async with asyncio.timeout(llm.NODE_TIMEOUT_S):
            while True:
                ai = await model.ainvoke(messages)
                messages.append(ai)
                if not ai.tool_calls:
                    break
                for tc in ai.tool_calls:
                    if calls >= MAX_TOOL_CALLS:
                        content = "batas panggilan tool tercapai, jawab dengan data yang ada"
                    else:
                        content = llm.compact(await tools[tc["name"]].ainvoke(tc["args"]))
                        calls += 1
                    messages.append(ToolMessage(content, tool_call_id=tc["id"]))
                if calls >= MAX_TOOL_CALLS:
                    ai = await llm.chat(reasoning=llm.THINKING).ainvoke(messages)
                    break
        answer = str(ai.content).strip()
        if not answer:
            raise ValueError("jawaban kosong")
    except Exception:
        trends = await toolbox.compute_trends(uid, 7)
        answer = "Ringkasan 7 hari terakhir:\n" + _trend_lines(trends)
    return {"final_response": answer, "passages": passages}


class KnowledgeAnswer(BaseModel):
    answer: str
    citations: list[str] = []
    found: bool


async def knowledge_info(state: GraphState) -> dict:
    question = last_user_text(state)
    passages = await toolbox.retrieve_guidelines(question, k=5)
    if not passages:  # retrieve sudah membuang kandidat dengan kemiripan rendah
        return {"final_response": prompts.NOT_IN_CORPUS, "passages": []}
    out = await llm.structured(
        KnowledgeAnswer,
        prompts.KNOWLEDGE_INFO,
        llm.compact(
            {
                "pertanyaan": question,
                "passages": [
                    p.model_dump(include={"source_id", "title", "text"}) for p in passages
                ],
            }
        ),
    )
    cited = {c for c in (out.citations if out else [])} & {p.source_id for p in passages}
    if out is None or not out.found or not cited:
        return {"final_response": prompts.NOT_IN_CORPUS, "passages": []}
    return {
        "final_response": out.answer,
        "passages": [p.model_dump(mode="json") for p in passages if p.source_id in cited],
    }


def _trend_lines(trends: TrendReport) -> str:
    lines = []
    for metric, t in trends.metrics.items():
        if t.mean is None:
            continue
        line = f"- {metric}: rata-rata {t.mean:g} (min {t.min:g}, maks {t.max:g}, n={t.n_obs})"
        if t.delta is not None:
            line += f", perubahan {t.delta:+g} vs periode sebelumnya"
        lines.append(line)
    return "\n".join(lines) or "- belum ada data"


def _chip(source_id: str, passages: list[dict], channel: str) -> str:
    url = next((p["url"] for p in passages if p["source_id"] == source_id), None)
    return f"[{source_id}]({url})" if channel == "web" and url else f"[{source_id}]"


def render_assessment(state: GraphState) -> str:
    """Render deterministik (tanpa LLM) supaya semua angka sama persis dengan assessment."""
    ch, passages = state["channel"], state.get("passages", [])
    trends = state.get("trends", {})
    out = ["Ringkasan risiko", trends.get("interpretation", "")]
    for f in state.get("flags", []):
        stale = " (data lama)" if f.get("stale") else ""
        out.append(f"- {f['code']}: {f['value']} (acuan {f['threshold']}){stale}")
    fr = state.get("framingham") or {}
    if fr.get("applicable"):
        out.append(
            f"Risiko kardiovaskular 10 tahun (Framingham non-lab): {fr['risk_10y_pct']}%. "
            + FRAMINGHAM_CAVEAT
        )
    elif fr:
        out.append(f"Skor Framingham: tidak berlaku ({fr.get('reason')}).")
    dm = state.get("diabetes") or {}
    if dm:
        factors = ", ".join(f["feature"] for f in dm.get("top_factors", []))
        out.append(
            f"Indikasi risiko diabetes: {dm['band']} ({dm['prob'] * 100:.0f}%). "
            f"Faktor utama: {factors}. {DIABETES_CAVEAT}"
        )

    critique = state.get("critique") or {}
    if state.get("needs_clinician") and not critique.get("fallback"):
        out.append("Rencana Anda sedang ditinjau tenaga medis. Kami kabari setelah selesai.")
    elif state.get("plan_draft"):
        plan = PlanContent.model_validate(state["plan_draft"])
        out.append("Saran umum" if critique.get("fallback") else "Rencana 4 minggu")
        for w in plan.weeks:
            targets = ", ".join(f"{t.metric} {t.target:g}" for t in w.targets)
            out.append(f"{w.range}" + (f" (target: {targets})" if targets else ""))
            out += [
                f"- {a.text} " + " ".join(_chip(c, passages, ch) for c in a.citations)
                for a in w.actions
            ]
    return "\n".join(line for line in out if line)


async def response(state: GraphState) -> dict:
    ch = state["channel"]
    parts = [REFERRAL[f["code"]] for f in state.get("red_flags", []) if f["code"] in REFERRAL]
    text = state.get("final_response")
    intent = state.get("intent")
    if text is None and intent == "smalltalk":
        recent = state.get("messages", [])[-HISTORY_WINDOW:]
        try:
            async with asyncio.timeout(llm.NODE_TIMEOUT_S):
                reply = await llm.chat(reasoning=False).ainvoke(
                    [SystemMessage(prompts.SMALLTALK), *recent]
                )
            text = str(reply.content).strip() or prompts.CLARIFY_FALLBACK
        except Exception:
            text = prompts.CLARIFY_FALLBACK
    elif text is None and state.get("trends"):
        text = render_assessment(state)
    elif text is None:
        text = "Catatan tersimpan."
        draft = state.get("draft_log") or {}
        if missing := [
            prompts.FIELD_LABELS[f]
            for f in prompts.FIELD_LABELS
            if draft.get("log", {}).get(f) is None
        ]:
            text += " Belum lengkap: " + ", ".join(missing) + "."
    parts.append(text)

    if intent in ("history_question", "health_info") and state.get("passages"):
        ids = dict.fromkeys(p["source_id"] for p in state["passages"])
        parts.append("Sumber: " + " ".join(_chip(i, state["passages"], ch) for i in ids))
    if intent != "smalltalk":
        parts.append(DISCLAIMER)
    if ch == "telegram" and state.get("trends"):
        parts.append(f"Detail lengkap: {settings.APP_BASE_URL}/dashboard")

    critique = state.get("critique") or {}
    if (
        state.get("plan_draft")
        and critique.get("pass")
        and not critique.get("fallback")
        and not state.get("needs_clinician")
    ):
        await toolbox.save_plan(
            state["user_id"],
            PlanIn(
                status="active",
                content=PlanContent.model_validate(state["plan_draft"]),
                starts_on=today(),
            ),
        )
    chart = None
    if state.get("trends"):
        chart = await toolbox.build_chart_payload(TrendReport.model_validate(state["trends"]))
        chart = chart.model_dump(mode="json")
    final = "\n\n".join(parts)
    return {"final_response": final, "chart_payload": chart, "messages": [AIMessage(final)]}
