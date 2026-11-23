"""Mapping data user -> fitur BRFSS untuk model diabetes (PRD bagian 8.3)."""

from datetime import date
from statistics import fmean

from app.risk import guidelines as g
from app.schemas import Binary, DiabetesFeatures, LatestValues, Profile


def bmi(height_cm: float, weight_kg: float) -> float:
    return round(weight_kg / (height_cm / 100) ** 2, 1)


def age_category(age: int) -> int:
    """_AGEG5YR BRFSS: 1 = 18-24, 2 = 25-29, ..., 12 = 75-79, 13 = 80+."""
    return 1 if age < 25 else min(13, (age - 25) // 5 + 2)


def _b(value: bool | None) -> Binary:
    # TODO(PRD): jawaban profil "tidak tahu" (None) dianggap 0 (tidak), sesuai kode BRFSS biner.
    return 1 if value else 0


def build_features(
    profile: Profile,
    latest: LatestValues,
    age: int,
    systolic_30d: list[float],
    diastolic_30d: list[float],
) -> DiabetesFeatures | None:
    """None kalau berat badan belum pernah dicatat (BMI wajib)."""
    if latest.weight_kg is None:
        return None
    high_bp = (
        bool(profile.dx_hypertension)
        or (bool(systolic_30d) and fmean(systolic_30d) >= g.BP_STAGE1_SYS)
        or (bool(diastolic_30d) and fmean(diastolic_30d) >= g.BP_STAGE1_DIA)
    )
    high_chol = bool(profile.dx_high_chol) or (
        latest.cholesterol_total is not None and latest.cholesterol_total.value >= g.CHOL_HIGH
    )
    return DiabetesFeatures(
        HighBP=_b(high_bp),
        HighChol=_b(high_chol),
        BMI=bmi(profile.height_cm, latest.weight_kg.value),
        Smoker=_b(profile.smoker_lifetime_100),
        PhysActivity=_b(profile.phys_activity_30d),
        Fruits=_b(profile.fruits_daily),
        Veggies=_b(profile.veggies_daily),
        HvyAlcoholConsump=_b(profile.heavy_alcohol),
        GenHlth=profile.gen_health or 3,  # TODO(PRD): "tidak tahu" -> 3 (baik, nilai tengah)
        DiffWalk=_b(profile.diff_walk),
        Sex=1 if profile.sex == "male" else 0,
        Age=age_category(age),
    )


def age_years(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))
