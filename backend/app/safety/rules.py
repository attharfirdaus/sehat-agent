"""Red flag deterministik (PRD bagian 13): ambang angka + keyword gejala. Tanpa LLM.

NEEDS_VERIFICATION: daftar keyword dan pola diverifikasi track C (bagian 17).
"""

import re
from datetime import UTC, datetime, timedelta

from app.risk import guidelines as g
from app.schemas import LatestValues, MeasurementValue, RedFlag

_NORMALIZE = [
    (r"(.)\1{2,}", r"\1"),  # "sakiiit" -> "sakit"
    (r"\bnafas\b", "napas"),
    (r"\bbernafas\b", "bernapas"),
    (r"\b(gak|ga|gk|nggak|ngga|enggak|engga|tdk|tak|ndak)\b", "tidak"),
    (r"\b(bgt|bngt|bener|beneran)\b", "banget"),
    (r"\bsblh\b", "sebelah"),
]

_NOT = r"(?:(?!\btidak\b)[^.!?\n]){0,25}?"  # rentang pendek tanpa negasi "tidak"

SYMPTOM_PATTERNS = [
    rf"\bdada(ku|nya)?\b{_NOT}\b(sakit|nyeri|sesak|ditekan|tertekan|tertindih|berat|perih|ngilu)",
    rf"\b(sakit|nyeri|sesak|tertekan|ngilu)\b{_NOT}\bdada(ku|nya)?\b",
    r"\bsesak\s+napas\b[^.!?\n]{0,20}\b(berat|parah|banget|sekali|hebat)\b",
    r"\b(tidak bisa|susah|sulit|sukar)\s+(ber)?napas\b",
    r"\b(pingsan|tidak sadarkan diri|hilang kesadaran)\b",
    r"\b(lemah|lemas|mati rasa|kesemutan|kebas|lumpuh)\b[^.!?\n]{0,20}"
    r"\b(satu sisi|sebelah|separuh)\b",
    r"\b(wajah|muka|mulut)\b[^.!?\n]{0,15}\b(mencong|perot|miring|turun sebelah)\b",
    r"\b(bicara|ngomong|bicaranya|omongan)\b[^.!?\n]{0,15}\b(pelo|cadel|tidak jelas|kacau)\b",
]

SELFHARM_PATTERNS = [
    r"\bbunuh diri\b",
    r"\b(ingin|pengen|pingin|mau|kepikiran)\s+(mati|mengakhiri hidup)\b",
    r"\bmengakhiri hidup\b",
    r"\b(menyakiti|melukai|nyakitin|ngelukain)\s+(diri|diriku|diri sendiri)\b",
    r"\b(self[- ]?harm|nyilet|menyilet)\b",
    r"\btidak (mau|ingin|pengen) hidup lagi\b",
]


def normalize(text: str) -> str:
    t = text.lower()
    for pattern, repl in _NORMALIZE:
        t = re.sub(pattern, repl, t)
    return t


_NEGATION_BEFORE = re.compile(r"\b(tidak|belum|bukan)\b(\s+\w+){0,2}\s*$")


def _match(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        for m in re.finditer(p, text):
            if not _NEGATION_BEFORE.search(text[: m.start()]):  # "tidak pernah pingsan"
                return m.group(0)
    return None


def _recent(v: MeasurementValue | None) -> bool:
    # TODO(PRD): jendela 24 jam juga dipakai RF-HR (PRD hanya menyebutnya untuk RF-BP-CRISIS).
    return v is not None and v.measured_at >= datetime.now(UTC) - timedelta(
        hours=g.RF_BP_WINDOW_HOURS
    )


def evaluate(latest: LatestValues, user_text: str) -> list[RedFlag]:
    flags: list[RedFlag] = []
    text = normalize(user_text)
    if hit := _match(SYMPTOM_PATTERNS, text):
        flags.append(RedFlag(code="RF-SYMPTOM", detail={"match": hit}))
    if hit := _match(SELFHARM_PATTERNS, text):
        flags.append(RedFlag(code="RF-SELFHARM", detail={"match": hit}))
    sys_ = latest.systolic if _recent(latest.systolic) else None
    dia = latest.diastolic if _recent(latest.diastolic) else None
    if (sys_ and sys_.value >= g.BP_CRISIS_SYS) or (dia and dia.value >= g.BP_CRISIS_DIA):
        flags.append(
            RedFlag(
                code="RF-BP-CRISIS",
                detail={
                    "systolic": sys_.value if sys_ else None,
                    "diastolic": dia.value if dia else None,
                },
            )
        )
    hr = latest.resting_hr
    if _recent(hr) and hr is not None and (hr.value > g.RF_HR_HIGH or hr.value < g.RF_HR_LOW):
        flags.append(RedFlag(code="RF-HR", detail={"resting_hr": hr.value}))
    return flags
