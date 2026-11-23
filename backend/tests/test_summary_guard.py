"""Ringkasan LLM tidak boleh bertentangan dengan flag (mis. "berat badan ideal" + BMI berlebih)."""

from typing import Any

import pytest

from app.graph.nodes.assess import contradicts_flags

BMI = [{"code": "BMI_OVERWEIGHT"}]
BP_SLEEP = [{"code": "BP_STAGE1"}, {"code": "SLEEP_SHORT"}]


@pytest.mark.parametrize(
    ("summary", "flags"),
    [
        (
            "Hasil pemeriksaan menunjukkan Anda memiliki berat badan ideal (BMI 23,2) dan "
            "kemungkinan diabetes rendah.",
            BMI,
        ),
        ("BMI Anda normal, namun tidur masih kurang.", BMI),
        ("Tekanan darah Anda aman. Tidur perlu ditambah.", BP_SLEEP),
        ("Durasi tidur Anda sudah cukup.", BP_SLEEP),
    ],
)
def test_detects_contradiction(summary: str, flags: Any) -> None:
    assert contradicts_flags(summary, flags)


@pytest.mark.parametrize(
    ("summary", "flags"),
    [
        ("Berat badan Anda berlebih dan belum ideal. Kurangi porsi makan malam.", BMI),
        ("Tekanan darah sedikit di atas normal dan tidur kurang dari 7 jam.", BP_SLEEP),
        ("Usahakan tidur cukup agar tekanan darah kembali normal.", BP_SLEEP),
        ("Perbaiki pola tidur supaya lebih baik demi kesehatan jangka panjang.", BP_SLEEP),
        ("Risiko jantung Anda rendah dan kemungkinan diabetes juga baik.", BMI),  # topik lain
    ],
)
def test_allows_consistent_summary(summary: str, flags: Any) -> None:
    assert not contradicts_flags(summary, flags)
