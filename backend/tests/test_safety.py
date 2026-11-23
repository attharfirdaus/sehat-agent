"""red_flag_rules: 15 kasus positif + 15 negatif, termasuk ejaan informal (bagian 15)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.safety.rules import evaluate
from app.schemas import LatestValues, MeasurementValue

NOW = datetime.now(UTC)

POSITIVE = [
    ("dada sakit banget dari tadi", "RF-SYMPTOM"),
    ("dada saya nyeri kayak ditekan", "RF-SYMPTOM"),
    ("nyeri di dada kiri menjalar ke lengan", "RF-SYMPTOM"),
    ("dadaku sakiiit bgt", "RF-SYMPTOM"),  # perlu normalisasi huruf berulang + "bgt"
    ("sesak nafas berat sejak pagi", "RF-SYMPTOM"),
    ("gak bisa napas", "RF-SYMPTOM"),
    ("susah bernafas pas tiduran", "RF-SYMPTOM"),
    ("tadi sempat pingsan di kantor", "RF-SYMPTOM"),
    ("tangan kiri lemas sebelah dan kesemutan", "RF-SYMPTOM"),
    ("tiba2 mati rasa satu sisi tubuh", "RF-SYMPTOM"),
    ("ngomong jadi pelo dari sejam lalu", "RF-SYMPTOM"),
    ("wajah ibu mencong sebelah", "RF-SYMPTOM"),
    ("aku pengen mati aja", "RF-SELFHARM"),
    ("kepikiran bunuh diri", "RF-SELFHARM"),
    ("udah ga mau hidup lagi", "RF-SELFHARM"),
]

NEGATIVE = [
    "jalan 6rb langkah, tidur 5 jam",
    "dada tidak sakit kok, cuma capek",
    "habis lari agak sesak napas dikit",
    "napas lega setelah yoga",
    "kaki pegal setelah naik tangga",
    "saya tidak pernah pingsan",
    "tensi 130/85, nadi 72",
    "makan nasi padang, minum es teh",
    "pengen makan sate",
    "mau tidur cepat malam ini",
    "nonton film tentang bunuh-bunuhan zombie",
    "otot lengan nyeri habis gym",
    "berat badan 70 kg",
    "bicara di depan umum bikin deg-degan",
    "tidur siang sebelah kiri biar nyaman",
]


@pytest.mark.parametrize(("text", "code"), POSITIVE)
def test_positive(text: str, code: str) -> None:
    assert code in [f.code for f in evaluate(LatestValues(), text)]


@pytest.mark.parametrize("text", NEGATIVE)
def test_negative(text: str) -> None:
    assert evaluate(LatestValues(), text) == []


def mv(value: float, hours_ago: float) -> MeasurementValue:
    return MeasurementValue(value=value, measured_at=NOW - timedelta(hours=hours_ago))


def test_numeric_red_flags() -> None:
    crisis = evaluate(LatestValues(systolic=mv(182, 1), diastolic=mv(95, 1)), "")
    assert [f.code for f in crisis] == ["RF-BP-CRISIS"] and crisis[0].detail["systolic"] == 182
    assert [f.code for f in evaluate(LatestValues(diastolic=mv(120, 2)), "")] == ["RF-BP-CRISIS"]
    assert evaluate(LatestValues(systolic=mv(179, 1), diastolic=mv(119, 1)), "") == []
    assert evaluate(LatestValues(systolic=mv(200, 30)), "") == []  # > 24 jam
    assert [f.code for f in evaluate(LatestValues(resting_hr=mv(121, 1)), "")] == ["RF-HR"]
    assert [f.code for f in evaluate(LatestValues(resting_hr=mv(39, 1)), "")] == ["RF-HR"]
    assert evaluate(LatestValues(resting_hr=mv(120, 1)), "") == []
    assert evaluate(LatestValues(resting_hr=mv(40, 1)), "") == []
