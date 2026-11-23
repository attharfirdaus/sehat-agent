"""Evaluation harness (PRD bagian 15) dengan LLM asli. Hasil: eval/report.md.

Jalankan: `make eval` (butuh Ollama + model, DB dev, `make train`, `make ingest`).
Persona dibuat sebagai user sementara di DB dev lalu dihapus; checkpoint memakai InMemorySaver.
"""

import asyncio
import base64
import json
import statistics
import time
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import delete

from app.db.models import DailyLog, Measurement, User
from app.db.models import Profile as ProfileRow
from app.db.session import SessionLocal
from app.graph import llm, prompts
from app.graph.build import build_graph, thread_config
from app.graph.nodes.assess import deterministic_issues
from app.graph.nodes.intake import Extracted, IntentOut, ground
from app.safety.rules import evaluate
from app.schemas import LatestValues, MeasurementValue, PlanContent
from app.settings import settings
from app.tools.data import today
from app.tools.nutrition import estimate_meal_from_image

EVAL = Path(__file__).resolve().parent
FIELDS = ["steps", "sleep_hours", "water_l", "smoked", "alcohol"]
INTENTS = ["log", "history_question", "health_info", "smalltalk"]
N8N_BASELINE_S = 120  # rata-rata ±2 menit dari 8 percobaan versi n8n (PRD bagian 1)


def jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (EVAL / name).read_text().splitlines() if line.strip()]


def same(pred: Any, label: Any) -> bool:
    if isinstance(label, float | int) and not isinstance(label, bool) and pred is not None:
        return abs(float(pred) - label) <= 0.05
    return pred == label


async def eval_intake() -> dict:
    rows = jsonl("intake_30.jsonl")
    correct, exact = Counter(), 0
    for r in rows:
        out = await llm.structured(
            Extracted, prompts.INTAKE, llm.compact({"teks": r["text"], "sudah_terisi": {}})
        )
        pred = ground(out, r["text"])[0].model_dump() if out else {}  # sama dengan node
        ok = {f: same(pred.get(f), r["label"][f]) for f in FIELDS}
        correct.update(f for f, v in ok.items() if v)
        exact += all(ok.values())
    return {
        "n": len(rows),
        "per_field": {f: correct[f] / len(rows) for f in FIELDS},
        "exact_match": exact / len(rows),
    }


async def eval_routing() -> dict:
    rows = jsonl("routing_40.jsonl")
    confusion: Counter[tuple[str, str]] = Counter()
    for r in rows:
        out = await llm.structured(IntentOut, prompts.SUPERVISOR, r["text"])
        confusion[(r["intent"], out.intent if out else "smalltalk")] += 1
    acc = sum(n for (a, p), n in confusion.items() if a == p) / len(rows)
    return {"n": len(rows), "accuracy": acc, "confusion": confusion}


def eval_redflag() -> dict:
    cases = json.loads((EVAL / "redflag_15.json").read_text())
    now = datetime.now(UTC)
    missed = []
    for c in cases:
        latest = LatestValues(
            **{
                k: MeasurementValue(value=v, measured_at=now)
                for k, v in c.get("latest", {}).items()
            }
        )
        if c["expected"] not in [f.code for f in evaluate(latest, c["text"])]:
            missed.append(c["text"])
    return {"n": len(cases), "recall": 1 - len(missed) / len(cases), "missed": missed}


async def eval_meals() -> str:
    photos = sorted((EVAL / "meals_15").glob("*.jpg"))
    if not photos:
        return "Dilewati: belum ada foto di eval/meals_15/ (lihat README di folder itu)."
    labels = json.loads((EVAL / "meals_15" / "labels.json").read_text())
    errors, inside = [], 0
    for photo in photos:
        est = await estimate_meal_from_image(base64.b64encode(photo.read_bytes()).decode(), None)
        low = sum(i.kcal_low for i in est.items)
        high = sum(i.kcal_high for i in est.items)
        ref = labels[photo.name]["kcal"]
        errors.append(abs((low + high) / 2 - ref))
        inside += low <= ref <= high
    return (
        f"{len(photos)} foto · MAE kalori {statistics.mean(errors):.0f} kkal · "
        f"{pct(inside / len(photos))} referensi di dalam rentang estimasi."
    )


async def seed_persona(p: dict) -> int:
    t = today()
    prof = p["profile"]
    async with SessionLocal() as s:
        user = User(
            email=f"eval-{p['name']}-{uuid.uuid4().hex[:6]}@eval.local",
            password_hash="x",
            name=p["name"],
        )
        s.add(user)
        await s.flush()
        s.add(
            ProfileRow(
                user_id=user.id,
                birth_date=t.replace(year=t.year - prof["age"]),
                **{k: v for k, v in prof.items() if k != "age"},
            )
        )
        for i in range(1, 14):  # 13 hari sebelumnya, variasi kecil deterministik
            b = p["base"]
            s.add(
                DailyLog(
                    user_id=user.id,
                    log_date=t - timedelta(days=i),
                    source="form",
                    steps=round(b["steps"] * (1 + (i % 3 - 1) * 0.1)),
                    sleep_hours=b["sleep_hours"] + (i % 2 - 0.5) * 0.5,
                    water_l=b["water_l"],
                    smoked=b["smoked"],
                    alcohol=b["alcohol"],
                )
            )
        for kind, value in p["measurements"].items():
            s.add(
                Measurement(
                    user_id=user.id,
                    kind=kind,
                    value=value,
                    measured_at=datetime.now(UTC) - timedelta(days=2),
                )
            )
        await s.commit()
        return user.id


def message(base: dict) -> str:
    return (
        f"hari ini jalan {base['steps']} langkah, tidur {base['sleep_hours']} jam, minum "
        f"{base['water_l']} liter, {'merokok' if base['smoked'] else 'tidak merokok'}, "
        f"{'minum alkohol' if base['alcohol'] else 'tidak minum alkohol'}"
    )


async def run_persona(graph: Any, p: dict) -> dict:
    uid = await seed_persona(p)
    cfg = thread_config(uid)
    start = time.perf_counter()
    graph_input: Any = {
        "user_id": uid,
        "channel": "web",
        "image_b64": None,
        "draft_log": None,
        "messages": [HumanMessage(message(p["base"]))],
    }
    try:
        for _ in range(5):
            await graph.ainvoke(graph_input, cfg)
            snap = await graph.aget_state(cfg)
            if not snap.interrupts:
                break
            kind = snap.interrupts[0].value["type"]
            graph_input = Command(
                resume="tidak tahu" if kind == "clarify" else {"action": "confirm"}
            )
        state = (await graph.aget_state(cfg)).values
        issues = [
            i
            async for h in graph.aget_state_history(cfg)
            for i in ((h.values.get("critique") or {}).get("issues") or [])
        ]
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()
    elapsed = time.perf_counter() - start
    plan = state.get("plan_draft")
    critique = state.get("critique") or {}
    actions = [a for w in PlanContent.model_validate(plan).weeks for a in w.actions] if plan else []
    sources = {x["source_id"] for x in state.get("passages", [])}
    cited = sum(bool(a.citations) and set(a.citations) <= sources for a in actions)
    numbers_ok = plan is not None and not any(
        i.startswith("angka") for i in deterministic_issues(state, PlanContent.model_validate(plan))
    )
    return {
        "name": p["name"],
        "seconds": round(elapsed, 1),
        "actions": len(actions),
        "cited": cited,
        "grounded": numbers_ok,
        "critic_pass": bool(critique.get("pass")) and not critique.get("fallback"),
        "fallback": bool(critique.get("fallback")),
        "needs_clinician": bool(state.get("needs_clinician")),
        "flags": [f["code"] for f in state.get("flags", [])],
        "reason": (issues[0][:90].replace("|", "/") if issues and critique.get("fallback") else ""),
    }


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def report(intake: dict, routing: dict, redflag: dict, personas: list[dict], meals: str) -> str:
    secs = [p["seconds"] for p in personas]
    q = statistics.quantiles(secs, n=20) if len(secs) > 1 else secs * 19
    total_actions = sum(p["actions"] for p in personas) or 1
    model = json.loads(
        (Path(__file__).parents[1] / "backend/models/diabetes_xgb_v1.json").read_text()
    )
    lines = [
        "# Laporan evaluasi SehatAgent",
        "",
        f"Dijalankan {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · LLM `{settings.LLM_MODEL}` · "
        f"embedding `{settings.EMBED_MODEL}` · thinking {'on' if llm.THINKING else 'off'}.",
        "",
        "## Ringkasan vs target (PRD bagian 2)",
        "",
        "| Metrik | Hasil | Target |",
        "| --- | --- | --- |",
        f"| Akurasi ekstraksi intake (min. per field) | {pct(min(intake['per_field'].values()))} "
        "| >= 90% per field |",
        f"| Akurasi routing intent | {pct(routing['accuracy'])} | — |",
        f"| Recall red flag | {pct(redflag['recall'])} | 100% |",
        f"| Coverage sitasi | {pct(sum(p['cited'] for p in personas) / total_actions)} | 100% |",
        f"| Groundedness angka (persona) | "
        f"{pct(sum(p['grounded'] for p in personas) / len(personas))} | 100% |",
        f"| Lolos Safety Critic tanpa fallback | "
        f"{pct(sum(p['critic_pass'] for p in personas) / len(personas))} | — |",
        f"| Latensi check-in p50 / p95 | {statistics.median(secs):.0f} s / {q[18]:.0f} s "
        f"| < baseline n8n ±{N8N_BASELINE_S} s |",
        "",
        "## Intake (30 kalimat)",
        "",
        "| Field | Akurasi |",
        "| --- | --- |",
        *[f"| {f} | {pct(v)} |" for f, v in intake["per_field"].items()],
        f"| exact match per kalimat | {pct(intake['exact_match'])} |",
        "",
        "## Routing (40 pesan)",
        "",
        "Baris = label, kolom = prediksi.",
        "",
        "| | " + " | ".join(INTENTS) + " |",
        "| --- |" + " --- |" * len(INTENTS),
        *[
            f"| {a} | " + " | ".join(str(routing["confusion"][(a, p)]) for p in INTENTS) + " |"
            for a in INTENTS
        ],
        "",
        "## Red flag (15 kasus)",
        "",
        f"Recall {pct(redflag['recall'])}."
        + (" Terlewat: " + "; ".join(redflag["missed"]) if redflag["missed"] else ""),
        "",
        "## Persona (10)",
        "",
        "| Persona | Detik | Aksi | Bersitasi | Angka grounded | Lolos critic | Fallback | "
        "Review clinician | Flags | Alasan fallback |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {p['name']} | {p['seconds']} | {p['actions']} | {p['cited']} | {p['grounded']} | "
            f"{p['critic_pass']} | {p['fallback']} | {p['needs_clinician']} | "
            f"{', '.join(p['flags']) or '–'} | {p['reason'] or '–'} |"
            for p in personas
        ],
        "",
        "## Model diabetes (test split)",
        "",
        "| Metrik | Nilai |",
        "| --- | --- |",
        *[f"| {k} | {v} |" for k, v in model["test"].items()],
        f"| CV ROC-AUC (5-fold) | {model['cv_roc_auc_mean']} ± {model['cv_roc_auc_std']} |",
        "",
        "## Foto makanan",
        "",
        meals,
        "",
        "Belum dijalankan: review manusia oleh tenaga medis dan ablation (PRD bagian 15).",
    ]
    return "\n".join(lines) + "\n"


async def main() -> None:
    print("intake…")
    intake = await eval_intake()
    print("routing…")
    routing = await eval_routing()
    redflag = eval_redflag()
    graph = build_graph(InMemorySaver())
    personas = []
    for p in json.loads((EVAL / "personas_10.json").read_text()):
        print("persona", p["name"])
        personas.append(await run_persona(graph, p))
    meals = await eval_meals()
    (EVAL / "report.md").write_text(report(intake, routing, redflag, personas, meals))
    print((EVAL / "report.md").read_text())


if __name__ == "__main__":
    asyncio.run(main())
