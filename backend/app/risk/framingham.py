"""Framingham 2008 general CVD, model non-laboratorium berbasis BMI.

D'Agostino RB et al. General cardiovascular risk profile for use in primary care.
Circulation 2008;117:743-753. Rumus sama dengan `ascvd_10y_frs_simple` paket R CVrisk:
risk = 1 - S0 ^ exp(sum(beta * x) - mean), x = ln(usia), ln(BMI), ln(SBP) (dipisah treated /
untreated), perokok, diabetes. Kalibrasi untuk populasi Indonesia belum divalidasi.
"""

import math
from typing import Literal

# Pria: terverifikasi terhadap contoh dokumentasi CVrisk (55 th, BMI 30, SBP 140 tanpa obat,
# bukan perokok, non-diabetes -> 16.7%).
# NEEDS_VERIFICATION: koefisien wanita dari paper (Tabel 2) belum dicocokkan ke CVrisk
# (butuh R: `CVrisk::frs_simple_coef`).
COEF = {
    "male": {
        "ln_age": 3.11296,
        "ln_bmi": 0.79277,
        "ln_sbp_untreated": 1.85508,
        "ln_sbp_treated": 1.92672,
        "smoker": 0.70953,
        "diabetes": 0.53160,
        "mean": 23.9388,
        "s0": 0.88431,
    },
    "female": {
        "ln_age": 2.72107,
        "ln_bmi": 0.51125,
        "ln_sbp_untreated": 2.81291,
        "ln_sbp_treated": 2.88267,
        "smoker": 0.61868,
        "diabetes": 0.77763,
        "mean": 26.0145,
        "s0": 0.94833,
    },
}


def risk_10y_pct(
    sex: Literal["male", "female"],
    age: float,
    bmi: float,
    sbp: float,
    bp_treated: bool,
    smoker: bool,
    diabetes: bool,
) -> float:
    """Risiko CVD 10 tahun dalam persen (2 desimal, seperti CVrisk; tanpa clamp 1-30)."""
    c = COEF[sex]
    s = (
        c["ln_age"] * math.log(age)
        + c["ln_bmi"] * math.log(bmi)
        + (c["ln_sbp_treated"] if bp_treated else c["ln_sbp_untreated"]) * math.log(sbp)
        + c["smoker"] * smoker
        + c["diabetes"] * diabetes
    )
    return round((1 - c["s0"] ** math.exp(s - c["mean"])) * 100, 2)
