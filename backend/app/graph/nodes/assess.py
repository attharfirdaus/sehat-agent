"""risk_analyst, knowledge, coach, safety_critic, safe_fallback, create_review."""

import json
import re
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from sqlalchemy import insert

from app.db.models import Assessment as AssessmentRow
from app.db.models import ClinicianReview
from app.db.session import SessionLocal
from app.graph import llm, prompts, toolbox
from app.graph.nodes.context import (
    last_user_text,
    latest_values,
    number_readings,
    number_tokens,
    numbers_in,
)
from app.graph.state import GraphState
from app.schemas import (
    Flag,
    Passage,
    PlanAction,
    PlanContent,
    PlanIn,
    PlanWeek,
    Profile,
)
from app.tools.data import today

MAX_PASSAGES = 8
_FOREIGN_SCRIPT = re.compile(r"[\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u4E00-\u9FFF]")


class Interpretation(BaseModel):
    summary: str = Field(max_length=1200)


class Queries(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3)


class Rubric(BaseModel):
    no_diagnosis_or_medication: bool
    risk_calibrated: bool
    issues: list[str] = []


def _flags_summary(flags: list[dict]) -> str:
    if not flags:
        return "Dari data saat ini, tidak ada hal yang perlu dikhawatirkan."
    return (
        "Yang perlu diperhatikan: "
        + ", ".join(prompts.flag_label(f["code"]).lower() for f in flags)
        + "."
    )


# Topik tiap flag dan kata yang berarti "baik-baik saja". Ringkasan LLM yang memakai kata itu untuk
# topik yang ditandai bermasalah dianggap bertentangan dengan data dan diganti ringkasan template.
_FLAG_TOPIC = {
    "BP": r"tensi|tekanan darah",
    "BMI": r"berat badan|bmi",
    "SLEEP": r"tidur",
    "CHOL": r"kolesterol",
    "RHR": r"denyut|nadi",
    "STEPS": r"langkah",
    "PA": r"olahraga|aktivitas fisik",
    "SMOKING": r"rokok|merokok",
}
_REASSURING = re.compile(r"\b(ideal|normal|sehat|aman|baik|cukup|tidak bermasalah)\b")
# "di atas normal", "belum ideal", "batas normal" dsb. bukan klaim bahwa kondisinya baik.
_NOT_REASSURING = re.compile(
    r"\b(di atas|di bawah|melebihi|lebih dari|kurang dari|belum|tidak|kurang|batas|mendekati|"
    r"menuju|agar|supaya|untuk|menjadi|kembali|lebih|usahakan|coba|perlu|harus|sebaiknya|"
    r"pastikan|jaga|menjaga)\s+(\w+\s+)?$"
)


def contradicts_flags(summary: str, flags: list[dict]) -> bool:
    """True kalau ringkasan menyebut topik yang ditandai sebagai ideal/normal/sehat."""
    topics = {t for f in flags for t in _FLAG_TOPIC if f["code"].startswith(t)}
    for sentence in re.split(r"[.!?;]", summary.lower()):
        for clause in re.split(r",|\bnamun\b|\btetapi\b|\bsedangkan\b|\bdan\b", sentence):
            if not any(re.search(_FLAG_TOPIC[t], clause) for t in topics):
                continue
            for m in _REASSURING.finditer(clause):
                if not _NOT_REASSURING.search(clause[: m.start()]):
                    return True
    return False


def plain_assessment(assessment: dict) -> dict:
    """Versi berlabel bahasa awam untuk prompt LLM (tanpa kode flag atau nama fitur model)."""
    trends = assessment["trends"].get("metrics", {})
    return {
        "hal_yang_perlu_diperhatikan": [
            {
                "label": prompts.flag_label(f["code"]),
                "keterangan": prompts.flag_line(f).split(": ", 1)[-1],
            }
            for f in assessment["flags"]
        ],
        "jantung": prompts.heart_text(assessment["framingham"]),
        "diabetes": prompts.diabetes_text(assessment["diabetes"]),
        "rata_rata_7_hari": {
            prompts.TARGET_TEXT.get(m, (m, ""))[0]: prompts.num(round(t["mean"], 1))
            for m, t in trends.items()
            if t.get("mean") is not None
        },
    }


async def risk_analyst(state: GraphState) -> dict:
    uid = state["user_id"]
    if not state.get("profile"):
        return {"final_response": prompts.PROFILE_MISSING}
    profile = Profile.model_validate(state["profile"])
    latest = await latest_values(uid)
    flags = await toolbox.guideline_flags(profile, latest)
    features = await toolbox.diabetes_features(uid, profile, latest)
    if features is None:  # BMI wajib untuk Framingham dan model diabetes
        return {"final_response": prompts.WEIGHT_MISSING}
    framingham = await toolbox.framingham_nonlab(profile, latest)
    diabetes = await toolbox.predict_diabetes(features)
    trends = await toolbox.compute_trends(uid, 7)
    assessment = {
        "flags": [f.model_dump(mode="json") for f in flags],
        "framingham": framingham.model_dump(mode="json"),
        "diabetes": diabetes.model_dump(mode="json"),
        "trends": trends.model_dump(mode="json"),
    }
    interp = await llm.structured(
        Interpretation,
        prompts.RISK_ANALYST,
        llm.compact(plain_assessment(assessment)),
        reasoning=llm.THINKING,
    )
    async with SessionLocal() as session:
        await session.execute(
            insert(AssessmentRow).values(user_id=uid, thread_id=f"user-{uid}", **assessment)
        )
        await session.commit()
    # TODO(PRD): GraphState tidak punya field interpretasi; disimpan di trends["interpretation"].
    summary = interp.summary if interp else None
    if summary is None or contradicts_flags(summary, assessment["flags"]):
        summary = _flags_summary(assessment["flags"])
    assessment["trends"]["interpretation"] = summary
    return assessment


def route_after_risk(state: GraphState) -> str:
    return "response" if state.get("final_response") else "knowledge"


def _trend_digest(trends: dict) -> dict:
    """Tren tanpa seri harian, supaya prompt ringkas."""
    return {
        m: {k: v for k, v in t.items() if k != "series"}
        for m, t in trends.get("metrics", {}).items()
    }


async def knowledge(state: GraphState) -> dict:
    flags = [Flag.model_validate(f) for f in state.get("flags", [])]
    out = await llm.structured(
        Queries,
        prompts.KNOWLEDGE,
        llm.compact(
            {
                "flags": [f.model_dump(include={"code", "metric"}) for f in flags],
                "pesan": last_user_text(state),
            }
        ),
    )
    queries = out.queries if out else [f"{f.metric} lifestyle recommendation" for f in flags]
    seen: dict[tuple[str, int], Passage] = {}
    for q in queries or ["healthy lifestyle physical activity diet"]:
        for p in await toolbox.retrieve_guidelines(q, k=5):
            seen.setdefault((p.source_id, p.chunk_id), p)
    passages = sorted(seen.values(), key=lambda p: p.score, reverse=True)[:MAX_PASSAGES]
    return {"passages": [p.model_dump(mode="json") for p in passages]}


def _age(profile: dict) -> int | None:
    if not profile.get("birth_date"):
        return None
    born = Profile.model_validate(profile).birth_date
    t = today()
    return t.year - born.year - ((t.month, t.day) < (born.month, born.day))


async def coach(state: GraphState) -> dict:
    previous = await toolbox.get_active_plan(state["user_id"])
    profile = state.get("profile", {})
    payload = {
        "profil": {"usia": _age(profile), "sex": profile.get("sex")},
        "flags": state.get("flags", []),
        "framingham": state.get("framingham"),
        "diabetes": state.get("diabetes"),
        "tren_7_hari": _trend_digest(state.get("trends", {})),
        "interpretasi": state.get("trends", {}).get("interpretation"),
        "passages": [
            {"source_id": p["source_id"], "title": p["title"], "text": p["text"][:600]}
            for p in state.get("passages", [])
        ],
        "source_id_valid": sorted({p["source_id"] for p in state.get("passages", [])}),
        "previous_plan": previous.content.model_dump() if previous else None,
        "critique": state.get("critique"),
    }
    out = await llm.structured(
        PlanContent, prompts.COACH, llm.compact(payload), reasoning=llm.THINKING
    )
    return {"plan_draft": out.model_dump(mode="json") if out else None}


def deterministic_issues(state: GraphState, plan: PlanContent) -> list[str]:
    """Cek kode bagian 13: (1) angka cocok dengan data, (2) sitasi valid; plus 4 minggu (US-05)
    dan tidak ada aksara asing (qwen kadang menyisipkan kata Rusia/Cina)."""
    sources = {p["source_id"] for p in state.get("passages", [])}
    data = json.dumps(
        [
            state.get(k)
            for k in ("profile", "recent_logs", "flags", "framingham", "diabetes", "trends")
        ]
        + [p["text"] for p in state.get("passages", [])],
        default=str,
    )
    allowed = numbers_in(data) | {t.target for w in plan.weeks for t in w.targets}
    allowed |= {n for w in plan.weeks for n in numbers_in(w.range)}
    issues = [] if len(plan.weeks) == 4 else [f"rencana harus 4 minggu, bukan {len(plan.weeks)}"]
    for w in plan.weeks:
        for a in w.actions:
            if _FOREIGN_SCRIPT.search(a.text):
                issues.append(f"teks bukan bahasa Indonesia: {a.text!r}")
            if not a.citations:
                issues.append(f"aksi tanpa sitasi: {a.text!r}")
            elif bad := set(a.citations) - sources:
                issues.append(f"sitasi tidak ada di hasil retrieval {sorted(bad)}: {a.text!r}")
            if extra := [t for t in number_tokens(a.text) if not number_readings(t) & allowed]:
                issues.append(f"angka tanpa dasar data {extra}: {a.text!r}")
    return issues


async def safety_critic(state: GraphState) -> dict:
    red_codes = {f["code"] for f in state.get("red_flags", [])}
    needs_clinician = (
        any(f["severity"] == "urgent" for f in state.get("flags", []))
        or state.get("diabetes", {}).get("band") == "high"
        or "RF-BP-CRISIS" in red_codes
    )
    revision = state.get("revision_count", 0)
    if not state.get("plan_draft"):
        issues = ["coach tidak menghasilkan rencana"]
    else:
        plan = PlanContent.model_validate(state["plan_draft"])
        # Gagal cek kode -> revisi tanpa LLM critic (bagian 13).
        issues = deterministic_issues(state, plan)
        if not issues:
            rubric = await llm.structured(
                Rubric,
                prompts.CRITIC,
                llm.compact(
                    {
                        "plan": state["plan_draft"],
                        "flags": state.get("flags"),
                        "framingham": state.get("framingham"),
                        "diabetes": state.get("diabetes"),
                    }
                ),
                reasoning=llm.THINKING,
            )
            if rubric is None:  # critic gagal -> langsung safe_fallback
                return {
                    "critique": {"pass": False, "issues": ["critic gagal"]},
                    "needs_clinician": needs_clinician,
                    "revision_count": 2,
                }
            if not (rubric.no_diagnosis_or_medication and rubric.risk_calibrated):
                issues = rubric.issues or ["melanggar rubric"]
    passed = not issues
    return {
        "critique": {"pass": passed, "issues": issues},
        "needs_clinician": needs_clinician,
        "revision_count": revision if passed else revision + 1,
    }


def route_after_critic(state: GraphState) -> str:
    if state["critique"]["pass"]:
        return "create_review" if state["needs_clinician"] else "response"
    return "coach" if state["revision_count"] < 2 else "safe_fallback"


GENERIC_ADVICE = (
    "Pertahankan pencatatan harian dan tingkatkan aktivitas fisik secara bertahap sesuai pedoman."
)


async def safe_fallback(state: GraphState) -> dict:
    """Versi minimal yang aman: flags (dirender response) + saran umum template + sitasi."""
    passages = state.get("passages", [])
    actions = (
        [PlanAction(text=GENERIC_ADVICE, citations=[passages[0]["source_id"]])] if passages else []
    )
    plan = PlanContent(weeks=[PlanWeek(range="4 minggu", targets=[], actions=actions)])
    return {
        "plan_draft": plan.model_dump(mode="json"),
        "critique": {**(state.get("critique") or {}), "pass": True, "fallback": True},
    }


def make_create_review(review_graph: CompiledStateGraph) -> Any:
    async def create_review(state: GraphState) -> dict:
        uid = state["user_id"]
        plan = await toolbox.save_plan(
            uid,
            PlanIn(
                status="pending_review",
                content=PlanContent.model_validate(state["plan_draft"]),
                starts_on=today(),
            ),
        )
        thread_id = f"review-{plan.id}"
        async with SessionLocal() as session:
            review_id = await session.scalar(
                insert(ClinicianReview)
                .values(plan_id=plan.id, thread_id=thread_id)
                .returning(ClinicianReview.id)
            )
            await session.commit()
        await review_graph.ainvoke(
            {
                "review_id": review_id,
                "plan_id": plan.id,
                "user_id": uid,
                "assessment": {k: state[k] for k in ("flags", "framingham", "diabetes", "trends")},
            },
            {"configurable": {"thread_id": thread_id}},
        )
        return {}

    return create_review
