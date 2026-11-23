import json
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Literal

import joblib
import pandas as pd
import shap

from app.risk import guidelines as g
from app.risk.features import age_years, bmi
from app.risk.framingham import risk_10y_pct
from app.schemas import (
    DiabetesFeatures,
    DiabetesPrediction,
    Flag,
    FraminghamResult,
    LatestValues,
    MeasurementValue,
    Profile,
    ShapFactor,
)
from app.tools.data import today

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "diabetes_xgb_v1.joblib"


def _stale(*values: MeasurementValue) -> bool:
    cutoff = datetime.now(UTC) - timedelta(days=g.STALE_DAYS)
    return any(v.measured_at < cutoff for v in values)


def _flag(
    code: str,
    severity: Literal["info", "warn", "urgent"],
    metric: str,
    value: Any,
    threshold: str,
    source_id: str | None,
    stale: bool = False,
) -> Flag:
    if stale and severity == "urgent":  # data lama tidak memicu urgent (8.1)
        severity = "warn"
    return Flag(
        code=code,
        severity=severity,
        metric=metric,
        value=value,
        threshold=threshold,
        source_id=source_id,
        stale=stale,
    )


async def guideline_flags(profile: Profile, latest: LatestValues) -> list[Flag]:
    """Flag berbasis ambang di app/risk/guidelines.py (bagian 8.1). Measurement > 90 hari
    diberi `stale=True` dan tidak memicu urgent."""
    flags: list[Flag] = []
    sys_, dia = latest.systolic, latest.diastolic
    if sys_ and dia:
        bp, stale = f"{sys_.value:g}/{dia.value:g}", _stale(sys_, dia)
        if sys_.value >= g.BP_CRISIS_SYS or dia.value >= g.BP_CRISIS_DIA:
            flags.append(
                _flag(
                    "BP_CRISIS",
                    "urgent",
                    "blood_pressure",
                    bp,
                    f">={g.BP_CRISIS_SYS}/>={g.BP_CRISIS_DIA}",
                    g.BP_SOURCE,
                    stale,
                )
            )
        elif sys_.value >= g.BP_STAGE2_SYS or dia.value >= g.BP_STAGE2_DIA:
            flags.append(
                _flag(
                    "BP_STAGE2",
                    "warn",
                    "blood_pressure",
                    bp,
                    f">={g.BP_STAGE2_SYS}/>={g.BP_STAGE2_DIA}",
                    g.BP_SOURCE,
                    stale,
                )
            )
        elif sys_.value >= g.BP_STAGE1_SYS or dia.value >= g.BP_STAGE1_DIA:
            flags.append(
                _flag(
                    "BP_STAGE1",
                    "warn",
                    "blood_pressure",
                    bp,
                    f"{g.BP_STAGE1_SYS}-{g.BP_STAGE2_SYS - 1}/"
                    f"{g.BP_STAGE1_DIA}-{g.BP_STAGE2_DIA - 1}",
                    g.BP_SOURCE,
                    stale,
                )
            )
        elif sys_.value >= g.BP_ELEVATED_SYS:
            flags.append(
                _flag(
                    "BP_ELEVATED",
                    "info",
                    "blood_pressure",
                    bp,
                    f"{g.BP_ELEVATED_SYS}-{g.BP_STAGE1_SYS - 1}/<{g.BP_STAGE1_DIA}",
                    g.BP_SOURCE,
                    stale,
                )
            )
    if latest.weight_kg:
        # Bandingkan nilai mentah; pembulatan hanya untuk tampilan (18,48 tetap < 18,5).
        raw = latest.weight_kg.value / (profile.height_cm / 100) ** 2
        b, stale = round(raw, 1), _stale(latest.weight_kg)
        if raw >= g.BMI_OBESE:
            flags.append(
                _flag("BMI_OBESE", "warn", "bmi", b, f">={g.BMI_OBESE}", g.BMI_SOURCE, stale)
            )
        elif raw >= g.BMI_OVERWEIGHT:
            flags.append(
                _flag(
                    "BMI_OVERWEIGHT",
                    "warn",
                    "bmi",
                    b,
                    f"{g.BMI_OVERWEIGHT}-{g.BMI_OBESE}",
                    g.BMI_SOURCE,
                    stale,
                )
            )
        elif raw < g.BMI_UNDERWEIGHT:
            flags.append(
                _flag(
                    "BMI_UNDERWEIGHT",
                    "warn",
                    "bmi",
                    b,
                    f"<{g.BMI_UNDERWEIGHT}",
                    g.BMI_SOURCE,
                    stale,
                )
            )
    if profile.phys_activity_30d is False:
        flags.append(
            _flag(
                "PA_NONE",
                "info",
                "physical_activity",
                "tidak ada (30 hari)",
                f">={g.PA_MIN_MINUTES_WEEK} menit/minggu",
                g.PA_SOURCE,
            )
        )
    if (
        g.STEPS_PROXY_MIN is not None
        and latest.avg_steps_7d is not None
        and latest.avg_steps_7d < g.STEPS_PROXY_MIN
    ):
        flags.append(
            _flag(
                "STEPS_LOW",
                "info",
                "steps",
                round(latest.avg_steps_7d),
                f">={g.STEPS_PROXY_MIN}",
                g.PA_SOURCE,
            )
        )
    if latest.avg_sleep_7d is not None and latest.avg_sleep_7d < g.SLEEP_MIN_HOURS:
        flags.append(
            _flag(
                "SLEEP_SHORT",
                "info",
                "sleep_hours",
                round(latest.avg_sleep_7d, 1),
                f"<{g.SLEEP_MIN_HOURS:g}",
                g.SLEEP_SOURCE,
            )
        )
    if latest.cholesterol_total:
        c, stale = latest.cholesterol_total.value, _stale(latest.cholesterol_total)
        if c >= g.CHOL_HIGH:
            flags.append(
                _flag(
                    "CHOL_HIGH",
                    "warn",
                    "cholesterol_total",
                    c,
                    f">={g.CHOL_HIGH}",
                    g.CHOL_SOURCE,
                    stale,
                )
            )
        elif c >= g.CHOL_BORDERLINE:
            flags.append(
                _flag(
                    "CHOL_BORDERLINE",
                    "warn",
                    "cholesterol_total",
                    c,
                    f"{g.CHOL_BORDERLINE}-{g.CHOL_HIGH - 1}",
                    g.CHOL_SOURCE,
                    stale,
                )
            )
    if latest.resting_hr and latest.resting_hr.value > g.RESTING_HR_HIGH:
        flags.append(
            _flag(
                "RHR_HIGH",
                "warn",
                "resting_hr",
                latest.resting_hr.value,
                f">{g.RESTING_HR_HIGH}",
                g.RHR_SOURCE,
                _stale(latest.resting_hr),
            )
        )
    if latest.smoked_days_7d:
        flags.append(
            _flag(
                "SMOKING",
                "warn",
                "smoked",
                f"{latest.smoked_days_7d} hari/7",
                "0 hari",
                g.SMOKING_SOURCE,
            )
        )
    return flags


async def framingham_nonlab(profile: Profile, latest: LatestValues) -> FraminghamResult:
    """Framingham 2008 non-lab (D'Agostino et al.), risiko CVD 10 tahun. Usia di luar 30-74:
    `applicable=False, reason="age_out_of_range"`."""
    age = age_years(profile.birth_date, today())
    if not g.FRAMINGHAM_AGE_MIN <= age <= g.FRAMINGHAM_AGE_MAX:
        return FraminghamResult(applicable=False, reason="age_out_of_range")
    if latest.weight_kg is None:
        return FraminghamResult(applicable=False, reason="missing_weight")
    if latest.systolic is None:
        return FraminghamResult(applicable=False, reason="missing_systolic")
    pct = risk_10y_pct(
        profile.sex,
        age,
        bmi(profile.height_cm, latest.weight_kg.value),
        latest.systolic.value,
        bp_treated=bool(profile.bp_treated),
        # TODO(PRD): status perokok saat ini dari log 7 hari (profil hanya punya definisi BRFSS).
        smoker=bool(latest.smoked_days_7d),
        diabetes=bool(profile.dx_diabetes),
    )
    category: Literal["low", "intermediate", "high"] = (
        "high"
        if pct >= g.FRAMINGHAM_HIGH_PCT
        else "intermediate"
        if pct >= g.FRAMINGHAM_INTERMEDIATE_PCT
        else "low"
    )
    return FraminghamResult(applicable=True, risk_10y_pct=pct, category=category)


@cache
def _model(path: Path) -> tuple[dict, shap.TreeExplainer, str]:
    if not path.exists():
        raise FileNotFoundError(f"{path} belum ada: jalankan `make train`")
    bundle = joblib.load(path)
    version = json.loads(path.with_suffix(".json").read_text())["model_version"]
    return bundle, shap.TreeExplainer(bundle["base"]), version


async def predict_diabetes(features: DiabetesFeatures) -> DiabetesPrediction:
    """Probabilitas terkalibrasi diabetes/prediabetes + top-3 faktor SHAP (bagian 8.3)."""
    bundle, explainer, version = _model(MODEL_PATH)
    row = pd.DataFrame([features.model_dump()])[bundle["features"]]
    prob = float(bundle["calibrated"].predict_proba(row)[0, 1])
    values = explainer.shap_values(row)[0]
    top = sorted(zip(bundle["features"], values, strict=True), key=lambda t: -abs(t[1]))[:3]
    band: Literal["low", "moderate", "high"] = (
        "high"
        if prob >= g.DIABETES_HIGH_PROB
        else "moderate"
        if prob >= g.DIABETES_MODERATE_PROB
        else "low"
    )
    return DiabetesPrediction(
        prob=round(prob, 4),
        band=band,
        top_factors=[
            ShapFactor(
                feature=f,
                value=float(row[f].iloc[0]),
                shap=round(float(v), 4),
                direction="increase" if v > 0 else "decrease",
            )
            for f, v in top
        ],
        model_version=version,
    )
