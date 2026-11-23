"""Teks hasil penilaian untuk orang awam: tanpa kode flag, nama fitur, atau istilah Inggris."""

import re

from app.graph import prompts
from app.graph.nodes.answer import render_assessment
from app.tools import mocks

JARGON = re.compile(
    r"[A-Z]{2,}_[A-Z]+|Framingham|BRFSS|age_out_of_range|\b(low|moderate|high)\b|HighBP|Age\b"
)


def test_number_format() -> None:
    assert [prompts.num(v) for v in (8500, 6.5, 4.0, 1.29)] == ["8.500", "6,5", "4", "1,3"]


def test_flag_and_risk_texts() -> None:
    line = prompts.flag_line({"code": "SLEEP_SHORT", "value": 4.0, "stale": False})
    assert (
        line == "- **Tidur kurang dari 7 jam**: rata-rata 4 jam per malam, disarankan minimal 7 jam"
    )
    smoke = prompts.flag_line({"code": "SMOKING", "value": "2 hari/7", "stale": True})
    assert smoke == "- **Merokok**: merokok 2 dari 7 hari terakhir (data lebih dari 3 bulan lalu)"
    assert "usia 30 sampai 74" in prompts.heart_text(
        {"applicable": False, "reason": "age_out_of_range"}
    )
    dm = {
        "prob": 0.0129,
        "band": "low",
        "top_factors": [
            {"feature": "Age", "value": 5, "direction": "increase"},
            {"feature": "HighBP", "value": 1, "direction": "increase"},
            {"feature": "HighChol", "value": 0, "direction": "decrease"},
        ],
    }
    text = prompts.diabetes_text(dm)
    assert (
        "rendah (sekitar 1%)" in text
        and "menaikkan: usia Anda, riwayat tekanan darah tinggi." in text
    )
    assert "menurunkan: tidak ada riwayat kolesterol tinggi." in text and not JARGON.search(text)
    assert prompts.target_text("sleep_hours", 7) == "tidur 7 jam per malam"


def test_render_assessment_has_no_jargon() -> None:
    state = {
        "channel": "web",
        "passages": [],
        "trends": {"interpretation": "Tidur Anda masih kurang."},
        "flags": [
            {"code": "SLEEP_SHORT", "value": 4.0, "threshold": "<7", "stale": False},
            {"code": "BP_STAGE1", "value": "132/84", "threshold": "", "stale": False},
        ],
        "framingham": {"applicable": False, "reason": "age_out_of_range"},
        "diabetes": {
            "prob": 0.01,
            "band": "low",
            "top_factors": [{"feature": "Age", "direction": "increase"}],
        },
        "plan_draft": mocks.SAMPLE_PLAN_CONTENT.model_dump(),
        "critique": {"pass": True},
    }
    text = render_assessment(state)  # type: ignore[arg-type]
    assert not JARGON.search(text), JARGON.search(text)
    assert "Yang perlu diperhatikan" in text and "tensi 132/84 mmHg" in text
    bmi = prompts.flag_line({"code": "BMI_OVERWEIGHT", "value": 24.0})
    assert bmi == (
        "- **Berat badan berlebih**: BMI 24 (perbandingan berat dan tinggi badan); "
        "untuk orang Asia, normal sampai 22,9"
    )
    assert "#### minggu 1\nTarget: langkah 7.000 per hari" in text
    assert text.startswith("### Hasil penilaian hari ini")
    assert "### Perkiraan risiko\n- **Penyakit jantung:** Belum bisa dihitung, karena" in text
    assert "- **Diabetes:** Rendah (sekitar 1%)." in text


def test_plain_text_for_telegram() -> None:
    from app.graph.nodes.answer import plain_text

    md = "### Judul\n- **Label**: isi\n\n> Catatan: bukan diagnosis."
    assert plain_text(md) == "Judul\n- Label: isi\n\nCatatan: bukan diagnosis."
